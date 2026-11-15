# System-level configuration sources

Files here mirror selected root-owned system paths. Review and validate each
source, back up the installed file, then install a copy with the required
root ownership and mode. Never symlink privileged files into this user-writable
repository.

`usr/sbin/mount.anystorage-ossfs2` is the fstab helper for the AnyStorage
GNOME volume. It delegates to the repository's user-level `bin/anystorage-control`.

`fstab/anystorage.entry` records the specific AnyStorage `/etc/fstab` line as
a reference fragment. Linux does not automatically include this repository
path; do not replace `/etc/fstab` wholesale when applying it.

`systemd/zram-generator.conf` mirrors `/etc/systemd/zram-generator.conf` (`zstd`
swap on `/dev/zram0` at priority `100`, capped at `min(ram, 32768)` virtual size
and `ram / 2` resident limit).

`sysctl.d/99-desktop-memory.conf` mirrors `/etc/sysctl.d/99-desktop-memory.conf`
(`vm.swappiness=100`, `vm.page-cluster=0`, `vm.watermark_boost_factor=0`,
`vm.watermark_scale_factor=125`), optimizing high-memory allocations and single-page
ZRAM I/O on Lunar Lake LPDDR5X.

`systemd/journald.conf.d/max-size.conf` mirrors
`/etc/systemd/journald.conf.d/max-size.conf` (`SystemMaxUse=1G`), restricting total
persistent systemd-journald disk consumption.

`systemd/system/-.slice.d/50-oomd-swap.conf` and
`systemd/system/user-.slice.d/50-oomd-memory-pressure.conf` mirror the root-owned
`/etc/systemd/system/` drop-ins that enable `systemd-oomd` system-wide swap
monitoring (`ManagedOOMSwap=kill` on `-.slice`) and per-user slice memory
pressure monitoring (`ManagedOOMMemoryPressure=kill`, `60%` limit on
`user-.slice`, covering SSH `session-*.scope` units outside `user@.service`).

`usr/local/lib/gdm-filter-non-gdm-sessions.c`,
`usr/local/lib/gdm-filter-non-gdm-sessions.map`, and
`systemd/system/gdm.service.d/50-filter-non-gdm-sessions.conf` build and load
`/usr/local/lib/gdm-filter-non-gdm-sessions.so` into `gdm.service` (`root:root`,
mode `0644`). The library strips itself from `LD_PRELOAD` in its constructor so
child processes do not inherit it, and intercepts `sd_session_get_type` inside
`gdm3` so non-GDM sessions (`SERVICE != gdm*`, such as TTY-launched Sway with
`SERVICE=login`) report `type="tty"` and do not shadow GDM's own display session
during `OpenReauthenticationChannel`.
