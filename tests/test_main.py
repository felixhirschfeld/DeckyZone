import sys
import types
import unittest
from pathlib import Path
import subprocess
import os
import asyncio


class _FakeLogger:
    def __init__(self):
        self.messages = []

    def info(self, *args, **kwargs):
        self.messages.append(("info", args, kwargs))

    def warning(self, *args, **kwargs):
        self.messages.append(("warning", args, kwargs))

    def error(self, *args, **kwargs):
        self.messages.append(("error", args, kwargs))


async def _async_noop(*args, **kwargs):
    return None


def _noop(*args, **kwargs):
    return None


_FAKE_SETTINGS_STORE = {}


def _fake_settings_module():
    module = types.ModuleType("settings")

    class SettingsManager:
        def __init__(self, name, settings_directory):
            self.name = name
            self.settings_directory = settings_directory
            self.settings = {}

        def read(self):
            self.settings = dict(_FAKE_SETTINGS_STORE)

        def setSetting(self, name, value):
            if not self.settings:
                self.settings = dict(_FAKE_SETTINGS_STORE)
            self.settings[name] = value
            return value

        def commit(self):
            _FAKE_SETTINGS_STORE.clear()
            _FAKE_SETTINGS_STORE.update(self.settings)

    module.SettingsManager = SettingsManager
    return module


def _fake_decky_module():
    module = types.ModuleType("decky")
    module.logger = _FakeLogger()
    module.DECKY_USER_HOME = "/tmp/decky-user"
    module.DECKY_HOME = "/tmp/decky-home"
    module.DECKY_PLUGIN_DIR = str(Path(__file__).resolve().parents[1])
    module.emit = _async_noop
    module.migrate_logs = _noop
    module.migrate_settings = _noop
    module.migrate_runtime = _noop
    return module


os.environ.setdefault("DECKY_PLUGIN_SETTINGS_DIR", "/tmp/deckyzone-settings")
sys.modules.setdefault("settings", _fake_settings_module())
sys.modules.setdefault("decky", _fake_decky_module())
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "py_modules"))

import main  # noqa: E402


