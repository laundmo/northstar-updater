from pathlib import Path
import tempfile
import zipfile

import httpx
import configparser
import semver
import sys
import subprocess
from tqdm import tqdm

config = configparser.ConfigParser()

config["Updater"] = {
    "repository": "R2Northstar/Northstar",
    "ignore_prerelease": "true",
}
config["Launcher"] = {
    "filename": "NorthstarLauncher.exe",
    "arguments": "",
}
config["Version"] = {"semver": "0.0.0"}

config.read("updater_config.ini")

repo_url = f"https://api.github.com/repos/{config.get('Updater', 'repository')}/"

client = httpx.Client(base_url=repo_url, follow_redirects=True)


def should_download(tag: str) -> bool:
    current_ver = semver.VersionInfo.parse(config.get("Version", "semver"))
    tag = tag.removeprefix("v")
    return current_ver < tag or not (Path.cwd() / config.get("Launcher", "filename")).exists()


class NoNewVersion(Exception):
    pass


def get_release():
    releases = client.get("releases").json()
    older = []
    for release in releases:
        if config.get("Updater", "ignore_prerelease") and release["prerelease"]:
            continue
        if should_download(release["tag_name"]):
            return release
        else:
            older.append(release)
    raise NoNewVersion("No newer version could be found", older)


class ReleaseIssue(Exception):
    pass


def get_asset(release_id) -> str:
    release = client.get(f"/releases/{release_id}/assets")
    for release_file in release.json():
        if release_file["content_type"] == "application/x-zip-compressed":
            return release_file["browser_download_url"]
    raise ReleaseIssue("No release zip file found.")


def download(url, download_file):
    with client.stream("GET", url) as response:
        total = int(response.headers["Content-Length"])

        with tqdm(total=total, unit_scale=True, unit_divisor=1024, unit="B") as progress:
            num_bytes_downloaded = response.num_bytes_downloaded
            for chunk in response.iter_bytes():
                download_file.write(chunk)
                progress.update(response.num_bytes_downloaded - num_bytes_downloaded)
                num_bytes_downloaded = response.num_bytes_downloaded


class ZipfileIssue(Exception):
    pass


def download_new():
    print("Fetching Northstar releases")
    release = get_release()
    download_url = get_asset(release["id"])
    print(f"Downloading release: {download_url}")
    dest = Path.cwd()
    with tempfile.NamedTemporaryFile() as download_file:
        download(download_url, download_file)
        print(f"Extracting to {dest}")
        release_zip = zipfile.ZipFile(download_file)
        if config.get("Launcher", "filename") in release_zip.namelist():
            release_zip.extractall(str(Path.cwd()))
            config.set("Version", "semver", release["tag_name"].removeprefix("v"))
        else:
            raise ZipfileIssue("Northstar not found in release zip.")


def main():
    print("Northstar Updater")
    try:
        download_new()
    except NoNewVersion:
        print("No new version found")
    except ReleaseIssue:
        print("Issue finding file in release.")
    except ZipfileIssue:
        print("Northstar launcher not found in release zip.")
    print("Launching Northstar")
    subprocess.run(
        [config.get("Launcher", "filename")]
        + config.get("Launcher", "arguments").split(" ")
        + sys.argv[1:],
        cwd=str(Path.cwd())
        )


main()
with open("updater_config.ini", "w+") as f:
    config.write(f)
