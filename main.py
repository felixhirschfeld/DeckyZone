import asyncio
import ctypes
import ctypes.util
import os
import subprocess
import sys
from pathlib import Path

import decky
import controller_targets
import plugin_settings


SUPPORTED_BOARDS = {"G0A1W", "G1A1W"}
INPUTPLUMBER_DBUS_PATH = "/org/shadowblip/InputPlumber/CompositeDevice0"
DBUS_READY_MESSAGE = "Waiting to apply startup mode."
UNSUPPORTED_MESSAGE = "Unsupported device: startup mode only applies on Zotac Zone."
DISABLED_MESSAGE = "Startup mode apply is disabled."
DISABLED_REBOOT_MESSAGE = (
    "Startup mode apply is disabled. Reboot to restore unmodified InputPlumber startup behavior."
)
READY_TIMEOUT_SECONDS = 5.0
READY_POLL_INTERVAL_SECONDS = 0.5
DEFAULT_APP_ID = "0"
STARTUP_MODE = "deck-uhid"
MISSING_GLYPH_FIX_TARGET = "xbox-elite"
ZOTAC_MOUSE_DEVICE_NAME = "ZOTAC Gaming Zone Mouse"
DEFAULT_RUMBLE_REAPPLY_INTERVAL_SECONDS = 2
RUMBLE_PREVIEW_DURATION_MS = 180
EV_FF = 0x15
FF_RUMBLE = 0x50
FF_GAIN = 0x60


class _TimeVal(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_long), ("tv_usec", ctypes.c_long)]


class _InputEvent(ctypes.Structure):
    _fields_ = [
        ("time", _TimeVal),
        ("type", ctypes.c_ushort),
        ("code", ctypes.c_ushort),
        ("value", ctypes.c_int),
    ]


class _FFTrigger(ctypes.Structure):
    _fields_ = [("button", ctypes.c_ushort), ("interval", ctypes.c_ushort)]


class _FFReplay(ctypes.Structure):
    _fields_ = [("length", ctypes.c_ushort), ("delay", ctypes.c_ushort)]


class _FFRumbleEffect(ctypes.Structure):
    _fields_ = [
        ("strong_magnitude", ctypes.c_ushort),
        ("weak_magnitude", ctypes.c_ushort),
    ]


class _FFEffectUnion(ctypes.Union):
    _fields_ = [("rumble", _FFRumbleEffect)]


class _FFEffect(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ushort),
        ("id", ctypes.c_short),
        ("direction", ctypes.c_ushort),
        ("trigger", _FFTrigger),
        ("replay", _FFReplay),
        ("u", _FFEffectUnion),
    ]


def _ioc(direction, ioctl_type, number, size):
    return (
        (direction << 30)
        | (ioctl_type << 8)
        | number
        | (size << 16)
    )


def _iow(ioctl_type, number, data_type):
    return _ioc(1, ioctl_type, number, ctypes.sizeof(data_type))


EVIOCSFF = _iow(ord("E"), 0x80, _FFEffect)
EVIOCRMFF = _iow(ord("E"), 0x81, ctypes.c_int)
EVIOCGRAB = _iow(ord("E"), 0x90, ctypes.c_int)


