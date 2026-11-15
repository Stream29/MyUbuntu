# User desktop launchers

Versioned `.desktop` sources are installed to `~/.local/share/applications/`
after review. `Exec` accepts a full executable path or a command found in the
desktop session's `PATH`; it is not a shell command, so `$HOME` is not expanded
as it would be by a shell. See the [Desktop Entry Specification](https://specifications.freedesktop.org/desktop-entry/latest-single/).

`anystorage.desktop` currently targets this host's repository path. Adjust that
path when installing on a device with a different home or checkout location.

`Snipaste.desktop` preserves the existing local AppRun bundle path and is
byte-identical to the deployed launcher. The application bundle, preferences,
and data are not stored in this repository.
