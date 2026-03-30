import tempfile
import unittest
from pathlib import Path

from .support import (
    _DECKYZONE_BASE_PROFILE,
    _DECKYZONE_GREEN_TINT_PROFILE,
    _VALID_ZOTAC_SYSTEM_PROFILE,
    _write_gamescope_display_assets,
    main,
)


class GamescopeDisplayProfilesTests(unittest.TestCase):
    def test_get_state_reports_builtin_profile_when_system_script_is_valid(self):
        with tempfile.TemporaryDirectory() as temp_home, tempfile.TemporaryDirectory() as temp_root:
            system_profile_path = (
                Path(temp_root)
                / "usr"
                / "share"
                / "gamescope"
                / "scripts"
                / "00-gamescope"
                / "displays"
                / "zotac.zone.oled.lua"
            )
            system_profile_path.parent.mkdir(parents=True, exist_ok=True)
            system_profile_path.write_text(_VALID_ZOTAC_SYSTEM_PROFILE, encoding="utf-8")

            helper = main.gamescope_display_profiles.GamescopeDisplayProfiles(
                user_home=temp_home,
                plugin_dir=temp_root,
                system_profile_paths=[system_profile_path],
            )

            settings = helper.get_state()

            self.assertTrue(settings["gamescopeZotacProfileBuiltIn"])
            self.assertFalse(settings["gamescopeZotacProfileInstalled"])
            self.assertFalse(settings["gamescopeGreenTintFixEnabled"])
            self.assertEqual(
                settings["gamescopeZotacProfileTargetPath"],
                str(Path(temp_home) / ".config" / "gamescope" / "scripts" / "zotac.zone.oled.lua"),
            )
            self.assertEqual(settings["gamescopeZotacProfileVerificationState"], "absent")

    def test_set_zotac_profile_enabled_installs_and_removes_managed_base_profile(self):
        with tempfile.TemporaryDirectory() as temp_home, tempfile.TemporaryDirectory() as temp_plugin_dir:
            _write_gamescope_display_assets(Path(temp_plugin_dir))
            helper = main.gamescope_display_profiles.GamescopeDisplayProfiles(
                user_home=temp_home,
                plugin_dir=temp_plugin_dir,
                system_profile_paths=[],
            )
            managed_base_path = (
                Path(temp_home)
                / ".config"
                / "gamescope"
                / "scripts"
                / "zotac.zone.oled.lua"
            )

            enabled_settings = helper.set_zotac_profile_enabled(True)

            self.assertTrue(managed_base_path.exists())
            self.assertEqual(managed_base_path.read_text(encoding="utf-8"), _DECKYZONE_BASE_PROFILE)
            self.assertFalse(enabled_settings["gamescopeZotacProfileBuiltIn"])
            self.assertTrue(enabled_settings["gamescopeZotacProfileInstalled"])
            self.assertFalse(enabled_settings["gamescopeGreenTintFixEnabled"])
            self.assertEqual(enabled_settings["gamescopeZotacProfileVerificationState"], "base")

            disabled_settings = helper.set_zotac_profile_enabled(False)

            self.assertFalse(managed_base_path.exists())
            self.assertFalse(disabled_settings["gamescopeZotacProfileInstalled"])
            self.assertEqual(disabled_settings["gamescopeZotacProfileVerificationState"], "absent")

    def test_set_green_tint_fix_enabled_rejects_when_base_profile_is_unavailable(self):
        with tempfile.TemporaryDirectory() as temp_home, tempfile.TemporaryDirectory() as temp_plugin_dir:
            _write_gamescope_display_assets(Path(temp_plugin_dir))
            helper = main.gamescope_display_profiles.GamescopeDisplayProfiles(
                user_home=temp_home,
                plugin_dir=temp_plugin_dir,
                system_profile_paths=[],
            )
            managed_profile_path = (
                Path(temp_home)
                / ".config"
                / "gamescope"
                / "scripts"
                / "zotac.zone.oled.lua"
            )

            settings = helper.set_green_tint_fix_enabled(True)

            self.assertFalse(managed_profile_path.exists())
            self.assertFalse(settings["gamescopeZotacProfileBuiltIn"])
            self.assertFalse(settings["gamescopeZotacProfileInstalled"])
            self.assertFalse(settings["gamescopeGreenTintFixEnabled"])
            self.assertEqual(settings["gamescopeZotacProfileVerificationState"], "absent")

    def test_set_green_tint_fix_enabled_writes_corrected_profile_when_builtin_exists(self):
        with (
            tempfile.TemporaryDirectory() as temp_home,
            tempfile.TemporaryDirectory() as temp_plugin_dir,
            tempfile.TemporaryDirectory() as temp_root,
        ):
            _write_gamescope_display_assets(Path(temp_plugin_dir))
            system_profile_path = (
                Path(temp_root)
                / "usr"
                / "share"
                / "gamescope"
                / "scripts"
                / "00-gamescope"
                / "displays"
                / "zotac.zone.oled.lua"
            )
            system_profile_path.parent.mkdir(parents=True, exist_ok=True)
            system_profile_path.write_text(_VALID_ZOTAC_SYSTEM_PROFILE, encoding="utf-8")
            helper = main.gamescope_display_profiles.GamescopeDisplayProfiles(
                user_home=temp_home,
                plugin_dir=temp_plugin_dir,
                system_profile_paths=[system_profile_path],
            )
            managed_profile_path = (
                Path(temp_home)
                / ".config"
                / "gamescope"
                / "scripts"
                / "zotac.zone.oled.lua"
            )

            settings = helper.set_green_tint_fix_enabled(True)

            self.assertTrue(managed_profile_path.exists())
            self.assertEqual(managed_profile_path.read_text(encoding="utf-8"), _DECKYZONE_GREEN_TINT_PROFILE)
            self.assertTrue(settings["gamescopeZotacProfileBuiltIn"])
            self.assertTrue(settings["gamescopeZotacProfileInstalled"])
            self.assertTrue(settings["gamescopeGreenTintFixEnabled"])
            self.assertEqual(settings["gamescopeZotacProfileVerificationState"], "green")

            disabled_settings = helper.set_green_tint_fix_enabled(False)

            self.assertFalse(managed_profile_path.exists())
            self.assertFalse(disabled_settings["gamescopeZotacProfileInstalled"])
            self.assertFalse(disabled_settings["gamescopeGreenTintFixEnabled"])
            self.assertEqual(disabled_settings["gamescopeZotacProfileVerificationState"], "absent")

    def test_set_green_tint_fix_enabled_rewrites_same_file_between_variants(self):
        with tempfile.TemporaryDirectory() as temp_home, tempfile.TemporaryDirectory() as temp_plugin_dir:
            _write_gamescope_display_assets(Path(temp_plugin_dir))
            helper = main.gamescope_display_profiles.GamescopeDisplayProfiles(
                user_home=temp_home,
                plugin_dir=temp_plugin_dir,
                system_profile_paths=[],
            )
            managed_profile_path = (
                Path(temp_home)
                / ".config"
                / "gamescope"
                / "scripts"
                / "zotac.zone.oled.lua"
            )

            helper.set_zotac_profile_enabled(True)
            green_settings = helper.set_green_tint_fix_enabled(True)

            self.assertTrue(managed_profile_path.exists())
            self.assertEqual(managed_profile_path.read_text(encoding="utf-8"), _DECKYZONE_GREEN_TINT_PROFILE)
            self.assertTrue(green_settings["gamescopeZotacProfileInstalled"])
            self.assertTrue(green_settings["gamescopeGreenTintFixEnabled"])
            self.assertEqual(green_settings["gamescopeZotacProfileVerificationState"], "green")

            base_settings = helper.set_green_tint_fix_enabled(False)

            self.assertTrue(managed_profile_path.exists())
            self.assertEqual(managed_profile_path.read_text(encoding="utf-8"), _DECKYZONE_BASE_PROFILE)
            self.assertTrue(base_settings["gamescopeZotacProfileInstalled"])
            self.assertFalse(base_settings["gamescopeGreenTintFixEnabled"])
            self.assertEqual(base_settings["gamescopeZotacProfileVerificationState"], "base")

    def test_disabling_managed_zotac_profile_removes_single_file_and_clears_green_state(self):
        with tempfile.TemporaryDirectory() as temp_home, tempfile.TemporaryDirectory() as temp_plugin_dir:
            _write_gamescope_display_assets(Path(temp_plugin_dir))
            helper = main.gamescope_display_profiles.GamescopeDisplayProfiles(
                user_home=temp_home,
                plugin_dir=temp_plugin_dir,
                system_profile_paths=[],
            )
            managed_profile_path = (
                Path(temp_home)
                / ".config"
                / "gamescope"
                / "scripts"
                / "zotac.zone.oled.lua"
            )

            helper.set_zotac_profile_enabled(True)
            helper.set_green_tint_fix_enabled(True)
            disabled_settings = helper.set_zotac_profile_enabled(False)

            self.assertFalse(managed_profile_path.exists())
            self.assertFalse(disabled_settings["gamescopeZotacProfileInstalled"])
            self.assertFalse(disabled_settings["gamescopeGreenTintFixEnabled"])
            self.assertEqual(disabled_settings["gamescopeZotacProfileVerificationState"], "absent")

    def test_get_state_reports_unexpected_managed_profile_content(self):
        with tempfile.TemporaryDirectory() as temp_home, tempfile.TemporaryDirectory() as temp_plugin_dir:
            _write_gamescope_display_assets(Path(temp_plugin_dir))
            managed_profile_path = (
                Path(temp_home)
                / ".config"
                / "gamescope"
                / "scripts"
                / "zotac.zone.oled.lua"
            )
            managed_profile_path.parent.mkdir(parents=True, exist_ok=True)
            managed_profile_path.write_text("-- unexpected", encoding="utf-8")

            helper = main.gamescope_display_profiles.GamescopeDisplayProfiles(
                user_home=temp_home,
                plugin_dir=temp_plugin_dir,
                system_profile_paths=[],
            )

            settings = helper.get_state()

            self.assertTrue(settings["gamescopeZotacProfileInstalled"])
            self.assertFalse(settings["gamescopeGreenTintFixEnabled"])
            self.assertEqual(settings["gamescopeZotacProfileVerificationState"], "unexpected")

    def test_get_state_migrates_legacy_deckyzone_paths_to_single_managed_file(self):
        with tempfile.TemporaryDirectory() as temp_home, tempfile.TemporaryDirectory() as temp_plugin_dir:
            _write_gamescope_display_assets(Path(temp_plugin_dir))
            legacy_green_path = (
                Path(temp_home)
                / ".config"
                / "gamescope"
                / "scripts"
                / "90-deckyzone"
                / "displays"
                / "20-zotac-zone-green-tint.lua"
            )
            legacy_green_path.parent.mkdir(parents=True, exist_ok=True)
            legacy_green_path.write_text(_DECKYZONE_GREEN_TINT_PROFILE, encoding="utf-8")

            helper = main.gamescope_display_profiles.GamescopeDisplayProfiles(
                user_home=temp_home,
                plugin_dir=temp_plugin_dir,
                system_profile_paths=[],
            )
            settings = helper.get_state()
            managed_profile_path = (
                Path(temp_home)
                / ".config"
                / "gamescope"
                / "scripts"
                / "zotac.zone.oled.lua"
            )

            self.assertTrue(managed_profile_path.exists())
            self.assertEqual(managed_profile_path.read_text(encoding="utf-8"), _DECKYZONE_GREEN_TINT_PROFILE)
            self.assertFalse(legacy_green_path.exists())
            self.assertFalse(legacy_green_path.parent.exists())
            self.assertTrue(settings["gamescopeZotacProfileInstalled"])
            self.assertTrue(settings["gamescopeGreenTintFixEnabled"])
            self.assertEqual(settings["gamescopeZotacProfileVerificationState"], "green")

    def test_get_state_returns_error_when_legacy_cleanup_raises_permission_error(self):
        with tempfile.TemporaryDirectory() as temp_home, tempfile.TemporaryDirectory() as temp_plugin_dir:
            _write_gamescope_display_assets(Path(temp_plugin_dir))
            helper = main.gamescope_display_profiles.GamescopeDisplayProfiles(
                user_home=temp_home,
                plugin_dir=temp_plugin_dir,
                system_profile_paths=[],
            )
            helper._migrate_legacy_managed_profiles = lambda: (_ for _ in ()).throw(
                PermissionError("denied")
            )

            settings = helper.get_state()

            self.assertFalse(settings["gamescopeZotacProfileBuiltIn"])
            self.assertFalse(settings["gamescopeZotacProfileInstalled"])
            self.assertFalse(settings["gamescopeGreenTintFixEnabled"])
            self.assertEqual(
                settings["gamescopeZotacProfileTargetPath"],
                str(Path(temp_home) / ".config" / "gamescope" / "scripts" / "zotac.zone.oled.lua"),
            )
            self.assertEqual(settings["gamescopeZotacProfileVerificationState"], "error")

    def test_cleanup_managed_files_removes_managed_and_legacy_profiles_only(self):
        with tempfile.TemporaryDirectory() as temp_home, tempfile.TemporaryDirectory() as temp_plugin_dir:
            _write_gamescope_display_assets(Path(temp_plugin_dir))
            helper = main.gamescope_display_profiles.GamescopeDisplayProfiles(
                user_home=temp_home,
                plugin_dir=temp_plugin_dir,
                system_profile_paths=[],
            )
            managed_scripts_dir = Path(temp_home) / ".config" / "gamescope" / "scripts"
            managed_scripts_dir.mkdir(parents=True, exist_ok=True)
            helper.managed_profile_path.write_text(_DECKYZONE_GREEN_TINT_PROFILE, encoding="utf-8")
            helper.legacy_managed_green_tint_profile_path.parent.mkdir(parents=True, exist_ok=True)
            helper.legacy_managed_green_tint_profile_path.write_text(
                _DECKYZONE_GREEN_TINT_PROFILE,
                encoding="utf-8",
            )
            custom_script_path = managed_scripts_dir / "custom.lua"
            custom_script_path.write_text("-- custom", encoding="utf-8")

            settings = helper.cleanup_managed_files()

            self.assertEqual(settings["gamescopeZotacProfileVerificationState"], "absent")
            self.assertFalse(helper.managed_profile_path.exists())
            self.assertFalse(helper.legacy_managed_green_tint_profile_path.exists())
            self.assertTrue(custom_script_path.exists())

