import asyncio
import ctypes
import ctypes.util
import errno
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
DEFAULT_INPUTPLUMBER_PROFILE_PATH = "/usr/share/inputplumber/profiles/default.yaml"
ZOTAC_MOUSE_DEVICE_NAME = "ZOTAC Gaming Zone Mouse"
ZOTAC_KEYBOARD_DEVICE_NAME = "ZOTAC Gaming Zone Keyboard"
DEFAULT_RUMBLE_REAPPLY_INTERVAL_SECONDS = 2
DEFAULT_BRIGHTNESS_DIAL_RETRY_INTERVAL_SECONDS = 1
DEFAULT_BRIGHTNESS_DIAL_POLL_INTERVAL_SECONDS = 0.1
DEFAULT_HOME_BUTTON_RETRY_INTERVAL_SECONDS = 1
DEFAULT_HOME_BUTTON_POLL_INTERVAL_SECONDS = 0.1
RUMBLE_PREVIEW_DURATION_MS = 180
INPUTPLUMBER_KEYBOARD_DEVICE_NAME = "InputPlumber Keyboard"
EV_KEY = 0x01
EV_FF = 0x15
FF_RUMBLE = 0x50
FF_GAIN = 0x60
KEY_BRIGHTNESSDOWN = 224
KEY_BRIGHTNESSUP = 225
KEY_ZOTAC_SHORT_PRESS = 186
KEY_MORE_BUTTON = 187
KEY_HOME_SHORT_PRESS = 188
KEY_HOME_LONG_PRESS = 189


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
        self._startup_target_active = False
        self._temporary_target_mode = None
        self._zotac_mouse_device_fd = None
        self._zotac_mouse_device_path = None
        self._brightness_dial_device_path = None
        self._brightness_dial_task = None
        self._brightness_dial_running = False
        self._home_button_device_path = None
        self._home_button_task = None
        self._home_button_running = False
        self._home_button_override_active = False
        self._home_button_original_profile_path = None
        self._home_button_original_profile_yaml = None
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
            "homeButtonEnabled": self.settings_store.get_home_button_enabled(),
            "brightnessDialFixEnabled": self.settings_store.get_brightness_dial_fix_enabled(),
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

    def _parse_busctl_string_output(self, output):
        text = (output or "").strip()
        if not text:
            return ""

        if " " not in text:
            return text

        _, encoded_value = text.split(" ", 1)
        encoded_value = encoded_value.strip()
        if len(encoded_value) >= 2 and encoded_value[0] == encoded_value[-1] == '"':
            encoded_value = encoded_value[1:-1]

        return bytes(encoded_value, "utf-8").decode("unicode_escape")

    def _get_inputplumber_profile_path(self):
        result = self.command_runner(
            self._busctl_args(
                "get-property",
                "org.shadowblip.InputPlumber",
                INPUTPLUMBER_DBUS_PATH,
                "org.shadowblip.Input.CompositeDevice",
                "ProfilePath",
            ),
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.get_env(),
        )
        self._inputplumber_available = True
        return self._parse_busctl_string_output(result.stdout)

    def _get_inputplumber_profile_yaml(self):
        result = self.command_runner(
            self._busctl_args(
                "call",
                "org.shadowblip.InputPlumber",
                INPUTPLUMBER_DBUS_PATH,
                "org.shadowblip.Input.CompositeDevice",
                "GetProfileYaml",
            ),
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.get_env(),
        )
        self._inputplumber_available = True
        return self._parse_busctl_string_output(result.stdout)

    def _load_inputplumber_profile_path(self, profile_path):
        self.command_runner(
            self._busctl_args(
                "call",
                "org.shadowblip.InputPlumber",
                INPUTPLUMBER_DBUS_PATH,
                "org.shadowblip.Input.CompositeDevice",
                "LoadProfilePath",
                "s",
                profile_path,
            ),
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.get_env(),
        )
        self._inputplumber_available = True

    def _load_inputplumber_profile_from_yaml(self, profile_yaml):
        self.command_runner(
            self._busctl_args(
                "call",
                "org.shadowblip.InputPlumber",
                INPUTPLUMBER_DBUS_PATH,
                "org.shadowblip.Input.CompositeDevice",
                "LoadProfileFromYaml",
                "s",
                profile_yaml,
            ),
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.get_env(),
        )
        self._inputplumber_available = True

    def _build_home_button_mapping_lines(self, indent):
        return [
            f"{indent}- name: QuickAccess2",
            f"{indent}  source_event:",
            f"{indent}    gamepad:",
            f"{indent}      button: QuickAccess2",
            f"{indent}  target_events:",
            f"{indent}    - keyboard: KeyF18",
        ]

    def _build_home_button_override_profile_yaml(self, profile_yaml):
        lines = profile_yaml.splitlines()
        trailing_newline = profile_yaml.endswith("\n")
        quick_access_index = None
        quick_access_indent = ""

        for index, line in enumerate(lines):
            stripped = line.lstrip()
            if not stripped.startswith("- name:"):
                continue

            if stripped.split(":", 1)[1].strip() != "QuickAccess2":
                continue

            quick_access_index = index
            quick_access_indent = line[: len(line) - len(stripped)]
            break

        if quick_access_index is not None:
            end_index = len(lines)
            for index in range(quick_access_index + 1, len(lines)):
                stripped = lines[index].lstrip()
                indent = lines[index][: len(lines[index]) - len(stripped)]
                if stripped.startswith("- name:") and indent == quick_access_indent:
                    end_index = index
                    break

            lines = (
                lines[:quick_access_index]
                + self._build_home_button_mapping_lines(quick_access_indent)
                + lines[end_index:]
            )
        else:
            mapping_indent = ""
            insert_index = len(lines)
            for index, line in enumerate(lines):
                if line.strip() == "mapping:":
                    mapping_indent = line[: len(line) - len(line.lstrip())]
                    insert_index = len(lines)
                    break
            else:
                lines.append("mapping:")
                insert_index = len(lines)

            lines.extend(self._build_home_button_mapping_lines(f"{mapping_indent}  "))

        override_yaml = "\n".join(lines)
        if trailing_newline or not override_yaml.endswith("\n"):
            override_yaml = f"{override_yaml}\n"
        return override_yaml

    def _ensure_home_button_original_profile(self):
        if self._home_button_original_profile_yaml is not None:
            return True

        self._home_button_original_profile_path = self._get_inputplumber_profile_path() or None
        self._home_button_original_profile_yaml = self._get_inputplumber_profile_yaml()
        return True

    def _load_home_button_override_profile(self):
        self._ensure_home_button_original_profile()
        base_profile_yaml = self._home_button_original_profile_yaml or ""
        override_profile_yaml = self._build_home_button_override_profile_yaml(base_profile_yaml)
        self._load_inputplumber_profile_from_yaml(override_profile_yaml)
        self._home_button_override_active = True
        return True

    def _restore_home_button_profile(self):
        if not self._home_button_override_active:
            return True

        if self._home_button_original_profile_path:
            self._load_inputplumber_profile_path(self._home_button_original_profile_path)
        elif self._home_button_original_profile_yaml:
            self._load_inputplumber_profile_from_yaml(self._home_button_original_profile_yaml)
        else:
            self._load_inputplumber_profile_path(DEFAULT_INPUTPLUMBER_PROFILE_PATH)

        self._home_button_override_active = False
        self._home_button_original_profile_path = None
        self._home_button_original_profile_yaml = None
        return True

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

    def _resolve_zotac_keyboard_device_path(self):
        for candidate_path in self._get_zotac_mouse_candidate_paths():
            try:
                device_name = self._read_input_device_name(candidate_path)
            except Exception:
                continue

            if device_name == ZOTAC_KEYBOARD_DEVICE_NAME:
                return candidate_path

        return None

    def _open_event_device(self, device_path):
        return os.open(device_path, os.O_RDONLY)

    def _open_nonblocking_event_device(self, device_path):
        return os.open(device_path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))

    def _close_event_device(self, fd):
        os.close(fd)

    def _resolve_inputplumber_keyboard_device_path(self):
        for candidate_path in self._get_zotac_mouse_candidate_paths():
            try:
                device_name = self._read_input_device_name(candidate_path)
            except Exception:
                continue

            if device_name == INPUTPLUMBER_KEYBOARD_DEVICE_NAME:
                return candidate_path

        return None

    def _read_input_event_from_fd(self, fd):
        raw_event = os.read(fd, ctypes.sizeof(_InputEvent))
        if len(raw_event) != ctypes.sizeof(_InputEvent):
            raise OSError("Incomplete input event read.")
        return _InputEvent.from_buffer_copy(raw_event)

    def _get_brightness_dial_direction(self, event):
        if event.type != EV_KEY or event.value != 1:
            return None

        if event.code == KEY_BRIGHTNESSUP:
            return "up"
        if event.code == KEY_BRIGHTNESSDOWN:
            return "down"
        return None

    async def _handle_brightness_dial_input_event(self, event):
        direction = self._get_brightness_dial_direction(event)
        if not direction:
            return False

        try:
            await decky.emit("brightness_dial_input", direction)
            return True
        except Exception as error:
            self.logger.warning(f"Failed to emit brightness dial input: {error}")
            return False

    def _is_home_short_press(self, event):
        return (
            event.type == EV_KEY
            and event.value == 1
            and event.code == KEY_HOME_SHORT_PRESS
        )

    async def _handle_home_button_input_event(self, event):
        if not self._is_home_short_press(event):
            return False

        try:
            await decky.emit("zotac_home_short_pressed")
            return True
        except Exception as error:
            self.logger.warning(f"Failed to emit Home short press: {error}")
            return False

    async def _home_button_loop(self):
        while self._home_button_running:
            device_path = self._resolve_inputplumber_keyboard_device_path()
            self._home_button_device_path = device_path

            if not device_path:
                await self.sleep(DEFAULT_HOME_BUTTON_RETRY_INTERVAL_SECONDS)
                continue

            fd = None
            try:
                fd = self._open_nonblocking_event_device(device_path)
                while self._home_button_running:
                    try:
                        event = self._read_input_event_from_fd(fd)
                    except BlockingIOError:
                        await self.sleep(DEFAULT_HOME_BUTTON_POLL_INTERVAL_SECONDS)
                        continue
                    except OSError as error:
                        if error.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                            await self.sleep(DEFAULT_HOME_BUTTON_POLL_INTERVAL_SECONDS)
                            continue
                        raise

                    await self._handle_home_button_input_event(event)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self.logger.warning(
                    f"Home button listener lost InputPlumber Keyboard device: {error}"
                )
            finally:
                if fd is not None:
                    try:
                        self._close_event_device(fd)
                    except Exception:
                        pass
                self._home_button_device_path = None

            if self._home_button_running:
                await self.sleep(DEFAULT_HOME_BUTTON_RETRY_INTERVAL_SECONDS)

    async def start_home_button_listener(self):
        if not self._is_linux_platform():
            return False

        if self._home_button_task and not self._home_button_task.done():
            return True

        self._home_button_running = True
        self._home_button_task = asyncio.create_task(self._home_button_loop())
        return True

    async def stop_home_button_listener(self):
        self._home_button_running = False

        if self._home_button_task and not self._home_button_task.done():
            self._home_button_task.cancel()
            try:
                await self._home_button_task
            except asyncio.CancelledError:
                pass

        self._home_button_task = None
        self._home_button_device_path = None
        return True

    async def _enable_home_button_navigation(self):
        try:
            self._load_home_button_override_profile()
            await self.start_home_button_listener()
            return True
        except Exception as error:
            self.logger.warning(f"Failed to enable Home button navigation: {error}")
            try:
                await self.stop_home_button_listener()
            except Exception:
                pass
            try:
                self._restore_home_button_profile()
            except Exception as restore_error:
                self.logger.warning(
                    f"Failed to restore Home button profile after error: {restore_error}"
                )
            return False

    async def _disable_home_button_navigation(self):
        try:
            await self.stop_home_button_listener()
            self._restore_home_button_profile()
            return True
        except Exception as error:
            self.logger.warning(f"Failed to disable Home button navigation: {error}")
            return False

    def _should_enable_home_button_navigation(self):
        return self.settings_store.get_home_button_enabled() and (
            self._startup_target_active
            or self._temporary_target_mode == MISSING_GLYPH_FIX_TARGET
        )

    async def _sync_home_button_navigation_state(self):
        if self._should_enable_home_button_navigation():
            return await self._enable_home_button_navigation()

        return await self._disable_home_button_navigation()

    async def sync_home_button_navigation_state(self):
        return await self._sync_home_button_navigation_state()

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
                await self._sync_home_button_navigation_state()
                return trackpad_result

            try:
                if not await self.wait_for_inputplumber_dbus_silently():
                    return False
                self._apply_target_devices(MISSING_GLYPH_FIX_TARGET)
                self._temporary_target_mode = MISSING_GLYPH_FIX_TARGET
                await self._sync_home_button_navigation_state()
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
            await self._sync_home_button_navigation_state()
            return False

        try:
            if self.settings_store.get_startup_apply_enabled():
                if not await self.wait_for_inputplumber_dbus_silently():
                    return False
                self._apply_target_devices(STARTUP_MODE)
                self._startup_target_active = True
            else:
                self._restart_inputplumber()
                self._startup_target_active = False
            self._temporary_target_mode = None
            await self._sync_home_button_navigation_state()
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

    async def disable_startup_target_runtime(self):
        self._startup_target_active = False

        if self._temporary_target_mode == MISSING_GLYPH_FIX_TARGET:
            await self._sync_home_button_navigation_state()
            return False

        try:
            self._restart_inputplumber()
            await self._sync_home_button_navigation_state()
            self._set_status("disabled", DISABLED_MESSAGE)
            return True
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or str(error)).strip()
            self.logger.warning(f"Failed to restore inherited controller target: {detail}")
            return False
        except Exception as error:
            self.logger.warning(f"Failed to restore inherited controller target: {error}")
            return False

    async def set_home_button_enabled(self, enabled):
        self.settings_store.set_home_button_enabled(enabled)
        await self._sync_home_button_navigation_state()
        return self._current_settings()

    async def _brightness_dial_loop(self):
        while self._brightness_dial_running:
            device_path = self._resolve_inputplumber_keyboard_device_path()
            self._brightness_dial_device_path = device_path

            if not device_path:
                await self.sleep(DEFAULT_BRIGHTNESS_DIAL_RETRY_INTERVAL_SECONDS)
                continue

            fd = None
            try:
                fd = self._open_nonblocking_event_device(device_path)
                while self._brightness_dial_running:
                    try:
                        event = self._read_input_event_from_fd(fd)
                    except BlockingIOError:
                        await self.sleep(DEFAULT_BRIGHTNESS_DIAL_POLL_INTERVAL_SECONDS)
                        continue
                    except OSError as error:
                        if error.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                            await self.sleep(DEFAULT_BRIGHTNESS_DIAL_POLL_INTERVAL_SECONDS)
                            continue
                        raise

                    await self._handle_brightness_dial_input_event(event)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self.logger.warning(
                    f"Brightness dial listener lost InputPlumber Keyboard device: {error}"
                )
            finally:
                if fd is not None:
                    try:
                        self._close_event_device(fd)
                    except Exception:
                        pass
                self._brightness_dial_device_path = None

            if self._brightness_dial_running:
                await self.sleep(DEFAULT_BRIGHTNESS_DIAL_RETRY_INTERVAL_SECONDS)

    async def start_brightness_dial_fixer(self):
        if self._brightness_dial_task and not self._brightness_dial_task.done():
            return True

        self._brightness_dial_running = True
        self._brightness_dial_task = asyncio.create_task(self._brightness_dial_loop())
        return True

    async def stop_brightness_dial_fixer(self):
        self._brightness_dial_running = False

        if self._brightness_dial_task and not self._brightness_dial_task.done():
            self._brightness_dial_task.cancel()
            try:
                await self._brightness_dial_task
            except asyncio.CancelledError:
                pass

        self._brightness_dial_task = None
        self._brightness_dial_device_path = None
        return True

    async def set_brightness_dial_fix_enabled(self, enabled):
        self.settings_store.set_brightness_dial_fix_enabled(enabled)

        if enabled:
            await self.start_brightness_dial_fixer()
        else:
            await self.stop_brightness_dial_fixer()

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
        return await self._wait_for_inputplumber_dbus(
            timeout=timeout,
            interval=interval,
            update_status=True,
        )

    async def wait_for_inputplumber_dbus_silently(
        self,
        timeout=READY_TIMEOUT_SECONDS,
        interval=READY_POLL_INTERVAL_SECONDS,
    ):
        return await self._wait_for_inputplumber_dbus(
            timeout=timeout,
            interval=interval,
            update_status=False,
        )

    async def _wait_for_inputplumber_dbus(
        self,
        timeout=READY_TIMEOUT_SECONDS,
        interval=READY_POLL_INTERVAL_SECONDS,
        update_status=True,
    ):
        if update_status:
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
        if update_status:
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
        self._startup_target_active = True
        await self._sync_home_button_navigation_state()
        self._set_status("applied", f"Startup mode re-applied: {STARTUP_MODE}.")
        return self.get_status()

    async def cleanup(self):
        self._startup_target_active = False
        self._temporary_target_mode = None
        await self._sync_home_button_navigation_state()
        await self.stop_brightness_dial_fixer()
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

        settings = self.service.set_startup_apply_enabled(enabled)
        if enabled and hasattr(self.service, "apply_startup_mode"):
            await self.service.apply_startup_mode()
        elif not enabled and hasattr(self.service, "disable_startup_target_runtime"):
            await self.service.disable_startup_target_runtime()
        if hasattr(self.service, "sync_home_button_navigation_state"):
            await self.service.sync_home_button_navigation_state()
        return settings

    async def set_home_button_enabled(self, enabled):
        return await self.service.set_home_button_enabled(enabled)

    async def set_rumble_enabled(self, enabled):
        return await self.service.set_rumble_enabled(enabled)

    async def set_rumble_intensity(self, intensity):
        return await self.service.set_rumble_intensity(intensity)

    async def set_brightness_dial_fix_enabled(self, enabled):
        return await self.service.set_brightness_dial_fix_enabled(enabled)

    async def set_missing_glyph_fix_enabled(self, app_id, enabled):
        return self.service.set_missing_glyph_fix_enabled(app_id, enabled)

    async def set_missing_glyph_fix_trackpads_disabled(self, app_id, disabled):
        return self.service.set_missing_glyph_fix_trackpads_disabled(app_id, disabled)

    async def sync_missing_glyph_fix_target(self, app_id):
        if self.startup_task is not None:
            try:
                await self.startup_task
            except asyncio.CancelledError:
                pass
            finally:
                if self.startup_task.done():
                    self.startup_task = None
        return await self.service.sync_missing_glyph_fix_target(app_id)

    async def test_rumble(self):
        return await self.service.test_rumble()

    async def _main(self):
        self.loop = asyncio.get_event_loop()
        decky.logger.info("DeckyZone starting")
        settings = self.service.get_settings()
        if settings["brightnessDialFixEnabled"]:
            await self.service.start_brightness_dial_fixer()
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
            if hasattr(self.service, "stop_brightness_dial_fixer"):
                await self.service.stop_brightness_dial_fixer()
            await self.service.stop_rumble_fixer()

    async def _uninstall(self):
        decky.logger.info("DeckyZone uninstall")
        if hasattr(self.service, "cleanup"):
            await self.service.cleanup()
        else:
            if hasattr(self.service, "stop_brightness_dial_fixer"):
                await self.service.stop_brightness_dial_fixer()
            await self.service.stop_rumble_fixer()
        plugin_settings.reset_settings()

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
