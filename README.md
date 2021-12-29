# northstar-updater
Auto-updater for the Northstar Titanfall 2 client

## Usage

1. compile with nuitka using the `compile.ps1` script or download from releases
2. put the compiled exe into the same folder as Northstar/Titanfall
3. run through the updater. i like to add it as a external game in steam.

It will look for new releases in the main repository here: https://github.com/R2Northstar/Northstar/releases and download it. After finishing it will defer to the NorthstarLauncher.exe, passing along all commandline args.
