import asyncio
import os
import stat
import sys
import tempfile
import types
import unittest
from pathlib import Path


# Minimal Decky Loader stubs required to import main.py in unit tests.
decky = types.ModuleType("decky")
decky.DECKY_PLUGIN_VERSION = "test"
class TestLogger:
    def warning(self, message):
        pass

    def info(self, message):
        pass

    def debug(self, message):
        pass

    def error(self, message):
        pass


decky.logger = TestLogger()
decky.DECKY_USER_HOME = "."
decky.DECKY_PLUGIN_DIR = "."
decky.DECKY_PLUGIN_RUNTIME_DIR = "."
sys.modules["decky"] = decky

settings = types.ModuleType("settings")


class SettingsManager:
    def __init__(self, *args, **kwargs):
        self.settings = {}

    def read(self):
        return self.settings

    def setSetting(self, name, value):
        self.settings[name] = value

    def commit(self):
        pass

class FakeGamescopeDisplayProfiles:
    def get_state(self):
        return {
            "gamescopeZotacProfileBuiltIn": False,
            "gamescopeZotacProfileInstalled": False,
            "gamescopeGreenTintFixEnabled": False,
            "gamescopeZotacProfileTargetPath": "",
            "gamescopeZotacProfileVerificationState": "absent",
        }

settings.SettingsManager = SettingsManager
sys.modules["settings"] = settings

os.environ["DECKY_PLUGIN_SETTINGS_DIR"] = "."

import main
import steamos_sleep_fix


GRUB_DEFAULTS_WITH_OFF = '''GRUB_CMDLINE_LINUX="${GRUB_CMDLINE_LINUX} \\
log_buf_len=4M \\
amd_iommu=off \\
audit=0 \\
"
'''

GRUB_DEFAULTS_WITHOUT_OFF = '''GRUB_CMDLINE_LINUX="${GRUB_CMDLINE_LINUX} \\
log_buf_len=4M \\
audit=0 \\
"
'''

class FakeSettingsStore:
    def __init__(self, fix_sleep_enabled=False, original_iommu_disabled=None):
        self.fix_sleep_enabled = fix_sleep_enabled
        self.original_iommu_disabled = original_iommu_disabled

    def get_fix_sleep_enabled(self):
        return self.fix_sleep_enabled

    def set_fix_sleep_enabled(self, enabled):
        self.fix_sleep_enabled = bool(enabled)
        return self.fix_sleep_enabled

    def get_fix_sleep_original_amd_iommu_off(self):
        return self.original_iommu_disabled

    def set_fix_sleep_original_amd_iommu_off(self, disabled):
        self.original_iommu_disabled = bool(disabled)
        return self.original_iommu_disabled

    def clear_fix_sleep_original_amd_iommu_off(self):
        self.original_iommu_disabled = None

    def get_startup_apply_enabled(self):
        return False

    def get_home_button_enabled(self):
        return False

    def get_brightness_dial_fix_enabled(self):
        return False

    def get_trackpad_mode(self):
        return "default"

    def get_zotac_glyphs_enabled(self):
        return False

    def get_rumble_enabled(self):
        return False

    def get_rumble_intensity(self):
        return 75

    def get_per_game_settings(self):
        return {}

class FakeSleepFix:
    def __init__(self, config_iommu_disabled):
        self.config_iommu_disabled = config_iommu_disabled
        self.apply_calls = []

    def get_state(self):
        return {
            "available": True,
            "message": "",
            "configIommuDisabled": self.config_iommu_disabled,
            "runtimeIommuDisabled": self.config_iommu_disabled,
        }

    def apply_iommu_disabled(self, disabled):
        self.apply_calls.append(bool(disabled))
        self.config_iommu_disabled = bool(disabled)
        return True