class DeckyZoneService:
    def __init__(
        self,
        command_runner=subprocess.run,
        sleep=asyncio.sleep,
        logger=decky.logger,
        read_text=None,
        settings_store=plugin_settings,
    ):
        self.command_runner = command_runner
        self.sleep = sleep
        self.logger = logger
        self.read_text = read_text or self._read_text
        self.settings_store = settings_store
        self._status = {"state": "idle", "message": DBUS_READY_MESSAGE}
        self._privilege_context_logged = False
        self._inputplumber_available = False
        self._startup_applied_this_session = False
        self._temporary_target_mode = None
        self._zotac_mouse_device_fd = None
        self._zotac_mouse_device_path = None
        self._rumble_available = False
        self._rumble_device_path = None
        self._rumble_task = None
        self._rumble_running = False
        self._libc = ctypes.CDLL(ctypes.util.find_library("c") or None, use_errno=True)

    def get_status(self):
        return dict(self._status)

    def get_settings(self):
        self._inputplumber_available = bool(self.probe_inputplumber_available())
        self._rumble_available = bool(self.probe_rumble_available())
        return self._current_settings()

    def _set_status(self, state, message):
        self._status = {"state": state, "message": message}

    def _read_text(self, path):
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip()

    def _current_settings(self):
        return {
            "startupApplyEnabled": self.settings_store.get_startup_apply_enabled(),
            "inputplumberAvailable": self._inputplumber_available,
            "rumbleEnabled": self.settings_store.get_rumble_enabled(),
            "rumbleIntensity": self.settings_store.get_rumble_intensity(),
            "rumbleAvailable": self._rumble_available,
            "missingGlyphFixGames": self.settings_store.get_missing_glyph_fix_games(),
        }

    def get_env(self):
        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = ""
        return env

    def _busctl_args(self, *args):
        return ["busctl", *args]

    def _systemctl_args(self, *args):
        return ["systemctl", *args]

    def _get_ids(self):
        return os.getuid(), os.geteuid()

    def log_privilege_context(self):
        if self._privilege_context_logged:
            return

        uid, euid = self._get_ids()
        elevated = uid == 0 or euid == 0
        self.logger.info(
            f"DeckyZone privilege context: uid={uid} euid={euid} elevated={elevated}"
        )
        self._privilege_context_logged = True

    def is_supported_device(self):
        try:
            vendor = self.read_text("/sys/devices/virtual/dmi/id/sys_vendor")
            board = self.read_text("/sys/devices/virtual/dmi/id/board_name")
        except Exception:
            return False
        return vendor == "ZOTAC" and board in SUPPORTED_BOARDS

    def _probe_inputplumber_profile_name(self):
        result = self.command_runner(
            self._busctl_args(
                "get-property",
                "org.shadowblip.InputPlumber",
                INPUTPLUMBER_DBUS_PATH,
                "org.shadowblip.Input.CompositeDevice",
                "ProfileName",
            ),
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.get_env(),
        )
        self._inputplumber_available = result.returncode == 0
        return self._inputplumber_available

    def probe_inputplumber_available(self):
        try:
            return self._probe_inputplumber_profile_name()
        except Exception:
            self._inputplumber_available = False
            return False

    def _apply_target_devices(self, target_mode, include_mouse=True):
        self.command_runner(
            self._busctl_args(
                "call",
                "org.shadowblip.InputPlumber",
                INPUTPLUMBER_DBUS_PATH,
                "org.shadowblip.Input.CompositeDevice",
                "SetTargetDevices",
                "as",
                *controller_targets.build_target_devices_busctl_args(
                    target_mode,
                    include_mouse=include_mouse,
                ),
            ),
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.get_env(),
        )
        self._inputplumber_available = True

    def _get_zotac_mouse_candidate_paths(self):
        input_class_path = Path("/sys/class/input")
        if not input_class_path.exists():
            return []

        return sorted(
            f"/dev/input/{path.name}"
            for path in input_class_path.glob("event*")
        )

    def _read_input_device_name(self, device_path):
        event_name = Path(device_path).name
        return self.read_text(f"/sys/class/input/{event_name}/device/name")

    def _resolve_zotac_mouse_device_path(self):
        for candidate_path in self._get_zotac_mouse_candidate_paths():
            try:
                device_name = self._read_input_device_name(candidate_path)
            except Exception:
                continue

            if device_name == ZOTAC_MOUSE_DEVICE_NAME:
                return candidate_path

        return None

    def _open_event_device(self, device_path):
        return os.open(device_path, os.O_RDONLY)

    def _close_event_device(self, fd):
        os.close(fd)

    def _set_event_device_grab(self, fd, grabbed):
        self._ioctl(fd, EVIOCGRAB, ctypes.c_int(1 if grabbed else 0))

    def _grab_zotac_mouse_device(self):
        if self._zotac_mouse_device_fd is not None:
            return True

        device_path = self._resolve_zotac_mouse_device_path()
        if not device_path:
            self.logger.warning("Unable to locate Zotac mouse input device for trackpad suppression.")
            return False

        fd = None
        try:
            fd = self._open_event_device(device_path)
            self._set_event_device_grab(fd, True)
            self._zotac_mouse_device_fd = fd
            self._zotac_mouse_device_path = device_path
            return True
        except Exception as error:
            if fd is not None:
                try:
                    self._close_event_device(fd)
                except Exception:
                    pass
            self.logger.warning(f"Failed to grab Zotac mouse input device: {error}")
            return False

    def _release_zotac_mouse_device(self):
        fd = self._zotac_mouse_device_fd
        if fd is None:
            return True

        released = True
        try:
            self._set_event_device_grab(fd, False)
        except Exception as error:
            self.logger.warning(f"Failed to release Zotac mouse input device: {error}")
            released = False
        finally:
            try:
                self._close_event_device(fd)
            except Exception:
                pass
            self._zotac_mouse_device_fd = None
            self._zotac_mouse_device_path = None

        return released

    def _restart_inputplumber(self):
        self.command_runner(
            self._systemctl_args("restart", "inputplumber"),
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.get_env(),
        )
        self._inputplumber_available = True

    def set_missing_glyph_fix_enabled(self, app_id, enabled):
        if app_id in (None, "", DEFAULT_APP_ID):
            return self._current_settings()

        self.settings_store.set_missing_glyph_fix_enabled(app_id, enabled)
        return self._current_settings()

    def set_missing_glyph_fix_trackpads_disabled(self, app_id, disabled):
        if app_id in (None, "", DEFAULT_APP_ID):
            return self._current_settings()

        self.settings_store.set_missing_glyph_fix_trackpads_disabled(app_id, disabled)
        return self._current_settings()

    async def sync_missing_glyph_fix_target(self, app_id):
        app_id = str(app_id or DEFAULT_APP_ID)
        glyph_fix_enabled = (
            app_id != DEFAULT_APP_ID
            and self.settings_store.get_missing_glyph_fix_enabled(app_id)
        )
        trackpads_disabled = (
            glyph_fix_enabled
            and self.settings_store.get_missing_glyph_fix_trackpads_disabled(app_id)
        )

        if glyph_fix_enabled:
            trackpad_result = (
                self._grab_zotac_mouse_device()
                if trackpads_disabled
                else self._release_zotac_mouse_device()
            )
            if self._temporary_target_mode == MISSING_GLYPH_FIX_TARGET:
                return trackpad_result

            try:
                self._apply_target_devices(MISSING_GLYPH_FIX_TARGET)
                self._temporary_target_mode = MISSING_GLYPH_FIX_TARGET
                return trackpad_result
            except subprocess.CalledProcessError as error:
                detail = (error.stderr or error.stdout or str(error)).strip()
                self.logger.warning(f"Failed to apply missing glyph fix: {detail}")
                return False
            except Exception as error:
                self.logger.warning(f"Failed to apply missing glyph fix: {error}")
                return False

        self._release_zotac_mouse_device()
        if self._temporary_target_mode != MISSING_GLYPH_FIX_TARGET:
            return False

        try:
            if self.settings_store.get_startup_apply_enabled():
                self._apply_target_devices(STARTUP_MODE)
            else:
                self._restart_inputplumber()
            self._temporary_target_mode = None
            return True
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or str(error)).strip()
            self.logger.warning(f"Failed to restore inherited controller target: {detail}")
            return False
        except Exception as error:
            self.logger.warning(f"Failed to restore inherited controller target: {error}")
            return False

    def _is_linux_platform(self):
        return sys.platform.startswith("linux")

    def _open_rumble_device(self, device_path):
        return os.open(device_path, os.O_RDWR)

    def _close_rumble_device(self, fd):
        os.close(fd)

    def _write_event_to_fd(self, fd, event):
        return os.write(fd, ctypes.string_at(ctypes.byref(event), ctypes.sizeof(event)))

    def _write_event_to_device(self, device_path, event):
        fd = self._open_rumble_device(device_path)
        try:
            self._write_event_to_fd(fd, event)
        finally:
            self._close_rumble_device(fd)

    def _ioctl(self, fd, request, arg):
        result = self._libc.ioctl(fd, request, arg)
        if result < 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error))
        return result

    def _build_input_event(self, event_type, code, value):
        event = _InputEvent()
        event.time.tv_sec = 0
        event.time.tv_usec = 0
        event.type = event_type
        event.code = code
        event.value = value
        return event

    def _build_gain_event(self, gain_percent):
        gain_value = int((gain_percent / 100.0) * 0xFFFF)
        return self._build_input_event(EV_FF, FF_GAIN, gain_value)

    def _build_preview_effect(self):
        effect = _FFEffect()
        effect.type = FF_RUMBLE
        effect.id = -1
        effect.direction = 0
        effect.trigger.button = 0
        effect.trigger.interval = 0
        effect.replay.length = RUMBLE_PREVIEW_DURATION_MS
        effect.replay.delay = 0
        effect.u.rumble.strong_magnitude = 0xFFFF
        effect.u.rumble.weak_magnitude = 0xFFFF
        return effect

    def _get_rumble_candidate_paths(self):
        by_id_path = Path("/dev/input/by-id")
        if not by_id_path.exists():
            return []

        return sorted(
            str(device)
            for device in by_id_path.iterdir()
            if "event-joystick" in device.name
        )

    def _resolve_rumble_candidate_path(self, candidate_path):
        return str(Path(candidate_path).resolve())

    def _read_rumble_candidate_device_name(self, resolved_path):
        event_name = Path(resolved_path).name
        return self.read_text(f"/sys/class/input/{event_name}/device/name")

    def _get_zotac_hid_config_paths(self):
        hidraw_class_path = Path("/sys/class/hidraw")
        if not hidraw_class_path.exists():
            return []

        return sorted(str(path / "device") for path in hidraw_class_path.glob("hidraw*/device"))

    def _is_zotac_hid_config_path(self, config_path):
        return Path(config_path, "save_config").is_file()

    def _resolve_zotac_hid_config_path(self):
        for config_path in self._get_zotac_hid_config_paths():
            if self._is_zotac_hid_config_path(config_path):
                return config_path

        return None

    def _has_zotac_hid_attribute(self, config_path, attribute_name):
        return Path(config_path, attribute_name).is_file()

    def _write_zotac_hid_value(self, path, value):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(value)

    def _resolve_rumble_device_path(self):
        candidates = []
        seen_paths = set()

        for candidate_path in self._get_rumble_candidate_paths():
            resolved_path = self._resolve_rumble_candidate_path(candidate_path)
            if not resolved_path or resolved_path in seen_paths:
                continue

            seen_paths.add(resolved_path)
            try:
                device_name = self._read_rumble_candidate_device_name(resolved_path)
            except Exception:
                device_name = ""

            candidates.append(
                {
                    "candidate_path": candidate_path,
                    "resolved_path": resolved_path,
                    "device_name": device_name,
                }
            )

        if not candidates:
            return None

        exact_zotac = [
            candidate
            for candidate in candidates
            if candidate["device_name"] == "ZOTAC Gaming Zone"
        ]
        if exact_zotac:
            return exact_zotac[0]["resolved_path"]

        zotac_matches = [
            candidate
            for candidate in candidates
            if "ZOTAC" in candidate["device_name"].upper()
            or "ZOTAC" in candidate["candidate_path"].upper()
            or "ZOTAC" in candidate["resolved_path"].upper()
        ]
        if zotac_matches:
            return zotac_matches[0]["resolved_path"]

        if len(candidates) == 1:
            return candidates[0]["resolved_path"]

        return None

    def _validate_rumble_device_path(self, device_path):
        if not device_path:
            return False

        try:
            fd = self._open_rumble_device(device_path)
        except OSError:
            return False
        else:
            self._close_rumble_device(fd)
            return True

    def probe_rumble_available(self):
        if not self._is_linux_platform():
            self._rumble_device_path = None
            self._rumble_available = False
            return False

        self._rumble_device_path = self._resolve_rumble_device_path()

        if not self._validate_rumble_device_path(self._rumble_device_path):
            self._rumble_device_path = None
            self._rumble_available = False
            return False

        self._rumble_available = True
        return self._rumble_available

    def set_startup_apply_enabled(self, enabled):
        enabled = self.settings_store.set_startup_apply_enabled(enabled)

        if enabled:
            if not self.is_supported_device():
                self._set_status("unsupported", UNSUPPORTED_MESSAGE)
            else:
                self._set_status("idle", DBUS_READY_MESSAGE)
        elif self._startup_applied_this_session:
            self._set_status("disabled", DISABLED_REBOOT_MESSAGE)
        else:
            self._set_status("disabled", DISABLED_MESSAGE)

        return self._current_settings()

    # TODO: Keep using the current FF_GAIN path for now. Zotac may also support
    # a native HID/sysfs method via save_config, vibration_intensity, and
    # motor_test; a future change could evaluate that path or add a
    # compatibility/testing switch between methods if needed.
    async def _apply_rumble_gain_once(self, device_path=None):
        device_path = device_path or self._rumble_device_path
        if not device_path:
            return False

        try:
            self._write_event_to_device(
                device_path,
                self._build_gain_event(self.settings_store.get_rumble_intensity()),
            )
            return True
        except OSError as error:
            self.logger.warning(f"Failed to apply rumble intensity: {error}")
            return False

    async def _play_rumble_preview_once(self, device_path=None):
        device_path = device_path or self._rumble_device_path
        if not device_path:
            return False

        effect = self._build_preview_effect()
        fd = None

        try:
            fd = self._open_rumble_device(device_path)
            self._ioctl(fd, EVIOCSFF, ctypes.byref(effect))
            self._write_event_to_fd(fd, self._build_input_event(EV_FF, effect.id, 1))
            await self.sleep(RUMBLE_PREVIEW_DURATION_MS / 1000.0)
            self._ioctl(fd, EVIOCRMFF, ctypes.c_int(effect.id))
            return True
        except OSError as error:
            self.logger.warning(f"Failed to play rumble preview: {error}")
            return False
        finally:
            try:
                self._close_rumble_device(fd)
            except Exception:
                pass

    async def _rumble_loop(self):
        while self._rumble_running:
            await self._apply_rumble_gain_once(self._rumble_device_path)
            await self.sleep(DEFAULT_RUMBLE_REAPPLY_INTERVAL_SECONDS)

    async def start_rumble_fixer(self):
        if self._rumble_task and not self._rumble_task.done():
            return True

        if not self.probe_rumble_available():
            return False

        self._rumble_running = True
        await self._apply_rumble_gain_once(self._rumble_device_path)
        self._rumble_task = asyncio.create_task(self._rumble_loop())
        return True

    async def stop_rumble_fixer(self):
        self._rumble_running = False

        if self._rumble_task and not self._rumble_task.done():
            self._rumble_task.cancel()
            try:
                await self._rumble_task
            except asyncio.CancelledError:
                pass

        self._rumble_task = None
        return True

    async def set_rumble_enabled(self, enabled):
        self.settings_store.set_rumble_enabled(enabled)

        if enabled:
            self._rumble_available = bool(await self.start_rumble_fixer())
        else:
            await self.stop_rumble_fixer()
            self._rumble_available = bool(self.probe_rumble_available())

        return self._current_settings()

    async def set_rumble_intensity(self, intensity):
        intensity = max(0, min(100, int(intensity)))
        self.settings_store.set_rumble_intensity(intensity)

        if self.settings_store.get_rumble_enabled():
            device_path = self._resolve_rumble_device_path()
            if self._validate_rumble_device_path(device_path):
                self._rumble_device_path = device_path
                self._rumble_available = True
                await self._apply_rumble_gain_once(device_path)
                await self._play_rumble_preview_once(device_path)
            else:
                self._rumble_device_path = None
                self._rumble_available = False

        return self._current_settings()

    async def test_rumble(self):
        intensity = max(0.0, min(1.0, self.settings_store.get_rumble_intensity() / 100.0))
        try:
            self.command_runner(
                self._busctl_args(
                    "call",
                    "org.shadowblip.InputPlumber",
                    INPUTPLUMBER_DBUS_PATH,
                    "org.shadowblip.Output.ForceFeedback",
                    "Rumble",
                    "d",
                    str(intensity),
                ),
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self.get_env(),
            )
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or str(error)).strip()
            self.logger.warning(f"Failed to send test rumble via InputPlumber: {detail}")
            return False
        except Exception as error:
            self.logger.warning(f"Failed to send test rumble via InputPlumber: {error}")
            return False

        await self.sleep(RUMBLE_PREVIEW_DURATION_MS / 1000.0)

        try:
            self.command_runner(
                self._busctl_args(
                    "call",
                    "org.shadowblip.InputPlumber",
                    INPUTPLUMBER_DBUS_PATH,
                    "org.shadowblip.Output.ForceFeedback",
                    "Stop",
                ),
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self.get_env(),
            )
            return True
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or str(error)).strip()
            self.logger.warning(f"Failed to stop test rumble via InputPlumber: {detail}")
            return False
        except Exception as error:
            self.logger.warning(f"Failed to stop test rumble via InputPlumber: {error}")
            return False

    async def wait_for_inputplumber_dbus(
        self,
        timeout=READY_TIMEOUT_SECONDS,
        interval=READY_POLL_INTERVAL_SECONDS,
    ):
        self._set_status("waiting", "Waiting for InputPlumber D-Bus.")
        elapsed = 0.0

        while elapsed < timeout:
            try:
                if self._probe_inputplumber_profile_name():
                    return True
            except Exception:
                self._inputplumber_available = False

            await self.sleep(interval)
            elapsed += interval

        self._inputplumber_available = False
        self._set_status(
            "failed",
            f"InputPlumber D-Bus was not ready within {timeout:.1f}s.",
        )
        return False

    async def apply_startup_mode(self):
        if not self.is_supported_device():
            self._set_status("unsupported", UNSUPPORTED_MESSAGE)
            return self.get_status()

        if not await self.wait_for_inputplumber_dbus():
            return self.get_status()

        self.log_privilege_context()

        try:
            self._apply_target_devices(STARTUP_MODE)
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or str(error)).strip()
            self._set_status("failed", f"Failed to apply startup mode: {detail}")
            return self.get_status()
        except Exception as error:
            self._set_status("failed", f"Failed to apply startup mode: {error}")
            return self.get_status()

        self._startup_applied_this_session = True
        self._set_status("applied", f"Startup mode re-applied: {STARTUP_MODE}.")
        return self.get_status()

    async def cleanup(self):
        self._release_zotac_mouse_device()
        await self.stop_rumble_fixer()


