"""Safety tests for the external persistent-cache controller."""
import importlib.machinery
import importlib.util
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "bin/anystoragectl"
loader = importlib.machinery.SourceFileLoader("external_control", str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
control = importlib.util.module_from_spec(spec)
loader.exec_module(control)


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.disk = Path(self.temp.name)
        self.cache_root = self.disk / ".rclone-cache"
        self.cache = self.cache_root / "vfs"
        self.cache.mkdir(parents=True)
        self.entry = self.disk / "AnyStorage"
        self.entry.mkdir()
        self.adult = self.disk / "adult"
        self.adult.mkdir()
        (self.adult / "synthetic").write_bytes(b"leave unchanged")
        for name, value in (
            ("DISK", self.disk),
            ("CACHE_ROOT", self.cache_root),
            ("CACHE", self.cache),
            ("ENTRY", self.entry),
        ):
            p = patch.object(control, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.table = {
            str(self.disk): {
                "uuid": control.UUID,
                "fstype": "ext4",
            }
        }
        p = patch.object(control, "mounts", lambda: self.table)
        p.start()
        self.addCleanup(p.stop)
        p = patch.object(
            control, "service_info",
            return_value={"active": "inactive", "sub": "dead", "pid": "0", "exit": "0"},
        )
        self.state = p.start()
        self.addCleanup(p.stop)

    def test_wrong_disk_rejected(self):
        self.table[str(self.disk)]["uuid"] = "another-disk"
        with self.assertRaises(control.ControlError):
            control.ensure_cache_paths(self.table)

    def test_foreign_entry_rejected(self):
        self.table[str(self.entry)] = {
            "source": "foreign:bucket",
            "fstype": "fuse.rclone",
        }
        with self.assertRaises(control.ControlError):
            control.vfs_info(self.table)

    def test_foreign_filesystem_rejected(self):
        self.table[str(self.entry)] = {
            "source": "anystorage:anystorage",
            "fstype": "fuse.ossfs2",
        }
        with self.assertRaises(control.ControlError):
            control.vfs_info(self.table)

    def test_existing_mount_is_idempotent(self):
        self.table[str(self.entry)] = {
            "source": "anystorage{hash}:anystorage",
            "fstype": "fuse.rclone",
        }
        with patch.object(control, "authorize") as auth:
            control.mount_vfs()
        auth.assert_not_called()

    def test_active_service_rejects_prepare(self):
        self.state.return_value = {
            "active": "active", "sub": "running", "pid": "1", "exit": "0",
        }
        with self.assertRaises(control.ControlError):
            control.mount_vfs()

    def test_nested_mount_rejects_prepare(self):
        self.table[str(self.cache / "nested")] = {"fstype": "ext4"}
        with self.assertRaises(control.ControlError):
            control.ensure_cache_paths(self.table)

    def test_cache_symlink_rejected(self):
        shutil.rmtree(self.cache_root)
        self.cache_root.symlink_to(self.adult, target_is_directory=True)
        with self.assertRaises(control.ControlError):
            control.ensure_cache_paths(self.table)

    def test_busy_unmount_does_not_stop_service(self):
        self.table[str(self.entry)] = {
            "source": "anystorage{hash}:anystorage",
            "fstype": "fuse.rclone",
        }
        with patch.object(control, "fuser_has_process", return_value=True), \
                patch.object(control, "authorize") as auth:
            with self.assertRaises(control.ControlError):
                control.unmount_vfs()
        auth.assert_not_called()

    def test_privileged_action_is_limited_to_new_cache_unit(self):
        with self.assertRaises(control.ControlError):
            control.authorize("restart")
        with patch.object(control.subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess([], 0)
            control.authorize("stop")
            run.assert_called_once_with([
                "pkexec", "/usr/bin/systemctl", "--no-pager",
                "stop", control.MOUNT_UNIT,
            ], timeout=120)


if __name__ == "__main__":
    unittest.main()
