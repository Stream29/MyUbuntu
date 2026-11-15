# Shell integration

`path.sh` puts this repository's `bin/` first when that directory exists, then
removes repeated `PATH` entries while preserving the first occurrence of each
directory. In interactive Bash shells inside `tmux`, it also syncs
`WAYLAND_DISPLAY`, `DISPLAY`, and `SWAYSOCK` from
`${XDG_RUNTIME_DIR}/active-display.env` (maintained by [`../bin/sway-fcitx`](../bin/sway-fcitx))
before commands and prompts without altering `$?` or `$_`. The user's
`~/.profile` and `~/.bashrc` source it for login and interactive Bash shells.