class Plugin:
    def __init__(self, service=None):
        self.loop = None
        self.startup_task = None
        self.service = service or DeckyZoneService()

    async def get_status(self):
        return self.service.get_status()

    async def get_settings(self):
        return self.service.get_settings()

    async def set_startup_apply_enabled(self, enabled):
        if not enabled and self.startup_task and not self.startup_task.done():
            self.startup_task.cancel()
            try:
                await self.startup_task
            except asyncio.CancelledError:
                pass
            self.startup_task = None

        return self.service.set_startup_apply_enabled(enabled)

    async def set_rumble_enabled(self, enabled):
        return await self.service.set_rumble_enabled(enabled)

    async def set_rumble_intensity(self, intensity):
        return await self.service.set_rumble_intensity(intensity)

    async def set_missing_glyph_fix_enabled(self, app_id, enabled):
        return self.service.set_missing_glyph_fix_enabled(app_id, enabled)

    async def set_missing_glyph_fix_trackpads_disabled(self, app_id, disabled):
        return self.service.set_missing_glyph_fix_trackpads_disabled(app_id, disabled)

    async def sync_missing_glyph_fix_target(self, app_id):
        return await self.service.sync_missing_glyph_fix_target(app_id)

    async def test_rumble(self):
        return await self.service.test_rumble()

    async def _main(self):
        self.loop = asyncio.get_event_loop()
        decky.logger.info("DeckyZone starting")
        settings = self.service.get_settings()
        if settings["rumbleEnabled"]:
            await self.service.start_rumble_fixer()
        if settings["startupApplyEnabled"]:
            self.startup_task = self.loop.create_task(self.service.apply_startup_mode())
        else:
            self.service.set_startup_apply_enabled(False)

    async def _unload(self):
        decky.logger.info("DeckyZone stopping")
        if self.startup_task and not self.startup_task.done():
            self.startup_task.cancel()
            try:
                await self.startup_task
            except asyncio.CancelledError:
                pass
        if hasattr(self.service, "cleanup"):
            await self.service.cleanup()
        else:
            await self.service.stop_rumble_fixer()

    async def _uninstall(self):
        decky.logger.info("DeckyZone uninstall")
        if hasattr(self.service, "cleanup"):
            await self.service.cleanup()
        else:
            await self.service.stop_rumble_fixer()

    async def _migration(self):
        decky.logger.info("Migrating DeckyZone")
        decky.migrate_logs(
            os.path.join(
                decky.DECKY_USER_HOME,
                ".config",
                "deckyzone",
                "deckyzone.log",
            )
        )
        decky.migrate_settings(
            os.path.join(decky.DECKY_HOME, "settings", "deckyzone.json"),
            os.path.join(decky.DECKY_USER_HOME, ".config", "deckyzone"),
        )
        decky.migrate_runtime(
            os.path.join(decky.DECKY_HOME, "deckyzone"),
            os.path.join(decky.DECKY_USER_HOME, ".local", "share", "deckyzone"),
        )