class SteamOSSleepFixTests(unittest.TestCase):
    def test_enable_removes_all_iommu_off_arguments(self):
        updated, changed = steamos_sleep_fix.set_amd_iommu_disabled(
            GRUB_DEFAULTS_WITH_OFF, False
        )

        self.assertTrue(changed)
        self.assertNotIn("amd_iommu=off", updated)

    def test_enable_is_idempotent_when_iommu_off_is_absent(self):
        updated, changed = steamos_sleep_fix.set_amd_iommu_disabled(
            GRUB_DEFAULTS_WITHOUT_OFF, False
        )

        self.assertFalse(changed)
        self.assertEqual(updated, GRUB_DEFAULTS_WITHOUT_OFF)

    def test_disable_adds_one_iommu_off_argument(self):
        updated, changed = steamos_sleep_fix.set_amd_iommu_disabled(
            GRUB_DEFAULTS_WITHOUT_OFF, True
        )

        self.assertTrue(changed)
        self.assertEqual(updated.count("amd_iommu=off"), 1)

    def test_disable_is_idempotent_when_one_iommu_off_argument_exists(self):
        updated, changed = steamos_sleep_fix.set_amd_iommu_disabled(
            GRUB_DEFAULTS_WITH_OFF, True
        )

        self.assertFalse(changed)
        self.assertEqual(updated, GRUB_DEFAULTS_WITH_OFF)

    def test_rejects_an_unexpected_grub_assignment(self):
        with self.assertRaises(steamos_sleep_fix.SleepFixConfigurationError):
            steamos_sleep_fix.set_amd_iommu_disabled('GRUB_CMDLINE_LINUX="quiet"\n', False)

    def test_failed_generation_restores_both_grub_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            os_release_path = root / "os-release"
            defaults_path = root / "grub-steamos"
            generated_path = root / "grub.cfg"
            mkconfig_path = root / "grub-mkconfig"
            runtime_dir = root / "runtime"

            os_release_path.write_text('ID="steamos"\n', encoding="utf-8")
            defaults_path.write_text(GRUB_DEFAULTS_WITH_OFF, encoding="utf-8")
            generated_path.write_text("previous generated config\n", encoding="utf-8")
            mkconfig_path.write_text("placeholder", encoding="utf-8")
            mkconfig_path.chmod(mkconfig_path.stat().st_mode | stat.S_IXUSR)

            def failing_runner(args, **kwargs):
                generated_path.write_text("partial generated config\n", encoding="utf-8")
                raise RuntimeError("grub-mkconfig failed")

            sleep_fix = steamos_sleep_fix.SteamOSSleepFix(
                command_runner=failing_runner,
                runtime_dir=runtime_dir,
                os_release_paths=(os_release_path,),
                grub_default_path=defaults_path,
                grub_config_path=generated_path,
                grub_mkconfig_path=mkconfig_path,
            )

            with self.assertRaises(steamos_sleep_fix.SleepFixConfigurationError):
                sleep_fix.apply_iommu_disabled(False)

            self.assertEqual(
                defaults_path.read_text(encoding="utf-8"), GRUB_DEFAULTS_WITH_OFF
            )
            self.assertEqual(
                generated_path.read_text(encoding="utf-8"), "previous generated config\n"
            )
            self.assertEqual(
                (runtime_dir / steamos_sleep_fix.ORIGINAL_GRUB_BACKUP_FILENAME).read_text(
                    encoding="utf-8"
                ),
                GRUB_DEFAULTS_WITH_OFF,
            )

    def test_service_restores_original_iommu_disabled_state(self):
        settings = FakeSettingsStore()
        sleep_fix = FakeSleepFix(config_iommu_disabled=True)

        service = main.DeckyZoneService.__new__(main.DeckyZoneService)
        service.settings_store = settings
        service.sleep_fix = sleep_fix
        service.gamescope_display_profiles = FakeGamescopeDisplayProfiles()
        service.logger = main.decky.logger
        service._inputplumber_available = False
        service._rumble_available = False

        service._get_controller_mode_snapshot = lambda: {
            "mode": "gamepad",
            "available": True,
        }

        service._get_gyro_mount_matrix_fix_state = lambda: {
            "available": False,
            "enabled": False,
        }

        asyncio.run(service.set_fix_sleep_enabled(True))

        self.assertTrue(settings.get_fix_sleep_enabled())
        self.assertTrue(
            settings.get_fix_sleep_original_amd_iommu_off()
        )
        self.assertEqual(sleep_fix.apply_calls, [False])

        asyncio.run(service.set_fix_sleep_enabled(False))

        self.assertFalse(settings.get_fix_sleep_enabled())
        self.assertIsNone(
            settings.get_fix_sleep_original_amd_iommu_off()
        )
        self.assertEqual(sleep_fix.apply_calls, [False, True])

    def test_service_restores_original_iommu_enabled_state(self):
        settings = FakeSettingsStore()
        sleep_fix = FakeSleepFix(config_iommu_disabled=False)

        service = main.DeckyZoneService.__new__(main.DeckyZoneService)
        service.settings_store = settings
        service.sleep_fix = sleep_fix
        service.gamescope_display_profiles = FakeGamescopeDisplayProfiles()
        service.logger = main.decky.logger
        service._inputplumber_available = False
        service._rumble_available = False

        service._get_controller_mode_snapshot = lambda: {
            "mode": "gamepad",
            "available": True,
        }

        service._get_gyro_mount_matrix_fix_state = lambda: {
            "available": False,
            "enabled": False,
        }

        asyncio.run(service.set_fix_sleep_enabled(True))

        self.assertTrue(settings.get_fix_sleep_enabled())
        self.assertFalse(
            settings.get_fix_sleep_original_amd_iommu_off()
        )
        self.assertEqual(sleep_fix.apply_calls, [False])

        asyncio.run(service.set_fix_sleep_enabled(False))

        self.assertFalse(settings.get_fix_sleep_enabled())
        self.assertIsNone(
            settings.get_fix_sleep_original_amd_iommu_off()
        )
        self.assertEqual(sleep_fix.apply_calls, [False, False])

if __name__ == "__main__":
    unittest.main()
