# MyUbuntu

Custom Ubuntu desktop configuration, Sway/GNOME integration helpers, user systemd services, and system tuning reference sources.

- `home/`: Mirrors `$HOME` (`~/.config/sway`, `~/.config/tmux`, `~/.config/systemd/user`, `~/.config/environment.d`, `~/.local/share/applications`, `~/.gnupg`).
- `system/`: Mirrors `/` (`system/etc/...` and `system/usr/...`) as reference sources for root-owned files (copy with `root:root`; do not symlink `/etc` into user-writable trees).
- `gnome/`: Declarative GNOME [`dconf-settings.ini`](gnome/dconf-settings.ini), extension inventory [`extensions.json`](gnome/extensions.json), and system extension patches under `gnome/patches/`.
- `bin/`: Sway, GNOME/Caffeine lock sync, Kodex notification, tmux, Wine, AnyStorage, and Rime OSS helper scripts.
- `shell/`: Shell integration (`path.sh`) exposing `bin/` directories and syncing `tmux` display env.
- `tests/`: Regression tests for desktop lock, Sway/Fcitx5, AnyStorage control, and GNOME configuration snapshots.
- `docs/`: Additional notes (including [`docs/gnome.md`](docs/gnome.md) for GNOME settings/extensions and [`docs/ime.md`](docs/ime.md) for desktop Fcitx5/Rime/vinput setup).
