import asyncio
import tempfile
import unittest
from pathlib import Path

from .support import (
    _CompletedProcess,
    _FAKE_SETTINGS_STORE,
    _async_noop,
    _write_gamescope_display_assets,
    main,
    reset_test_state,
)


class PluginLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        reset_test_state()

    async def test_main_schedules_startup_apply_when_enabled(self):
        calls = []

        class _FakeService:
            def get_settings(self):
                return {
                    "startupApplyEnabled": True,
                    "homeButtonEnabled": True,
                    "brightnessDialFixEnabled": True,
                    "inputplumberAvailable": True,
                    "rumbleEnabled": True,
                    "rumbleIntensity": 75,
                    "rumbleAvailable": True,
                    "missingGlyphFixGames": {},
                }

            async def apply_startup_mode(self):
                calls.append("applied")

            async def start_rumble_fixer(self):
                calls.append("rumble-started")

            async def stop_rumble_fixer(self):
                calls.append("rumble-stopped")

            async def start_brightness_dial_fixer(self):
                calls.append("brightness-started")

            async def stop_brightness_dial_fixer(self):
                calls.append("brightness-stopped")

        plugin = main.Plugin()
        plugin.service = _FakeService()

        await plugin._main()
        await asyncio.sleep(0)

        self.assertIsNotNone(plugin.startup_task)
        self.assertEqual(calls, ["rumble-started", "applied"])
        await plugin._unload()

    async def test_main_skips_startup_apply_when_disabled(self):
        calls = []

        class _FakeService:
            def get_settings(self):
                return {
                    "startupApplyEnabled": False,
                    "homeButtonEnabled": True,
                    "brightnessDialFixEnabled": True,
                    "inputplumberAvailable": True,
                    "rumbleEnabled": True,
                    "rumbleIntensity": 75,
                    "rumbleAvailable": True,
                    "missingGlyphFixGames": {},
                }

            def set_startup_apply_enabled(self, enabled):
                calls.append(("set", enabled))
                return {
                    "startupApplyEnabled": enabled,
                    "homeButtonEnabled": True,
                    "brightnessDialFixEnabled": True,
                    "inputplumberAvailable": True,
                    "rumbleEnabled": True,
                    "rumbleIntensity": 75,
                    "rumbleAvailable": True,
                    "missingGlyphFixGames": {},
                }

            async def apply_startup_mode(self):
                calls.append("applied")

            async def start_rumble_fixer(self):
                calls.append("rumble-started")

            async def stop_rumble_fixer(self):
                calls.append("rumble-stopped")

            async def start_brightness_dial_fixer(self):
                calls.append("brightness-started")

            async def stop_brightness_dial_fixer(self):
                calls.append("brightness-stopped")

        plugin = main.Plugin()
        plugin.service = _FakeService()

        await plugin._main()
        await asyncio.sleep(0)

        self.assertIsNone(plugin.startup_task)
        self.assertEqual(calls, ["rumble-started", ("set", False)])

    async def test_main_skips_brightness_dial_listener_when_disabled(self):
        calls = []

        class _FakeService:
            def get_settings(self):
                return {
                    "startupApplyEnabled": False,
                    "homeButtonEnabled": True,
                    "brightnessDialFixEnabled": False,
                    "inputplumberAvailable": True,
                    "rumbleEnabled": True,
                    "rumbleIntensity": 75,
                    "rumbleAvailable": True,
                    "missingGlyphFixGames": {},
                }

            def set_startup_apply_enabled(self, enabled):
                calls.append(("set", enabled))
                return self.get_settings()

            async def apply_startup_mode(self):
                calls.append("applied")

            async def start_rumble_fixer(self):
                calls.append("rumble-started")

            async def stop_rumble_fixer(self):
                calls.append("rumble-stopped")

            async def start_brightness_dial_fixer(self):
                calls.append("brightness-started")

            async def stop_brightness_dial_fixer(self):
                calls.append("brightness-stopped")

        plugin = main.Plugin()
        plugin.service = _FakeService()

        await plugin._main()
        await asyncio.sleep(0)

        self.assertEqual(calls, ["rumble-started", ("set", False)])

    async def test_plugin_test_rumble_delegates_to_service(self):
        calls = []

        class _FakeService:
            async def test_rumble(self):
                calls.append("tested")
                return True

        plugin = main.Plugin()
        plugin.service = _FakeService()

        result = await plugin.test_rumble()

        self.assertTrue(result)
        self.assertEqual(calls, ["tested"])

    async def test_plugin_sync_missing_glyph_fix_target_waits_for_startup_task(self):
        calls = []
        startup_started = asyncio.Event()
        startup_release = asyncio.Event()

        class _FakeService:
            def get_settings(self):
                return {
                    "startupApplyEnabled": True,
                    "homeButtonEnabled": True,
                    "brightnessDialFixEnabled": False,
                    "inputplumberAvailable": True,
                    "rumbleEnabled": False,
                    "rumbleIntensity": 75,
                    "rumbleAvailable": True,
                    "missingGlyphFixGames": {},
                }

            async def apply_startup_mode(self):
                calls.append("applied-start")
                startup_started.set()
                await startup_release.wait()
                calls.append("applied-end")

            async def sync_missing_glyph_fix_target(self, app_id):
                calls.append(("synced", app_id))
                return True

            async def cleanup(self):
                calls.append("cleanup")

        plugin = main.Plugin()
        plugin.service = _FakeService()

        await plugin._main()
        await startup_started.wait()

        sync_task = asyncio.create_task(plugin.sync_missing_glyph_fix_target("123"))
        await asyncio.sleep(0)
        self.assertEqual(calls, ["applied-start"])

        startup_release.set()
        result = await sync_task

        self.assertTrue(result)
        self.assertEqual(
            calls,
            ["applied-start", "applied-end", ("synced", "123")],
        )
        await plugin._unload()

    async def test_plugin_set_startup_apply_enabled_applies_target_immediately_when_enabled(self):
        calls = []

        class _FakeService:
            def set_startup_apply_enabled(self, enabled):
                calls.append(("set", enabled))
                return {
                    "startupApplyEnabled": enabled,
                    "homeButtonEnabled": True,
                    "brightnessDialFixEnabled": True,
                    "inputplumberAvailable": True,
                    "rumbleEnabled": True,
                    "rumbleIntensity": 75,
                    "rumbleAvailable": True,
                    "missingGlyphFixGames": {},
                }

            async def apply_startup_mode(self):
                calls.append("apply")
                return {"state": "applied", "message": "Startup mode re-applied: deck-uhid."}

            async def sync_home_button_navigation_state(self):
                calls.append("sync-home")

        plugin = main.Plugin()
        plugin.service = _FakeService()

        result = await plugin.set_startup_apply_enabled(True)

        self.assertTrue(result["startupApplyEnabled"])
        self.assertEqual(calls, [("set", True), "apply", "sync-home"])

    async def test_plugin_set_startup_apply_enabled_restores_target_immediately_when_disabled(self):
        calls = []

        class _FakeService:
            def set_startup_apply_enabled(self, enabled):
                calls.append(("set", enabled))
                return {
                    "startupApplyEnabled": enabled,
                    "homeButtonEnabled": True,
                    "brightnessDialFixEnabled": True,
                    "inputplumberAvailable": True,
                    "rumbleEnabled": True,
                    "rumbleIntensity": 75,
                    "rumbleAvailable": True,
                    "missingGlyphFixGames": {},
                }

            async def disable_startup_target_runtime(self):
                calls.append("disable-runtime")
                return True

            async def sync_home_button_navigation_state(self):
                calls.append("sync-home")

        plugin = main.Plugin()
        plugin.service = _FakeService()

        result = await plugin.set_startup_apply_enabled(False)

        self.assertFalse(result["startupApplyEnabled"])
        self.assertEqual(calls, [("set", False), "disable-runtime", "sync-home"])

    async def test_plugin_uninstall_runs_cleanup_and_clears_settings(self):
        calls = []
        main.plugin_settings.set_startup_apply_enabled(False)
        main.plugin_settings.set_home_button_enabled(False)
        main.plugin_settings.set_missing_glyph_fix_enabled("123", True)

        class _FakeService:
            async def cleanup(self):
                calls.append("cleanup")

        plugin = main.Plugin()
        plugin.service = _FakeService()

        await plugin._uninstall()

        self.assertEqual(calls, ["cleanup"])
        self.assertEqual(_FAKE_SETTINGS_STORE, {})

    async def test_plugin_uninstall_removes_only_managed_gamescope_display_files(self):
        with tempfile.TemporaryDirectory() as temp_home, tempfile.TemporaryDirectory() as temp_plugin_dir:
            _write_gamescope_display_assets(Path(temp_plugin_dir))
            helper = main.gamescope_display_profiles.GamescopeDisplayProfiles(
                user_home=temp_home,
                plugin_dir=temp_plugin_dir,
                system_profile_paths=[],
            )
            service = main.DeckyZoneService(
                command_runner=lambda *args, **kwargs: _CompletedProcess(returncode=0),
                sleep=_async_noop,
                read_text=lambda path: "",
                gamescope_display_profiles=helper,
            )
            plugin = main.Plugin(service=service)
            custom_script_path = (
                Path(temp_home)
                / ".config"
                / "gamescope"
                / "scripts"
                / "custom.lua"
            )
            custom_script_path.parent.mkdir(parents=True, exist_ok=True)
            custom_script_path.write_text("-- custom", encoding="utf-8")

            managed_dir = Path(temp_home) / ".config" / "gamescope" / "scripts"
            managed_profile_path = managed_dir / "zotac.zone.oled.lua"

            await service.set_gamescope_zotac_profile_enabled(True)
            await service.set_gamescope_green_tint_fix_enabled(True)
            await plugin._uninstall()

            self.assertTrue(custom_script_path.exists())
            self.assertTrue(managed_dir.exists())
            self.assertFalse(managed_profile_path.exists())

