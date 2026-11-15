# MyUbuntu

Custom Ubuntu desktop configuration, Sway/GNOME integration helpers, user systemd services, and system tuning reference sources.

- `bin/`: Sway, GNOME/Caffeine lock sync, Kodex notification, tmux, and Wine helper scripts.
- `sway/`, `tmux/`, `shell/`, `gnupg/`, `applications/`: User desktop and shell configuration.
- `systemd/`: User systemd units and `environment.d/` drop-ins.
- `system/`: Reference sources for root-owned `/etc` and `/usr/local/lib` configurations (copy with `root:root`; do not symlink `/etc` into user-writable trees).
- `tests/`: Regression tests for desktop lock, Sway/Fcitx5, and AnyStorage control.
- `docs/`: Additional notes (including [`docs/ime.md`](docs/ime.md) for desktop Fcitx5/Rime/vinput setup).
