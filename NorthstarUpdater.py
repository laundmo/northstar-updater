import configparser
import time
from datetime import datetime, timedelta
from pathlib import Path
from github.GitRelease import GitRelease
import shutil
import requests
import tempfile
import zipfile
from github import Github
import sys
import traceback
import subprocess
from tqdm import tqdm

config = configparser.ConfigParser()

config["Northstar"] = {
    "repository": "R2Northstar/Northstar",
    "last_update": "2021-12-29T05:14:32",
    "ignore_prerelease": "true",
    "file": "NorthstarLauncher.exe",
    "install_dir": ".",
    "exclude_files": "ns_startup_args.txt|ns_startup_args_dedi.txt",
}
config["NorthstarUpdater"] = {
    "repository": "laundmo/northstar-updater",
    "last_update": "0001-01-01T00:00:00",
    "ignore_prerelease": "true",
    "file": "NorthstarUpdater.exe",
    "install_dir": ".",
    "exclude_files": "",
}
config["ExampleMod"] = {
    "repository": "example/example-mod",
    "last_update": "0001-01-01T00:00:00",
}
config["Launcher"] = {"filename": "NorthstarLauncher.exe", "arguments": ""}


config.read("updater_config.ini")

if "Version" in config:
    del config["Version"]

if "Updater" in config:
    del config["Updater"]

if "ignore_prerelease" in config["ExampleMod"]:
    del config["ExampleMod"]["ignore_prerelease"]
if "file" in config["ExampleMod"]:
    del config["ExampleMod"]["file"]
if "install_dir" in config["ExampleMod"]:
    del config["ExampleMod"]["install_dir"]

g = Github()


def download(url, download_file):
    with requests.get(url, stream=True) as response:
        total = int(response.headers.get("content-length", 0))
        block_size = 1024
        with tqdm(
            total=total, unit_scale=True, unit_divisor=block_size, unit="B"
        ) as progress:
            for data in response.iter_content(block_size):
                progress.update(len(data))
                download_file.write(data)


class NoValidRelease(Exception):
    pass


class NoValidAsset(Exception):
    pass


class FileNotInZip(Exception):
    pass


update_everything = False
try:
    i = sys.argv.index("--update-everything")
    sys.argv.pop(i)
    update_everything = True
except ValueError:
    pass


