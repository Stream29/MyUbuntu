"""Non-disruptive validation tests for recorded GNOME settings and extensions."""

import ast
import configparser
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GNOME_DIR = REPO_ROOT / "gnome"
DCONF_INI = GNOME_DIR / "dconf-settings.ini"
EXTENSIONS_JSON = GNOME_DIR / "extensions.json"
APPINDICATORS_PATCH = GNOME_DIR / "patches" / "ubuntu-appindicators.patch"
DING_PATCH = GNOME_DIR / "patches" / "ding.patch"

FORBIDDEN_DCONF_SECTIONS = (
    "org/gnome/nm-applet",
    "org/gnome/portal/filechooser",
    "org/gnome/settings-daemon/plugins/color",
    "org/gnome/desktop/remote-desktop",
    "org/virt-manager",
    "system/proxy",
)


class GnomeConfigTests(unittest.TestCase):
    def test_dconf_settings_parse_and_exclude_sensitive_or_dynamic_keys(self) -> None:
        raw = DCONF_INI.read_text(encoding="utf-8")
        parser = configparser.ConfigParser(interpolation=None)
        parser.optionxform = str
        parser.read_string(raw)

        for section in parser.sections():
            for forbidden in FORBIDDEN_DCONF_SECTIONS:
                self.assertFalse(
                    section.startswith(forbidden),
                    f"Sensitive/ephemeral section {section!r} must not be stored",
                )

        self.assertEqual(
            parser["org/gnome/desktop/wm/keybindings"]["toggle-fullscreen"],
            "['<Super>f']",
        )
        self.assertNotIn("lock-enabled", parser["org/gnome/desktop/screensaver"])
        self.assertNotIn("user-enabled", parser["org/gnome/shell/extensions/caffeine"])

    @unittest.skipUnless(
        shutil.which("dbus-run-session") and shutil.which("dconf"),
        "dbus-run-session and dconf are required for isolated dconf load check",
    )
    def test_dconf_settings_load_cleanly_in_isolated_session(self) -> None:
        raw = DCONF_INI.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["HOME"] = tmp
            env["XDG_CONFIG_HOME"] = f"{tmp}/config"
            env["XDG_DATA_HOME"] = f"{tmp}/data"
            env["XDG_RUNTIME_DIR"] = f"{tmp}/run"
            os.makedirs(env["XDG_RUNTIME_DIR"], mode=0o700)

            proc = subprocess.run(
                [
                    "dbus-run-session",
                    "--",
                    "bash",
                    "-c",
                    "dconf load / && dconf read /org/gnome/desktop/wm/keybindings/toggle-fullscreen",
                ],
                input=raw,
                text=True,
                capture_output=True,
                env=env,
                check=True,
            )
            self.assertEqual(proc.stdout.strip(), "['<Super>f']")

    def test_extensions_manifest_matches_dconf_lists(self) -> None:
        manifest = json.loads(EXTENSIONS_JSON.read_text(encoding="utf-8"))
        entries = manifest["extensions"]
        uuids = [item["uuid"] for item in entries]
        self.assertEqual(len(uuids), len(set(uuids)), "Duplicate extension UUIDs found")

        for item in entries:
            self.assertIn(item["scope"], {"user", "system"})
            self.assertIsInstance(item["enabled"], bool)
            self.assertIsInstance(item["session_mode"], bool)

        parser = configparser.ConfigParser(interpolation=None)
        parser.optionxform = str
        parser.read_string(DCONF_INI.read_text(encoding="utf-8"))
        shell_sec = parser["org/gnome/shell"]
        dconf_enabled = set(ast.literal_eval(shell_sec["enabled-extensions"]))
        dconf_disabled = set(ast.literal_eval(shell_sec["disabled-extensions"]))

        stale = set(manifest.get("stale_dconf_enabled_extensions", []))
        manifest_enabled = {item["uuid"] for item in entries if item["enabled"]}
        manifest_disabled = {item["uuid"] for item in entries if not item["enabled"]}

        # snapd-prompting@canonical.com is enabled via ubuntu.json session mode rather than dconf enabled-extensions.
        self.assertTrue(
            dconf_enabled.issubset(manifest_enabled | stale),
            f"Unrecorded enabled extensions: {dconf_enabled - (manifest_enabled | stale)}",
        )
        self.assertEqual(dconf_disabled, manifest_disabled)

    def test_ubuntu_appindicators_patch_is_well_formed(self) -> None:
        patch_text = APPINDICATORS_PATCH.read_text(encoding="utf-8")
        self.assertIn("--- a/trayIconsManager.js", patch_text)
        self.assertIn("+++ b/trayIconsManager.js", patch_text)
        self.assertIn("+            Util.Logger.warn(", patch_text)
        self.assertIn("--- a/appIndicator.js", patch_text)
        self.assertIn("+++ b/appIndicator.js", patch_text)
        self.assertIn("+        return !!this._proxy?.g_name_owner;", patch_text)

    def test_ding_patch_is_well_formed(self) -> None:
        patch_text = DING_PATCH.read_text(encoding="utf-8")
        self.assertIn("--- a/extension.js", patch_text)
        self.assertIn("+++ b/extension.js", patch_text)
        self.assertIn("+    beginShutdown() {", patch_text)
        self.assertIn("+        if (!this.data.isEnabled || this.data.isShuttingDown)", patch_text)
        self.assertIn("+        if (this.data.isEnabled && !this.data.isShuttingDown) {", patch_text)
        self.assertIn("+                'SessionOver',", patch_text)
        self.assertIn("+            else if (obj.get_if_signaled() && reloadTime < 500)", patch_text)
