"""Non-disruptive unit tests for the hibernate systemd-sleep optimization hook."""

import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = REPO_ROOT / "system" / "usr" / "lib" / "systemd" / "system-sleep" / "60-device-management-hibernate"
TMPFILES_PATH = REPO_ROOT / "system" / "etc" / "tmpfiles.d" / "60-device-management-hibernate.conf"


class HibernateSleepHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.swappiness = self.root / "swappiness"
        self.swappiness.write_text("100\n", encoding="utf-8")

        self.ps_dir = self.root / "power_supply"
        ac = self.ps_dir / "AC"
        ac.mkdir(parents=True)
        (ac / "type").write_text("Mains\n", encoding="utf-8")
        (ac / "online").write_text("0\n", encoding="utf-8")

        usb = self.ps_dir / "ucsi-usb"
        usb.mkdir(parents=True)
        (usb / "type").write_text("USB\n", encoding="utf-8")
        (usb / "online").write_text("1\n", encoding="utf-8")

        self.state_dir = self.root / "state"
        self.profile_file = self.root / "profile"
        self.profile_file.write_text("power-saver\n", encoding="utf-8")
        self.fail_perf = self.root / "fail_perf"

        self.fake_ppctl = self.root / "fake-powerprofilesctl"
        self.fake_ppctl.write_text(
            f"""#!/bin/sh
set -eu
case "${{1:-}}" in
    get)
        cat {str(self.profile_file)!r}
        ;;
    set)
        if [ "${{2:-}}" = "performance" ] && [ -e {str(self.fail_perf)!r} ]; then
            exit 1
        fi
        printf '%s\\n' "$2" > {str(self.profile_file)!r}
        ;;
    *)
        exit 2
        ;;
esac
""",
            encoding="utf-8",
        )
        self.fake_ppctl.chmod(0o755)

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def run_hook(self, phase: str, sleep_type: str, sleep_action: str | None = None) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env.update(
            {
                "HIBERNATE_HOOK_SWAPPINESS_PATH": str(self.swappiness),
                "HIBERNATE_HOOK_POWER_SUPPLY_DIR": str(self.ps_dir),
                "HIBERNATE_HOOK_STATE_DIR": str(self.state_dir),
                "HIBERNATE_HOOK_POWERPROFILESCTL": str(self.fake_ppctl),
            }
        )
        if sleep_action is None:
            env.pop("SYSTEMD_SLEEP_ACTION", None)
        else:
            env["SYSTEMD_SLEEP_ACTION"] = sleep_action
        return subprocess.run(
            ["/bin/sh", str(HOOK_PATH), phase, sleep_type],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_files_syntax_and_tmpfiles_layout(self) -> None:
        syntax = subprocess.run(["/bin/sh", "-n", str(HOOK_PATH)], text=True, capture_output=True)
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        self.assertTrue(os.access(HOOK_PATH, os.X_OK))

        tmpfiles_lines = [
            line.strip()
            for line in TMPFILES_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        self.assertEqual(
            tmpfiles_lines,
            [
                "w /sys/power/image_size - - - - 17179869184",
                "w /sys/power/hibernate_compression_threads - - - - 6",
            ],
        )

    def test_suspend_is_noop(self) -> None:
        self.assertEqual(self.run_hook("pre", "suspend", "suspend").returncode, 0)
        self.assertEqual(self.swappiness.read_text(encoding="utf-8").strip(), "100")
        self.assertEqual(self.profile_file.read_text(encoding="utf-8").strip(), "power-saver")
        self.assertFalse(self.state_dir.exists())

        self.assertEqual(self.run_hook("post", "suspend", "suspend").returncode, 0)
        self.assertEqual(self.swappiness.read_text(encoding="utf-8").strip(), "100")

    def test_hibernate_battery_roundtrip_and_state_cleanup(self) -> None:
        res = self.run_hook("pre", "hibernate", "hibernate")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(self.swappiness.read_text(encoding="utf-8").strip(), "1")
        self.assertEqual(self.profile_file.read_text(encoding="utf-8").strip(), "performance")
        self.assertEqual(stat.S_IMODE((self.state_dir / "state").stat().st_mode), 0o600)

        res = self.run_hook("post", "hibernate", "hibernate")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(self.swappiness.read_text(encoding="utf-8").strip(), "100")
        self.assertEqual(self.profile_file.read_text(encoding="utf-8").strip(), "power-saver")
        self.assertFalse(self.state_dir.exists())

    def test_ac_plugged_while_hibernated_restores_performance(self) -> None:
        self.assertEqual(self.run_hook("pre", "hibernate", "hibernate").returncode, 0)
        (self.ps_dir / "AC" / "online").write_text("1\n", encoding="utf-8")

        self.assertEqual(self.run_hook("post", "hibernate", "hibernate").returncode, 0)
        self.assertEqual(self.swappiness.read_text(encoding="utf-8").strip(), "100")
        self.assertEqual(self.profile_file.read_text(encoding="utf-8").strip(), "performance")

    def test_fallback_to_balanced_and_failed_hibernate_post_restore(self) -> None:
        self.fail_perf.touch()
        self.assertEqual(self.run_hook("pre", "hybrid-sleep").returncode, 0)
        self.assertEqual(self.profile_file.read_text(encoding="utf-8").strip(), "balanced")

        self.assertEqual(
            self.run_hook("post", "suspend-then-hibernate", "suspend-after-failed-hibernate").returncode,
            0,
        )
        self.assertEqual(self.swappiness.read_text(encoding="utf-8").strip(), "100")
        self.assertEqual(self.profile_file.read_text(encoding="utf-8").strip(), "power-saver")
        self.assertFalse(self.state_dir.exists())


if __name__ == "__main__":
    unittest.main()
