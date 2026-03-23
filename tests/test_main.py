import sys
import types
import unittest
from pathlib import Path
import subprocess


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


def _fake_decky_module():
    module = types.ModuleType("decky")
    module.logger = _FakeLogger()
    module.DECKY_USER_HOME = "/tmp/decky-user"
    module.DECKY_HOME = "/tmp/decky-home"
    module.emit = _async_noop
    module.migrate_logs = _noop
    module.migrate_settings = _noop
    module.migrate_runtime = _noop
    return module


sys.modules.setdefault("decky", _fake_decky_module())
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main  # noqa: E402


class _CompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class DeckyZoneServiceTests(unittest.IsolatedAsyncioTestCase):
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
            {"state": "applied", "message": "Startup mode re-applied: xbox-elite."},
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
                "xbox-elite",
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


if __name__ == "__main__":
    unittest.main()