class Updater:
    def __init__(self, blockname):
        self.blockname = blockname
        self.repository = config.get(blockname, "repository")
        self._file = config.get(self.blockname, "file", fallback="mod.json")
        self.repo = g.get_repo(self.repository)
        self.ignore_prerelease = config.getboolean(
            blockname, "ignore_prerelease", fallback=True
        )
        self.install_dir = Path(
            config.get(blockname, "install_dir", fallback="./R2Northstar/mods")
        )
        self.file = (self.install_dir / self._file).resolve()
        self.exclude_files = config.get(blockname, "exclude_files", fallback="").split(
            "|"
        )

    @property
    def last_update(self):
        return datetime.fromisoformat(
            config.get(self.blockname, "last_update", fallback=datetime.min.isoformat())
        )

    @last_update.setter
    def last_update(self, value: datetime):
        config.set(self.blockname, "last_update", value.isoformat())

    def release(self):
        releases = self.repo.get_releases()
        for release in releases:
            if release.prerelease and self.ignore_prerelease:
                continue
            if update_everything:
                return release
            if release.published_at > self.last_update:
                return release
            if self._file != "mod.json":
                if not self.file.exists():
                    return release
            # TODO: check for installed mods that dont use file and rely on some path-modifying extract method.
            # maybe another config var for check installed path thats only used for checking and automatically written on successful extract?
        raise NoValidRelease("No new release found")

    def asset(self, release: GitRelease):
        assets = release.get_assets()
        for asset in assets:
            if asset.content_type in (
                "application/zip",
                "application/x-zip-compressed",
            ):
                return asset
        raise NoValidAsset("No valid asset was found in release")

    def _mod_json_extractor(self, zip_: zipfile.ZipFile):
        parts = None
        found = None
        for fileinfo in zip_.infolist():
            fp = Path(fileinfo.filename)
            if fp.name == self._file:
                parts = fp.parts[:-2]
                found = fp
                break
        if parts:
            for fileinfo in zip_.infolist():
                fp = Path(fileinfo.filename)
                strip = len(parts)
                if fp.parts[:strip] == parts:
                    new_fp = Path(*fp.parts[strip:])
                    fileinfo.filename = str(new_fp) + (
                        "/" if fileinfo.filename.endswith("/") else ""
                    )
                    zip_.extract(fileinfo, self.install_dir)
        elif found:
            for fileinfo in zip_.infolist():
                if zip_.filename:
                    fp = Path(Path(zip_.filename).stem) / fileinfo.filename
                    zip_.extract(fileinfo, self.install_dir)
        else:
            raise FileNotInZip(f"mod.json not found in the selected release zip.")

    def _file_extractor(self, zip_: zipfile.ZipFile):
        namelist = zip_.namelist()
        if self._file in namelist or self._file.strip("/") + "/mod.json" in namelist:
            for file_ in namelist:
                if file_ not in self.exclude_files:
                    zip_.extract(file_, self.install_dir)
        else:
            for zip_info in zip_.infolist():
                zip_info.filename
            raise FileNotInZip(f"{self._file} not found in the selected release zip.")

    def extract(self, zip_: zipfile.ZipFile):
        if self._file != "mod.json":
            self._file_extractor(zip_)
        else:
            self._mod_json_extractor(zip_)

    def run(self):
        print(f"Started updater for {self.blockname}")
        try:
            release = self.release()
            asset = self.asset(release)
        except NoValidRelease:
            print("No new release found")
            return
        except NoValidAsset:
            print("No matching asset in release, possibly faulty release.")
            return
        with tempfile.NamedTemporaryFile() as download_file:
            download(asset.browser_download_url, download_file)
            release_zip = zipfile.ZipFile(download_file)
            self.extract(release_zip)
            self.last_update = release.published_at


class SelfUpdater(Updater):
    def release(self):
        releases = self.repo.get_releases()
        for release in releases:
            if release.prerelease and self.ignore_prerelease:
                continue
            if release.published_at > self.last_update:
                return release
            if not self.file.exists():
                return release
            if datetime.fromtimestamp(
                self.file.stat().st_mtime
            ) < release.published_at - timedelta(hours=1):
                return release
        raise NoValidRelease("No new release found")

    def asset(self, release: GitRelease):
        assets = release.get_assets()
        for asset in assets:
            if asset.content_type in ("application/x-msdownload",):
                return asset
        raise NoValidAsset("No valid asset was found in release")

    def run(self):
        print(f"Started updater for {self.blockname}")
        try:
            release = self.release()
            asset = self.asset(release)
        except NoValidRelease:
            print("No new release found")
            return
        except NoValidAsset:
            print("No matching asset in release, possibly faulty release.")
            return
        with tempfile.NamedTemporaryFile(delete=False) as download_file:
            download(asset.browser_download_url, download_file)
        newfile = self.file.with_suffix(".new")
        shutil.move(download_file.name, newfile)
        script = f"timeout 20 && del {self.file} && move {newfile} {self.file}"
        subprocess.Popen(["cmd", "/c", script])
        print("Starting timer for self-replacer, please dont interrupt.")
        self.last_update = release.published_at


def main():
    for section in config.sections():
        try:
            if section not in ("Launcher", "ExampleMod"):
                if section == "NorthstarUpdater":
                    u = SelfUpdater(section)
                    u.run()
                else:
                    u = Updater(section)
                    u.run()
        except FileNotInZip:
            print(f"Zip file for {section} doesn't contain expected files.")
        except Exception as e:
            traceback.print_exc()
            print(f"Starting Northstar in 10 seconds")
            time.sleep(10)
    try:
        subprocess.run(
            [config.get("Launcher", "filename")]
            + config.get("Launcher", "arguments").split(" ")
            + sys.argv[1:],
            cwd=str(Path.cwd()),
        )
    except FileNotFoundError:
        print(
            f"Could not run {config.get('Launcher', 'filename')}, does this file exist or is the configuration wrong?"
        )


main()
with open("updater_config.ini", "w+") as f:
    config.write(f)
