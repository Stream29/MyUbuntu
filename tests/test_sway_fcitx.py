import os
import signal
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SWAY_FCITX = REPO_ROOT / "bin" / "sway-fcitx"


def _wait_until(predicate, timeout: float = 5.0, interval: float = 0.05) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(interval)
    raise AssertionError("condition not met before timeout")


def test_sway_fcitx_supervises_and_cleans_up_launcher(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(mode=0o700)
    active_tty = tmp_path / "active_tty"
    active_tty.write_text("tty3\n", encoding="utf-8")
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()

    launcher_log = tmp_path / "launcher.log"
    launcher_pid_file = tmp_path / "launcher.pid"
    launcher_bin = tmp_path / "fake-launcher"
    launcher_bin.write_text(
        f"""#!/usr/bin/env bash
set -eu
echo "$$:${{WAYLAND_DISPLAY:-}}" >> {str(launcher_log)!r}
echo "$$" > {str(launcher_pid_file)!r}
trap 'exit 0' TERM INT
while true; do
    sleep 0.1
done
""",
        encoding="utf-8",
    )
    launcher_bin.chmod(0o755)

    swaymsg_bin = tmp_path / "fake-swaymsg"
    swaymsg_bin.write_text(
        """#!/usr/bin/env bash
trap 'exit 0' TERM INT
while true; do
    sleep 0.1
done
""",
        encoding="utf-8",
    )
    swaymsg_bin.chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "XDG_RUNTIME_DIR": str(runtime_dir),
            "WAYLAND_DISPLAY": "wayland-99",
            "DISPLAY": ":99",
            "SWAYSOCK": str(tmp_path / "sway.sock"),
            "SWAY_FCITX_ACTIVE_TTY_PATH": str(active_tty),
            "SWAY_FCITX_SESSIONS_DIR": str(sessions_dir),
            "SWAY_FCITX_ACTIVE_DISPLAY_ENV_FILE": str(tmp_path / "active-display.env"),
            "SWAY_FCITX_LAUNCHER_BIN": str(launcher_bin),
            "SWAY_FCITX_LAUNCHER_RETRY_SECONDS": "0.1",
            "SWAY_FCITX_SWAYMSG_BIN": str(swaymsg_bin),
        }
    )

    proc = subprocess.Popen(["bash", str(SWAY_FCITX)], env=env)
    try:
        _wait_until(
            lambda: launcher_log.exists()
            and len(launcher_log.read_text(encoding="utf-8").splitlines()) >= 1
        )
        first_line = launcher_log.read_text(encoding="utf-8").splitlines()[0]
        first_pid_str, first_display = first_line.split(":", 1)
        first_pid = int(first_pid_str)
        assert first_display == "wayland-99"

        # Simulate launcher exiting (e.g. fcitx5 restart or crash); supervisor must restart it.
        os.kill(first_pid, signal.SIGTERM)
        _wait_until(
            lambda: len(launcher_log.read_text(encoding="utf-8").splitlines()) >= 2
        )
        second_line = launcher_log.read_text(encoding="utf-8").splitlines()[1]
        second_pid_str, second_display = second_line.split(":", 1)
        second_pid = int(second_pid_str)
        assert second_pid != first_pid
        assert second_display == "wayland-99"

        # Stopping sway-fcitx must also terminate the supervised child launcher.
        proc.terminate()
        rc = proc.wait(timeout=5)
        assert rc in (0, -signal.SIGTERM, 143)

        _wait_until(lambda: not _pid_alive(second_pid))
        assert not (runtime_dir / "sway-fcitx").exists()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True
