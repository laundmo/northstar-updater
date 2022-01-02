# northstar-updater
Auto-updater for the Northstar Titanfall 2 client

## Installation and Usage

- Download the latest update from https://github.com/laundmo/northstar-updater/releases
- Put the `NorthstarUpdater.exe` into your Titanfall 2 directory next to Titanfall2.exe/NorthstarLauncher.exe
- Run NorthstarUpdater.exe and will update and then start Northstar.

You can run it without Northstar installed, and it will install it.

### Configuration:
After the first launch, it will have generated a `updater_config.ini` which you can edit to allow it to update mods.

Add one of these sections to it. The Github Repository needs to utilise releases for this to work.
```ini
[BetterServerbrowser]
repository = F1F7Y/Better.Serverbrowser
last_update = 0001-01-01T00:00:00
```
|key|explanation|
|-|-|
|repository|The GitHub username and repository of the mod (should contain releases)|
|last_update|by default this is 0, and will be overwritten whenever the updater has completed an update|
|ignore_prerelease (optional, default is true)|true by default, this will prevent the autoupdater from updating to a prerelease version|
|file (optional)|This is pointing to some file in the mod, used to verify the correct zip was downloaded and whether the mod is already installed.|
|install_dir (optional, default is ./R2Northstar/mods)|the directory into which the release will be unpacked. This is obviously different for other non-mod things like the updater itself|
|exclude_files (optional)|A pipe `|` seperated list of files to exclude when extracting the zip. can be useful for config files.|

### Working princple:
The udpater is just a fancy automatic way to download and extract zip archives from github.
It first fetches the releases and tries to determine whether there is a newer version available. Then, it tries to very naively guess which release asset to use, and downloads it. The downloaded zip file will get inspected whetehr it contains `file` to check that it was the correct one. Then, it will extract all fiels except those listed in `exclude_files` into the `install_dir`. The last step is calling NorthstarLauncher which will also be passed every commandline argument given to the updater.
