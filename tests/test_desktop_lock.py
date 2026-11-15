"""Non-disruptive regression tests: fake lockers and fake GNOME/logind only."""

import asyncio
import os
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SWAY = runpy.run_path(str(ROOT / "bin/sway-session-lock"), run_name="test_sway")
GNOME_PATH = ROOT / "bin/caffeine-lock-sync-candidate"
if not GNOME_PATH.exists():
    GNOME_PATH = ROOT / "bin/caffeine-lock-sync"
GNOME = runpy.run_path(str(GNOME_PATH), run_name="test_gnome")
DesktopPolicy = GNOME["DesktopPolicy"]
GLib = GNOME["GLib"]


class LockBrokerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.brokers = []

    async def asyncTearDown(self):
        for broker in self.brokers:
            if broker.process and broker.process.returncode is None:
                # These are test-owned Python processes, never real swaylock.
                broker.process.terminate()
                await broker.process.wait()

    def broker(self, code, timeout=1):
        broker = SWAY["LockBroker"]([sys.executable, "-c", code], timeout)
        self.brokers.append(broker)
        return broker

    async def test_concurrent_requests_share_confirmed_locker(self):
        broker = self.broker(
            "import os,sys,time; time.sleep(.05); "
            "os.write(int(sys.argv[-1]), b'\\n'); time.sleep(30)"
        )
        await asyncio.gather(*(broker.lock() for _ in range(5)))
        pid = broker.process.pid
        self.assertTrue(broker.ready)
        await broker.lock()
        self.assertEqual(pid, broker.process.pid)

    async def test_exit_without_readiness_is_not_success(self):
        broker = self.broker("pass")
        with self.assertRaises(RuntimeError):
            await broker.lock()
        self.assertFalse(broker.ready)

    async def test_timeout_never_reports_locked_or_kills_locker(self):
        broker = self.broker("import time; time.sleep(30)", timeout=.05)
        with self.assertRaises(asyncio.TimeoutError):
            await broker.lock()
        self.assertFalse(broker.ready)
        self.assertIsNone(broker.process.returncode)
        with self.assertRaises(RuntimeError):
            await broker.lock()

    async def test_new_lock_after_previous_locker_exits(self):
        broker = self.broker(
            "import os,sys,time; os.write(int(sys.argv[-1]), b'\\n'); time.sleep(30)"
        )
        await broker.lock()
        first_pid = broker.process.pid
        broker.process.terminate()
        await broker.process.wait()
        await broker.lock()
        self.assertNotEqual(first_pid, broker.process.pid)


class FakePolicy(DesktopPolicy):
    def __init__(self):
        self.caffeine = False
        self.alive = True
        self.props = {"LockedHint": False}
        self.block_fd = self.delay_fd = None
        self.sleep_pending = False
        self.sleep_session = None
        self.refresh_queued = False
        self.closed = False
        self.last_state = None
        self.enabled = True
        self.requested = []
        self.acquired = []
        self.session = self

    def gnome_session(self):
        return ("/gnome-only", self.props) if self.alive else (None, {})

    def owns(self, name):
        return self.alive

    def caffeine_active(self):
        return self.caffeine

    def properties(self, path):
        assert path == "/gnome-only"
        return self.props

    def set_lock_enabled(self, enabled):
        self.enabled = enabled

    def inhibit(self, mode):
        self.acquired.append(mode)
        return os.open("/dev/null", os.O_RDONLY)

    def call(self, *args):
        self.requested.append(args)


class GnomePolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = FakePolicy()

    def tearDown(self):
        self.policy.release("block_fd")
        self.policy.release("delay_fd")

    def test_caffeine_is_sleep_only_and_no_duplicate_fds(self):
        p = self.policy
        p.caffeine = True
        p.refresh()
        self.assertFalse(p.enabled)
        block, delay = p.block_fd, p.delay_fd
        p.refresh()
        self.assertEqual((p.block_fd, p.delay_fd), (block, delay))
        self.assertEqual(p.acquired, ["block", "delay"])
        p.caffeine = False
        p.refresh()
        self.assertTrue(p.enabled)
        self.assertIsNone(p.block_fd)
        self.assertEqual(p.delay_fd, delay)

    def test_locked_session_keeps_crash_relock_enabled(self):
        p = self.policy
        p.caffeine = True
        p.props["LockedHint"] = True
        p.refresh()
        self.assertTrue(p.enabled)
        self.assertEqual(p.requested, [])

    def test_gnome_exit_releases_all_inhibitors_ignoring_stale_caffeine(self):
        p = self.policy
        p.caffeine = True
        p.refresh()
        p.alive = False
        p.refresh()
        self.assertTrue(p.enabled)
        self.assertIsNone(p.block_fd)
        self.assertIsNone(p.delay_fd)

    def test_sleep_relies_on_native_gnome_and_waits_for_locked_hint(self):
        p = self.policy
        p.caffeine = True
        p.refresh()
        with patch.object(GLib, "timeout_add"):
            p.sleep_changed(None, None, None, None, None, GLib.Variant("(b)", (True,)), None)
        self.assertTrue(p.enabled)
        self.assertEqual(p.requested, [])
        self.assertIsNotNone(p.delay_fd)
        self.assertTrue(p.wait_for_lock())
        p.props["LockedHint"] = True
        self.assertFalse(p.wait_for_lock())
        self.assertIsNone(p.delay_fd)
        p.sleep_changed(None, None, None, None, None, GLib.Variant("(b)", (False,)), None)
        self.assertIsNotNone(p.delay_fd)
        self.assertTrue(p.enabled)

    def test_already_locked_sleep_sends_no_lock_request(self):
        p = self.policy
        p.refresh()
        p.props["LockedHint"] = True
        p.sleep_changed(None, None, None, None, None, GLib.Variant("(b)", (True,)), None)
        self.assertEqual(p.requested, [])
        self.assertIsNone(p.delay_fd)

    def test_failed_refresh_releases_caffeine_and_restores_protection(self):
        p = self.policy
        p.caffeine = True
        p.refresh()
        with patch.object(p, "gnome_session", side_effect=RuntimeError("bus disappeared")):
            with self.assertLogs("caffeine-lock-sync", level="ERROR"):
                p.refresh()
        self.assertTrue(p.enabled)
        self.assertIsNone(p.block_fd)

    def test_sleep_timeout_is_not_confirmed_and_keeps_delay(self):
        p = self.policy
        p.refresh()
        with patch.object(GLib, "timeout_add"):
            p.sleep_changed(None, None, None, None, None, GLib.Variant("(b)", (True,)), None)
        p.deadline = 0
        with self.assertLogs("caffeine-lock-sync", level="ERROR"):
            self.assertFalse(p.wait_for_lock())
        self.assertIsNotNone(p.delay_fd)
        self.assertTrue(p.enabled)

    def test_gnome_session_recognizes_gdm_fingerprint_and_ignores_greeter(self):
        p = self.policy
        p.system = object()
        uid = os.getuid()
        sessions = [
            ("1", uid, "stream", "seat0", "/s/greeter"),
            ("2", uid, "stream", "seat0", "/s/sway"),
            ("3", uid, "stream", "seat0", "/s/gnome"),
        ]
        props_by_path = {
            "/s/greeter": {"Service": "gdm-launch-environment", "Type": "wayland", "Remote": False, "Class": "greeter"},
            "/s/sway": {"Service": "login", "Type": "wayland", "Remote": False, "Class": "user"},
            "/s/gnome": {"Service": "gdm-fingerprint", "Type": "wayland", "Remote": False, "Class": "user"},
        }
        with patch.object(p, "call", return_value=(sessions,)), \
             patch.object(p, "properties", side_effect=props_by_path.__getitem__):
            path, props = DesktopPolicy.gnome_session(p)
        self.assertEqual(path, "/s/gnome")
        self.assertEqual(props["Service"], "gdm-fingerprint")


if __name__ == "__main__":
    unittest.main()