class _CompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class DeckyZoneServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        _FAKE_SETTINGS_STORE.clear()
        main.plugin_settings.setting_file.settings = {}

    async def test_initial_status_is_idle(self):
        service = main.DeckyZoneService(
            command_runner=lambda *args, **kwargs: _CompletedProcess(),
            sleep=_async_noop,
            read_text=lambda path: "",
        )

        self.assertEqual(
            service.get_status(),
            {"state": "idle", "message": "Waiting to apply startup mode."},
        )

    async def test_apply_startup_mode_reports_unsupported_when_device_does_not_match(self):
        calls = []

        def runner(*args, **kwargs):
            calls.append((args, kwargs))
            return _CompletedProcess()

        service = main.DeckyZoneService(
            command_runner=runner,
            sleep=_async_noop,
            read_text=lambda path: {"sys_vendor": "Other", "board_name": "Other"}[
                Path(path).name
            ],
        )

        status = await service.apply_startup_mode()

        self.assertEqual(
            status,
            {
                "state": "unsupported",
                "message": "Unsupported device: startup mode only applies on Zotac Zone.",
            },
        )
        self.assertEqual(calls, [])

    async def test_apply_startup_mode_calls_busctl_after_dbus_is_ready(self):
        commands = []
        logger = _FakeLogger()

        def runner(command, **kwargs):
            commands.append((command, kwargs))
            return _CompletedProcess(returncode=0)

        service = main.DeckyZoneService(
            command_runner=runner,
            sleep=_async_noop,
            logger=logger,
            read_text=lambda path: {"sys_vendor": "ZOTAC", "board_name": "G0A1W"}[
                Path(path).name
            ],
        )
        service._get_ids = lambda: (1000, 1000)

        status = await service.apply_startup_mode()

        self.assertEqual(
            status,
            {"state": "applied", "message": "Startup mode re-applied: deck-uhid."},
        )
        self.assertEqual(len(commands), 2)
        self.assertEqual(
            commands[0][0],
            [
                "busctl",
                "get-property",
                "org.shadowblip.InputPlumber",
                "/org/shadowblip/InputPlumber/CompositeDevice0",
                "org.shadowblip.Input.CompositeDevice",
                "ProfileName",
            ],
        )
        self.assertEqual(
            commands[1][0],
            [
                "busctl",
                "call",
                "org.shadowblip.InputPlumber",
                "/org/shadowblip/InputPlumber/CompositeDevice0",
                "org.shadowblip.Input.CompositeDevice",
                "SetTargetDevices",
                "as",
                "3",
                "deck-uhid",
                "keyboard",
                "mouse",
            ],
        )
        info_messages = [args[0] for level, args, _ in logger.messages if level == "info"]
        self.assertIn(
            "DeckyZone privilege context: uid=1000 euid=1000 elevated=False",
            info_messages,
        )

    async def test_apply_startup_mode_fails_when_inputplumber_never_appears(self):
        commands = []

        def runner(command, **kwargs):
            commands.append((command, kwargs))
            raise RuntimeError("dbus unavailable")

        service = main.DeckyZoneService(
            command_runner=runner,
            sleep=_async_noop,
            read_text=lambda path: {"sys_vendor": "ZOTAC", "board_name": "G1A1W"}[
                Path(path).name
            ],
        )

        status = await service.apply_startup_mode()

        self.assertEqual(
            status,
            {
                "state": "failed",
                "message": "InputPlumber D-Bus was not ready within 5.0s.",
            },
        )
        self.assertGreaterEqual(len(commands), 1)

    async def test_apply_startup_mode_surfaces_busctl_stderr(self):
        def runner(command, **kwargs):
            if command[1] == "get-property":
                return _CompletedProcess(returncode=0)
            raise subprocess.CalledProcessError(
                returncode=1,
                cmd=command,
                stderr="Access denied",
            )

        service = main.DeckyZoneService(
            command_runner=runner,
            sleep=_async_noop,
            read_text=lambda path: {"sys_vendor": "ZOTAC", "board_name": "G0A1W"}[
                Path(path).name
            ],
        )

        status = await service.apply_startup_mode()

        self.assertEqual(
            status,
            {
                "state": "failed",
                "message": "Failed to apply startup mode: Access denied",
            },
        )

    async def test_apply_startup_mode_logs_privilege_context_only_once(self):
        logger = _FakeLogger()

        def runner(command, **kwargs):
            return _CompletedProcess(returncode=0)

        service = main.DeckyZoneService(
            command_runner=runner,
            sleep=_async_noop,
            logger=logger,
            read_text=lambda path: {"sys_vendor": "ZOTAC", "board_name": "G0A1W"}[
                Path(path).name
            ],
        )
        service._get_ids = lambda: (0, 0)

        await service.apply_startup_mode()
        await service.apply_startup_mode()

        info_messages = [args[0] for level, args, _ in logger.messages if level == "info"]
        self.assertEqual(
            info_messages.count(
                "DeckyZone privilege context: uid=0 euid=0 elevated=True"
            ),
            1,
        )

    async def test_get_settings_defaults_to_enabled(self):
        service = main.DeckyZoneService(
            command_runner=lambda *args, **kwargs: _CompletedProcess(returncode=0),
            sleep=_async_noop,
            read_text=lambda path: "",
        )
        service.probe_rumble_available = lambda: True

        self.assertEqual(
            service.get_settings(),
            {
                "startupApplyEnabled": True,
                "inputplumberAvailable": True,
                "rumbleEnabled": True,
                "rumbleIntensity": 75,
                "rumbleAvailable": True,
                "missingGlyphFixGames": {},
            },
        )

    async def test_get_settings_reports_inputplumber_unavailable_when_probe_fails(self):
        def runner(*args, **kwargs):
            raise RuntimeError("dbus unavailable")

        service = main.DeckyZoneService(
            command_runner=runner,
            sleep=_async_noop,
            read_text=lambda path: "",
        )
        service.probe_rumble_available = lambda: False

        self.assertEqual(
            service.get_settings(),
            {
                "startupApplyEnabled": True,
                "inputplumberAvailable": False,
                "rumbleEnabled": True,
                "rumbleIntensity": 75,
                "rumbleAvailable": False,
                "missingGlyphFixGames": {},
            },
        )

    async def test_set_rumble_enabled_starts_and_stops_background_loop(self):
        calls = []
        service = main.DeckyZoneService(
            command_runner=lambda *args, **kwargs: _CompletedProcess(returncode=0),
            sleep=_async_noop,
            read_text=lambda path: "",
        )
        service._inputplumber_available = True
        service.probe_rumble_available = lambda: True

        async def start():
            calls.append("start")
            return True

        async def stop():
            calls.append("stop")
            return True

        service.start_rumble_fixer = start
        service.stop_rumble_fixer = stop

        result = await service.set_rumble_enabled(False)
        self.assertEqual(
            result,
            {
                "startupApplyEnabled": True,
                "inputplumberAvailable": True,
                "rumbleEnabled": False,
                "rumbleIntensity": 75,
                "rumbleAvailable": True,
                "missingGlyphFixGames": {},
            },
        )

        result = await service.set_rumble_enabled(True)
        self.assertEqual(
            result,
            {
                "startupApplyEnabled": True,
                "inputplumberAvailable": True,
                "rumbleEnabled": True,
                "rumbleIntensity": 75,
                "rumbleAvailable": True,
                "missingGlyphFixGames": {},
            },
        )
        self.assertEqual(calls, ["stop", "start"])

    async def test_sync_missing_glyph_fix_target_applies_xbox_elite_for_enabled_game(self):
        commands = []
        grabbed = []
        service = main.DeckyZoneService(
            command_runner=lambda command, **kwargs: commands.append(command)
            or _CompletedProcess(returncode=0),
            sleep=_async_noop,
            read_text=lambda path: "",
        )
        service._grab_zotac_mouse_device = lambda: grabbed.append("grab") or True
        main.plugin_settings.set_missing_glyph_fix_enabled("123", True)

        result = await service.sync_missing_glyph_fix_target("123")

        self.assertTrue(result)
        self.assertEqual(grabbed, ["grab"])
        self.assertEqual(
            commands,
            [
                [
                    "busctl",
                    "call",
                    "org.shadowblip.InputPlumber",
                    main.INPUTPLUMBER_DBUS_PATH,
                    "org.shadowblip.Input.CompositeDevice",
                    "SetTargetDevices",
                    "as",
                    "3",
                    "xbox-elite",
                    "keyboard",
                    "mouse",
                ]
            ],
        )

    async def test_sync_missing_glyph_fix_target_releases_zotac_mouse_device_when_trackpads_enabled(self):
        commands = []
        released = []
        service = main.DeckyZoneService(
            command_runner=lambda command, **kwargs: commands.append(command)
            or _CompletedProcess(returncode=0),
            sleep=_async_noop,
            read_text=lambda path: "",
        )
        service._grab_zotac_mouse_device = lambda: True
        service._release_zotac_mouse_device = lambda: released.append("release") or True
        main.plugin_settings.set_missing_glyph_fix_enabled("123", True)

        await service.sync_missing_glyph_fix_target("123")
        main.plugin_settings.set_missing_glyph_fix_trackpads_disabled("123", False)

        result = await service.sync_missing_glyph_fix_target("123")

        self.assertTrue(result)
        self.assertEqual(released, ["release"])
        self.assertEqual(
            commands[0],
            [
                "busctl",
                "call",
                "org.shadowblip.InputPlumber",
                main.INPUTPLUMBER_DBUS_PATH,
                "org.shadowblip.Input.CompositeDevice",
                "SetTargetDevices",
                "as",
                "3",
                "xbox-elite",
                "keyboard",
                "mouse",
            ],
        )

    async def test_sync_missing_glyph_fix_target_restores_startup_mode_when_game_ends(self):
        commands = []
        released = []
        service = main.DeckyZoneService(
            command_runner=lambda command, **kwargs: commands.append(command)
            or _CompletedProcess(returncode=0),
            sleep=_async_noop,
            read_text=lambda path: "",
        )
        service._grab_zotac_mouse_device = lambda: True
        service._release_zotac_mouse_device = lambda: released.append("release") or True
        main.plugin_settings.set_missing_glyph_fix_enabled("123", True)

        await service.sync_missing_glyph_fix_target("123")
        result = await service.sync_missing_glyph_fix_target("0")

        self.assertTrue(result)
        self.assertEqual(released, ["release"])
        self.assertEqual(
            commands[-1],
            [
                "busctl",
                "call",
                "org.shadowblip.InputPlumber",
                main.INPUTPLUMBER_DBUS_PATH,
                "org.shadowblip.Input.CompositeDevice",
                "SetTargetDevices",
                "as",
                "3",
                "deck-uhid",
                "keyboard",
                "mouse",
            ],
        )

    async def test_sync_missing_glyph_fix_target_restarts_inputplumber_when_startup_apply_disabled(self):
        commands = []
        service = main.DeckyZoneService(
            command_runner=lambda command, **kwargs: commands.append(command)
            or _CompletedProcess(returncode=0),
            sleep=_async_noop,
            read_text=lambda path: "",
        )
        main.plugin_settings.set_startup_apply_enabled(False)
        main.plugin_settings.set_missing_glyph_fix_enabled("123", True)

        await service.sync_missing_glyph_fix_target("123")
        result = await service.sync_missing_glyph_fix_target("0")

        self.assertTrue(result)
        self.assertEqual(commands[-1], ["systemctl", "restart", "inputplumber"])

    async def test_sync_missing_glyph_fix_target_does_not_overwrite_startup_status(self):
        service = main.DeckyZoneService(
            command_runner=lambda command, **kwargs: _CompletedProcess(returncode=0),
            sleep=_async_noop,
            read_text=lambda path: "",
        )
        service._set_status("disabled", "Startup mode apply is disabled.")
        main.plugin_settings.set_missing_glyph_fix_enabled("123", True)

        await service.sync_missing_glyph_fix_target("123")
        await service.sync_missing_glyph_fix_target("0")

        self.assertEqual(
            service.get_status(),
            {
                "state": "disabled",
                "message": "Startup mode apply is disabled.",
            },
        )

    async def test_resolve_zotac_mouse_device_path_prefers_named_event_device(self):
        service = main.DeckyZoneService(
            command_runner=lambda *args, **kwargs: _CompletedProcess(returncode=0),
            sleep=_async_noop,
            read_text=lambda path: {
                "/sys/class/input/event12/device/name": "Generic Mouse",
                "/sys/class/input/event15/device/name": "ZOTAC Gaming Zone Mouse",
            }[path],
        )
        service._get_zotac_mouse_candidate_paths = lambda: [
            "/dev/input/event12",
            "/dev/input/event15",
        ]

        self.assertEqual(service._resolve_zotac_mouse_device_path(), "/dev/input/event15")

    async def test_set_rumble_intensity_clamps_values(self):
        service = main.DeckyZoneService(
            command_runner=lambda *args, **kwargs: _CompletedProcess(returncode=0),
            sleep=_async_noop,
            read_text=lambda path: "",
        )
        service._resolve_rumble_device_path = lambda: "/dev/input/event0"
        service._validate_rumble_device_path = lambda path: True

        result = await service.set_rumble_intensity(130)
        self.assertEqual(result["rumbleIntensity"], 100)

        result = await service.set_rumble_intensity(-15)
        self.assertEqual(result["rumbleIntensity"], 0)

    async def test_build_gain_event_uses_ev_ff_ff_gain_and_scaled_value(self):
        service = main.DeckyZoneService(
            command_runner=lambda *args, **kwargs: _CompletedProcess(returncode=0),
            sleep=_async_noop,
            read_text=lambda path: "",
        )

        event = service._build_gain_event(50)

        self.assertEqual(event.type, main.EV_FF)
        self.assertEqual(event.code, main.FF_GAIN)
        self.assertEqual(event.value, int((50 / 100.0) * 0xFFFF))

    async def test_set_rumble_intensity_applies_gain_and_preview_when_enabled(self):
        calls = []
        service = main.DeckyZoneService(
            command_runner=lambda *args, **kwargs: _CompletedProcess(returncode=0),
            sleep=_async_noop,
            read_text=lambda path: "",
        )
        service._resolve_rumble_device_path = lambda: "/dev/input/event15"
        service._validate_rumble_device_path = lambda path: True

        async def apply_gain(device_path=None):
            calls.append(("gain", device_path))
            return True

        async def preview(device_path=None):
            calls.append(("preview", device_path))
            return True

        service._apply_rumble_gain_once = apply_gain
        service._play_rumble_preview_once = preview

        await service.set_rumble_intensity(80)

        self.assertEqual(
            calls,
            [
                ("gain", "/dev/input/event15"),
                ("preview", "/dev/input/event15"),
            ],
        )

    async def test_set_rumble_intensity_skips_preview_when_unavailable(self):
        calls = []
        service = main.DeckyZoneService(
            command_runner=lambda *args, **kwargs: _CompletedProcess(returncode=0),
            sleep=_async_noop,
            read_text=lambda path: "",
        )
        service._resolve_rumble_device_path = lambda: None

        async def apply_gain(device_path=None):
            calls.append(("gain", device_path))
            return True

        async def preview(device_path=None):
            calls.append(("preview", device_path))
            return True

        service._apply_rumble_gain_once = apply_gain
        service._play_rumble_preview_once = preview

        await service.set_rumble_intensity(80)

        self.assertEqual(calls, [])

    async def test_resolve_rumble_device_prefers_exact_zotac_name(self):
        service = main.DeckyZoneService(
            command_runner=lambda *args, **kwargs: _CompletedProcess(returncode=0),
            sleep=_async_noop,
            read_text=lambda path: "",
        )
        service._get_rumble_candidate_paths = lambda: [
            "/dev/input/by-id/usb-other-event-joystick",
            "/dev/input/by-id/usb-zotac-event-joystick",
        ]
        service._resolve_rumble_candidate_path = lambda path: {
            "/dev/input/by-id/usb-other-event-joystick": "/dev/input/event12",
            "/dev/input/by-id/usb-zotac-event-joystick": "/dev/input/event15",
        }[path]
        service._read_rumble_candidate_device_name = lambda path: {
            "/dev/input/event12": "Generic Gamepad",
            "/dev/input/event15": "ZOTAC Gaming Zone",
        }[path]

        self.assertEqual(service._resolve_rumble_device_path(), "/dev/input/event15")

    async def test_resolve_rumble_device_returns_none_for_multiple_non_zotac_candidates(self):
        service = main.DeckyZoneService(
            command_runner=lambda *args, **kwargs: _CompletedProcess(returncode=0),
            sleep=_async_noop,
            read_text=lambda path: "",
        )
        service._get_rumble_candidate_paths = lambda: [
            "/dev/input/by-id/usb-pad-a-event-joystick",
            "/dev/input/by-id/usb-pad-b-event-joystick",
        ]
        service._resolve_rumble_candidate_path = lambda path: {
            "/dev/input/by-id/usb-pad-a-event-joystick": "/dev/input/event12",
            "/dev/input/by-id/usb-pad-b-event-joystick": "/dev/input/event13",
        }[path]
        service._read_rumble_candidate_device_name = lambda path: {
            "/dev/input/event12": "Generic Gamepad A",
            "/dev/input/event13": "Generic Gamepad B",
        }[path]

        self.assertIsNone(service._resolve_rumble_device_path())

    async def test_probe_rumble_available_returns_false_off_linux(self):
        service = main.DeckyZoneService(
            command_runner=lambda *args, **kwargs: _CompletedProcess(returncode=0),
            sleep=_async_noop,
            read_text=lambda path: "",
        )
        service._is_linux_platform = lambda: False

        self.assertEqual(
            service.probe_rumble_available(),
            False,
        )

    async def test_apply_rumble_gain_once_logs_warning_on_device_error(self):
        logger = _FakeLogger()
        service = main.DeckyZoneService(
            command_runner=lambda *args, **kwargs: _CompletedProcess(returncode=0),
            sleep=_async_noop,
            logger=logger,
            read_text=lambda path: "",
        )
        service.probe_rumble_available = lambda: True
        service._rumble_device_path = "/dev/input/event0"

        def write_event(*args, **kwargs):
            raise OSError("write failed")

        service._write_event_to_device = write_event

        result = await service._apply_rumble_gain_once()

        self.assertFalse(result)
        warning_messages = [args[0] for level, args, _ in logger.messages if level == "warning"]
        self.assertTrue(any("write failed" in message for message in warning_messages))

    async def test_set_rumble_intensity_does_not_probe_inputplumber(self):
        calls = []
        service = main.DeckyZoneService(
            command_runner=lambda *args, **kwargs: _CompletedProcess(returncode=0),
            sleep=_async_noop,
            read_text=lambda path: "",
        )
        service._inputplumber_available = True
        service.probe_inputplumber_available = lambda: calls.append("inputplumber") or True
        service._resolve_rumble_device_path = lambda: "/dev/input/event15"
        service._validate_rumble_device_path = lambda path: True

        async def apply_gain(device_path=None):
            calls.append(("gain", device_path))
            return True

        async def preview(device_path=None):
            calls.append(("preview", device_path))
            return True

        service._apply_rumble_gain_once = apply_gain
        service._play_rumble_preview_once = preview

        await service.set_rumble_intensity(80)

        self.assertEqual(
            calls,
            [
                ("gain", "/dev/input/event15"),
                ("preview", "/dev/input/event15"),
            ],
        )

    async def test_test_rumble_calls_force_feedback_rumble_and_stop(self):
        calls = []
        sleeps = []

        def runner(cmd, **kwargs):
            calls.append(cmd)
            return _CompletedProcess(returncode=0)

        async def fake_sleep(value):
            sleeps.append(value)

        service = main.DeckyZoneService(
            command_runner=runner,
            sleep=fake_sleep,
            read_text=lambda path: "",
        )

        main.plugin_settings.set_rumble_intensity(55)

        result = await service.test_rumble()

        self.assertTrue(result)
        self.assertEqual(
            calls[0][:-1],
            [
                "busctl",
                "call",
                "org.shadowblip.InputPlumber",
                main.INPUTPLUMBER_DBUS_PATH,
                "org.shadowblip.Output.ForceFeedback",
                "Rumble",
                "d",
            ],
        )
        self.assertAlmostEqual(float(calls[0][-1]), 0.55)
        self.assertEqual(
            calls[1],
            [
                "busctl",
                "call",
                "org.shadowblip.InputPlumber",
                main.INPUTPLUMBER_DBUS_PATH,
                "org.shadowblip.Output.ForceFeedback",
                "Stop",
            ],
        )
        self.assertEqual(sleeps, [main.RUMBLE_PREVIEW_DURATION_MS / 1000.0])

    async def test_test_rumble_returns_false_when_rumble_dbus_call_fails(self):
        calls = []

        def runner(cmd, **kwargs):
            calls.append(cmd)
            if len(calls) == 1:
                raise subprocess.CalledProcessError(
                    1, cmd, stderr="dbus rumble failed"
                )
            return _CompletedProcess(returncode=0)

        service = main.DeckyZoneService(
            command_runner=runner,
            sleep=_async_noop,
            read_text=lambda path: "",
        )

        self.assertFalse(await service.test_rumble())
        self.assertEqual(len(calls), 1)

    async def test_test_rumble_returns_false_when_stop_dbus_call_fails(self):
        calls = []
        sleeps = []

        def runner(cmd, **kwargs):
            calls.append(cmd)
            if len(calls) == 2:
                raise subprocess.CalledProcessError(1, cmd, stderr="dbus stop failed")
            return _CompletedProcess(returncode=0)

        async def fake_sleep(value):
            sleeps.append(value)

        service = main.DeckyZoneService(
            command_runner=runner,
            sleep=fake_sleep,
            read_text=lambda path: "",
        )

        self.assertFalse(await service.test_rumble())
        self.assertEqual(len(calls), 2)
        self.assertEqual(sleeps, [main.RUMBLE_PREVIEW_DURATION_MS / 1000.0])

    async def test_set_rumble_enabled_does_not_probe_inputplumber(self):
        calls = []
        service = main.DeckyZoneService(
            command_runner=lambda *args, **kwargs: _CompletedProcess(returncode=0),
            sleep=_async_noop,
            read_text=lambda path: "",
        )
        service._inputplumber_available = True
        service.probe_inputplumber_available = lambda: calls.append("inputplumber") or True
        service.probe_rumble_available = lambda: True

        async def start():
            calls.append("start")
            return True

        async def stop():
            calls.append("stop")
            return True

        service.start_rumble_fixer = start
        service.stop_rumble_fixer = stop

        await service.set_rumble_enabled(False)
        await service.set_rumble_enabled(True)

        self.assertEqual(calls, ["stop", "start"])

    async def test_plugin_settings_persist_startup_apply_enabled(self):
        self.assertTrue(main.plugin_settings.get_startup_apply_enabled())
        self.assertFalse(main.plugin_settings.set_startup_apply_enabled(False))
        self.assertFalse(main.plugin_settings.get_startup_apply_enabled())

    async def test_plugin_settings_persist_rumble_values(self):
        self.assertTrue(main.plugin_settings.get_rumble_enabled())
        self.assertEqual(main.plugin_settings.get_rumble_intensity(), 75)

        self.assertFalse(main.plugin_settings.set_rumble_enabled(False))
        self.assertEqual(main.plugin_settings.set_rumble_intensity(55), 55)

        self.assertFalse(main.plugin_settings.get_rumble_enabled())
        self.assertEqual(main.plugin_settings.get_rumble_intensity(), 55)

    async def test_plugin_settings_persist_missing_glyph_fix_games_without_false_entries(self):
        self.assertEqual(main.plugin_settings.get_missing_glyph_fix_games(), {})

        self.assertEqual(
            main.plugin_settings.set_missing_glyph_fix_enabled("123", True),
            {"123": {"disableTrackpads": True}},
        )
        self.assertTrue(main.plugin_settings.get_missing_glyph_fix_enabled("123"))
        self.assertTrue(main.plugin_settings.get_missing_glyph_fix_trackpads_disabled("123"))

        self.assertEqual(
            main.plugin_settings.set_missing_glyph_fix_trackpads_disabled("123", False),
            {"123": {"disableTrackpads": False}},
        )
        self.assertFalse(main.plugin_settings.get_missing_glyph_fix_trackpads_disabled("123"))

        self.assertEqual(
            main.plugin_settings.set_missing_glyph_fix_enabled("123", False),
            {},
        )
        self.assertFalse(main.plugin_settings.get_missing_glyph_fix_enabled("123"))

    async def test_plugin_settings_migrates_legacy_missing_glyph_fix_bool_entries(self):
        _FAKE_SETTINGS_STORE["missingGlyphFixGames"] = {
            "123": True,
            "456": False,
        }

        self.assertEqual(
            main.plugin_settings.get_missing_glyph_fix_games(),
            {"123": {"disableTrackpads": True}},
        )
        self.assertTrue(main.plugin_settings.get_missing_glyph_fix_enabled("123"))
        self.assertTrue(main.plugin_settings.get_missing_glyph_fix_trackpads_disabled("123"))

    async def test_set_missing_glyph_fix_trackpads_disabled_ignores_unknown_games(self):
        self.assertEqual(
            main.plugin_settings.set_missing_glyph_fix_trackpads_disabled("123", False),
            {},
        )

    async def test_set_startup_apply_enabled_sets_plain_disabled_status_before_apply(self):
        service = main.DeckyZoneService(
            command_runner=lambda *args, **kwargs: _CompletedProcess(returncode=0),
            sleep=_async_noop,
            read_text=lambda path: "",
        )
        service._inputplumber_available = True
        service._rumble_available = False

        result = service.set_startup_apply_enabled(False)

        self.assertEqual(
            result,
            {
                "startupApplyEnabled": False,
                "inputplumberAvailable": True,
                "rumbleEnabled": True,
                "rumbleIntensity": 75,
                "rumbleAvailable": False,
                "missingGlyphFixGames": {},
            },
        )
        self.assertEqual(
            service.get_status(),
            {
                "state": "disabled",
                "message": "Startup mode apply is disabled.",
            },
        )

    async def test_set_startup_apply_enabled_keeps_cached_inputplumber_availability(self):
        def runner(*args, **kwargs):
            raise RuntimeError("dbus unavailable")

        service = main.DeckyZoneService(
            command_runner=runner,
            sleep=_async_noop,
            read_text=lambda path: "",
        )
        service._inputplumber_available = True
        service._rumble_available = False

        result = service.set_startup_apply_enabled(False)

        self.assertTrue(result["inputplumberAvailable"])

    async def test_set_startup_apply_enabled_sets_reboot_message_after_successful_apply(self):
        service = main.DeckyZoneService(
            command_runner=lambda *args, **kwargs: _CompletedProcess(returncode=0),
            sleep=_async_noop,
            read_text=lambda path: {"sys_vendor": "ZOTAC", "board_name": "G0A1W"}[
                Path(path).name
            ],
        )

        await service.apply_startup_mode()
        service.set_startup_apply_enabled(False)

        self.assertEqual(
            service.get_status(),
            {
                "state": "disabled",
                "message": "Startup mode apply is disabled. Reboot to restore unmodified InputPlumber startup behavior.",
            },
        )


class PluginLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        _FAKE_SETTINGS_STORE.clear()
        main.plugin_settings.setting_file.settings = {}

    async def test_main_schedules_startup_apply_when_enabled(self):
        calls = []

        class _FakeService:
            def get_settings(self):
                return {
                    "startupApplyEnabled": True,
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

        plugin = main.Plugin()
        plugin.service = _FakeService()

        await plugin._main()
        await asyncio.sleep(0)

        self.assertIsNone(plugin.startup_task)
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


class FrontendSourceTests(unittest.TestCase):
    def test_index_uses_controller_panel_with_rumble_controls(self):
        source = Path(__file__).resolve().parents[1].joinpath("src", "index.tsx").read_text()

        self.assertIn('title="Controller"', source)
        self.assertIn("ButtonItem", source)
        self.assertIn("Router.MainRunningApp", source)
        self.assertIn('Startup Target', source)
        self.assertIn('Missing Glyph Fix', source)
        self.assertIn('Vibration Intensity', source)
        self.assertIn('Vibration intensity', source)
        self.assertIn('setMissingGlyphFixEnabled = callable<[string, boolean], PluginSettings>', source)
        self.assertIn('set_missing_glyph_fix_enabled', source)
        self.assertIn('syncMissingGlyphFixTarget = callable<[string], boolean>', source)
        self.assertIn('set_missing_glyph_fix_trackpads_disabled', source)
        self.assertIn('setMissingGlyphFixTrackpadsDisabled = callable<[string, boolean], PluginSettings>', source)
        self.assertIn('testRumble = callable<[], boolean>', source)
        self.assertIn('Test Rumble', source)
        self.assertIn("missingGlyphFixGames", source)
        self.assertIn("disableTrackpads", source)
        self.assertIn("icon_data_format", source)
        self.assertIn("icon_hash", source)
        self.assertIn("local_cache_version", source)
        self.assertIn("Launch a game to enable this glyph fix.", source)
        self.assertIn("getActiveGameIconSource", source)
        self.assertIn("setInterval(() => {", source)
        self.assertIn('clearInterval(activeGamePollInterval)', source)
        self.assertIn('Disable Trackpads', source)
        self.assertIn("isTrackpadsDisabled", source)
        self.assertIn("isMissingGlyphFixEnabled &&", source)
        self.assertIn("rumbleMessageKind", source)
        self.assertIn("rumbleMessageKind === 'error' ? 'red' : undefined", source)
        self.assertIn("Restores the Zotac controller after boot.", source)
        self.assertIn("Change and test vibration intensity.", source)
        self.assertIn("Rumble device is not available.", source)
        self.assertIn("settings.rumbleEnabled &&", source)
        self.assertIn("getRumbleDescription(settings)", source)
        self.assertNotIn("getRumbleDescription(settings, rumbleMessage)", source)
        self.assertIn("rumbleIntensityDraft", source)
        self.assertIn("rumbleIntensitySaveTimeout", source)
        self.assertIn("value={rumbleIntensityDraft}", source)
        self.assertIn("setTimeout(() => {", source)
        self.assertIn("disabled={savingStartup}", source)
        self.assertIn("disabled={savingRumble}", source)
        self.assertIn("!settings.rumbleEnabled", source)
        self.assertIn("!settings.rumbleAvailable", source)
        self.assertNotIn("savingIntensity", source)
        self.assertNotIn("value={settings.rumbleIntensity}", source)
        self.assertNotIn("disabled={savingStartup || !settings.inputplumberAvailable}", source)
        self.assertNotIn("disabled={savingRumble || !settings.rumbleAvailable}", source)
        self.assertNotIn("<strong>State:</strong>", source)
        self.assertNotIn('title="Startup Mode"', source)
        self.assertNotIn('title="Controller Fix"', source)
        self.assertNotIn('label="Controller Fix"', source)
        self.assertNotIn('label="Apply controller fix on startup"', source)
        self.assertNotIn('label="Enable startup controller fix"', source)
        self.assertNotIn('label="Enable vibration intensity fix"', source)
        self.assertNotIn('label="Per-Game Overrides"', source)
        self.assertNotIn("Reapply Startup Mode", source)
        self.assertNotIn("Rumble helper or joystick device is not available.", source)


if __name__ == "__main__":
    unittest.main()
