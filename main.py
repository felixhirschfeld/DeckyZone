import asyncio
import ctypes
import ctypes.util
import errno
import json
import os
import select
import subprocess
import sys
import time
from pathlib import Path

import decky
import controller_targets
import gamescope_display_profiles as gamescope_display_profiles_module
import inputplumber_target_sync
import plugin_update
import plugin_settings
import runtime_profile_utils
import trackpad_modes

gamescope_display_profiles = gamescope_display_profiles_module


SUPPORTED_BOARDS = {"G0A1W", "G1A1W"}
INPUTPLUMBER_DBUS_PATH = "/org/shadowblip/InputPlumber/CompositeDevice0"
DMI_SYS_VENDOR_PATH = "/sys/devices/virtual/dmi/id/sys_vendor"
DMI_PRODUCT_NAME_PATH = "/sys/devices/virtual/dmi/id/product_name"
DMI_BOARD_NAME_PATH = "/sys/devices/virtual/dmi/id/board_name"
DMI_BOARD_VENDOR_PATH = "/sys/devices/virtual/dmi/id/board_vendor"
DMI_PATHS = (
    DMI_SYS_VENDOR_PATH,
    DMI_PRODUCT_NAME_PATH,
    DMI_BOARD_NAME_PATH,
    DMI_BOARD_VENDOR_PATH,
)
OS_RELEASE_CANDIDATE_PATHS = ("/etc/os-release", "/usr/lib/os-release")
ZOTAC_ZONE_PLATFORM_MODULE_PATH = "/sys/module/zotac_zone_platform"
ZOTAC_ZONE_HID_MODULE_PATH = "/sys/module/zotac_zone_hid"
FIRMWARE_ATTRIBUTES_CLASS_MODULE_PATH = "/sys/module/firmware_attributes_class"
FIRMWARE_ATTRIBUTES_NODE_PATH = "/sys/class/firmware-attributes/zotac_zone_platform"
ZOTAC_HID_CONFIG_SEARCH_ROOT = "/sys/class/hidraw/hidraw*/device"
ZOTAC_HID_CONFIG_MATCH_MARKER = "save_config"
ZOTAC_CONTROLLER_VENDOR_IDS = {"1ee9", "1e19"}
ZOTAC_CONTROLLER_PRODUCT_ID = "1590"
ZOTAC_CONTROLLER_INTERFACE_NUM = "03"
ZOTAC_RAW_REPORT_SIZE = 64
ZOTAC_RAW_HEADER_TAG = 0xE1
ZOTAC_RAW_PAYLOAD_SIZE = 0x3C
ZOTAC_RAW_CMD_SET_BUTTON_MAPPING = 0xA1
ZOTAC_RAW_CMD_GET_BUTTON_MAPPING = 0xA2
ZOTAC_RAW_CMD_SET_PROFILE = 0xB1
ZOTAC_RAW_CMD_GET_PROFILE = 0xB2
ZOTAC_CONTROLLER_MODE_GAMEPAD = "gamepad"
ZOTAC_CONTROLLER_MODE_DESKTOP = "desktop"
ZOTAC_CONTROLLER_MODE_TO_PROFILE = {
    ZOTAC_CONTROLLER_MODE_GAMEPAD: 0,
    ZOTAC_CONTROLLER_MODE_DESKTOP: 1,
}
ZOTAC_PROFILE_TO_CONTROLLER_MODE = {
    0: ZOTAC_CONTROLLER_MODE_GAMEPAD,
    1: ZOTAC_CONTROLLER_MODE_DESKTOP,
}
ZOTAC_RAW_REPLY_TIMEOUT_SECONDS = 1.0
DBUS_READY_MESSAGE = "Waiting to apply startup mode."
UNSUPPORTED_MESSAGE = "Unsupported device: startup mode only applies on Zotac Zone."
DISABLED_MESSAGE = "Startup mode apply is disabled."
DISABLED_REBOOT_MESSAGE = (
    "Startup mode apply is disabled. Reboot to restore unmodified InputPlumber startup behavior."
)
GAMEPAD_MODE_REQUIRED_MESSAGE = "Gamepad mode is required for controller features."
CONTROLLER_RUNTIME_RECOVERED_MESSAGE = "Controller runtime recovered."
RECOVERABLE_CONTROLLER_STATUS_FAILURE_DETAILS = (
    "InputPlumber target devices did not settle",
    "InputPlumber target gamepad device did not appear",
    "Startup runtime did not reach keyboard/profile-ready state.",
    "Home button runtime profile did not activate.",
)
READY_TIMEOUT_SECONDS = 5.0
READY_POLL_INTERVAL_SECONDS = 0.5
STARTUP_APPLY_ATTEMPTS = 3
STARTUP_APPLY_BACKOFF_SECONDS = 2.0
STARTUP_RUNTIME_READY_TIMEOUT_SECONDS = 4.0
STARTUP_RUNTIME_READY_POLL_INTERVAL_SECONDS = 0.25
CONTROLLER_MODE_MONITOR_INTERVAL_SECONDS = 2.0
DEFAULT_APP_ID = "0"
STARTUP_MODE = "deck-uhid"
STARTUP_MODE_APPLIED_MESSAGE = f"Startup mode re-applied: {STARTUP_MODE}."
MISSING_GLYPH_FIX_TARGET = "xbox-elite"
PER_GAME_REMAP_NONE = "none"
PER_GAME_REMAP_SOURCE_BUTTON_M1 = "LeftPaddle1"
PER_GAME_REMAP_SOURCE_BUTTON_M2 = "RightPaddle1"
PER_GAME_REMAP_TARGET_TO_INPUTPLUMBER_BUTTON = {
    "a": "South",
    "b": "East",
    "x": "West",
    "y": "North",
    "select": "Select",
    "start": "Start",
    "lb": "LeftBumper",
    "rb": "RightBumper",
    "lt": "LeftTrigger",
    "rt": "RightTrigger",
    "ls": "LeftStick",
    "rs": "RightStick",
    "dpad_up": "DPadUp",
    "dpad_down": "DPadDown",
    "dpad_left": "DPadLeft",
    "dpad_right": "DPadRight",
}
RUNTIME_PROFILE_HOME_BUTTON_MAPPING_NAME = "DeckyZone Home Button"
RUNTIME_PROFILE_M1_MAPPING_NAME = "DeckyZone M1 Remap"
RUNTIME_PROFILE_M2_MAPPING_NAME = "DeckyZone M2 Remap"
DEFAULT_INPUTPLUMBER_PROFILE_PATH = "/usr/share/inputplumber/profiles/default.yaml"
RUNTIME_INPUTPLUMBER_PROFILE_FILENAME = "inputplumber-runtime-profile.yaml"
HOME_BUTTON_OVERRIDE_PROFILE_FILENAME = "inputplumber-home-button-profile.yaml"
MANAGED_INPUTPLUMBER_CAPABILITY_MAPS_DIR = Path("/etc/inputplumber/capability_maps.d")
MANAGED_INPUTPLUMBER_DEVICES_DIR = Path("/etc/inputplumber/devices.d")
MANAGED_DIRECTIONAL_TRACKPAD_CAPABILITY_MAP_FILENAME = (
    "50-deckyzone-zone-trackpad-directional.yaml"
)
MANAGED_DIRECTIONAL_TRACKPAD_DEVICE_OVERRIDE_FILENAME = "50-zotac-zone.yaml"
DIRECTIONAL_TRACKPAD_BACKUP_FILENAME = "directional-trackpad-backup.json"
ZOTAC_MOUSE_DEVICE_NAME = "ZOTAC Gaming Zone Mouse"
ZOTAC_KEYBOARD_DEVICE_NAME = "ZOTAC Gaming Zone Keyboard"
ZOTAC_DIALS_DEVICE_NAME = "ZOTAC Gaming Zone Dials"
DEFAULT_RUMBLE_REAPPLY_INTERVAL_SECONDS = 2
DEFAULT_BRIGHTNESS_DIAL_RETRY_INTERVAL_SECONDS = 1
DEFAULT_BRIGHTNESS_DIAL_POLL_INTERVAL_SECONDS = 0.1
DEFAULT_HOME_BUTTON_RETRY_INTERVAL_SECONDS = 1
DEFAULT_HOME_BUTTON_POLL_INTERVAL_SECONDS = 0.1
RUMBLE_PREVIEW_DURATION_MS = 180
INPUTPLUMBER_KEYBOARD_DEVICE_NAME = "InputPlumber Keyboard"
EV_KEY = 0x01
EV_REL = 0x02
EV_FF = 0x15
FF_RUMBLE = 0x50
FF_GAIN = 0x60
REL_HWHEEL = 0x06
REL_WHEEL = 0x08
KEY_BRIGHTNESSDOWN = 224
KEY_BRIGHTNESSUP = 225
KEY_ZOTAC_SHORT_PRESS = 186
KEY_MORE_BUTTON = 187
KEY_HOME_SHORT_PRESS = 188
KEY_HOME_LONG_PRESS = 189


def _log_cleanup_step(logger, step):
    elapsed = step.get("elapsedSeconds")
    elapsed_text = ""
    if isinstance(elapsed, (int, float)):
        elapsed_text = f" elapsed={elapsed:.3f}s"

    message = step.get("message") or ""
    message_text = f" message={message}" if message else ""
    status = "ok=True" if step.get("ok") else "ok=False"
    changed = step.get("changed")
    log_message = (
        f"DeckyZone cleanup step {step.get('name')} finished: "
        f"{status} changed={changed}{elapsed_text}{message_text}"
    )

    if step.get("ok"):
        logger.info(log_message)
    else:
        logger.warning(log_message)


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
        gamescope_display_profiles=None,
    ):
        self.command_runner = command_runner
        self.sleep = sleep
        self.logger = logger
        self.read_text = read_text or self._read_text
        self.settings_store = settings_store
        self.gamescope_display_profiles = (
            gamescope_display_profiles
            or gamescope_display_profiles_module.GamescopeDisplayProfiles(
                user_home=decky.DECKY_USER_HOME,
                plugin_dir=decky.DECKY_PLUGIN_DIR,
            )
        )
        self._status = {"state": "idle", "message": DBUS_READY_MESSAGE}
        self._privilege_context_logged = False
        self._inputplumber_available = False
        self._startup_applied_this_session = False
        self._startup_target_active = False
        self._temporary_target_mode = None
        self._active_per_game_app_id = DEFAULT_APP_ID
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
        self._runtime_input_profile_active = False
        self._runtime_input_profile_original_profile_path = None
        self._runtime_input_profile_original_profile_yaml = None
        self._rumble_available = False
        self._rumble_device_path = None
        self._rumble_task = None
        self._rumble_running = False
        self._controller_mode_monitor_task = None
        self._controller_mode_monitor_running = False
        self._directional_trackpad_backup = None
        self._zotac_raw_command_seq = 0
        self._libc = ctypes.CDLL(ctypes.util.find_library("c") or None, use_errno=True)

    def get_status(self):
        self._clear_recovered_controller_status()
        return dict(self._status)

    def _is_recoverable_controller_status_failure(self):
        if self._status.get("state") != "failed":
            return False

        message = str(self._status.get("message") or "")
        if message.startswith("InputPlumber D-Bus was not ready within "):
            return True

        prefix = "Failed to apply startup mode: "
        if not message.startswith(prefix):
            return False

        detail = message[len(prefix) :]
        return any(
            detail.startswith(recoverable_detail)
            for recoverable_detail in RECOVERABLE_CONTROLLER_STATUS_FAILURE_DETAILS
        )

    def _is_active_button_prompt_fix_enabled(self):
        app_id = str(self._active_per_game_app_id or DEFAULT_APP_ID)
        return bool(
            app_id != DEFAULT_APP_ID
            and self.settings_store.get_per_game_settings_enabled(app_id)
            and self.settings_store.get_button_prompt_fix_enabled(app_id)
        )

    def _get_current_controller_target_mode(self):
        if self._is_active_button_prompt_fix_enabled():
            return MISSING_GLYPH_FIX_TARGET

        return STARTUP_MODE

    def _resolve_controller_target_gamepad_device_path(self, target_mode):
        return self._resolve_input_device_path_by_match(
            lambda device_name: controller_targets.is_target_gamepad_device_name(
                target_mode,
                device_name,
            )
        )

    def _is_current_controller_runtime_healthy(self):
        if not self.settings_store.get_startup_apply_enabled():
            return False

        if not self.probe_inputplumber_available():
            return False

        controller_mode_snapshot = self._get_controller_mode_snapshot()
        if not self._is_controller_mode_snapshot_safe(controller_mode_snapshot):
            return False

        target_mode = self._get_current_controller_target_mode()
        target_paths = self._get_inputplumber_target_device_paths()
        expected_target_count = len(
            controller_targets.build_target_devices(
                target_mode,
                include_mouse=self._should_include_mouse_target(),
            )
        )
        if len(target_paths) < expected_target_count:
            return False

        if not self._resolve_controller_target_gamepad_device_path(target_mode):
            return False

        if not self._resolve_inputplumber_keyboard_device_path():
            return False

        if self.settings_store.get_home_button_enabled():
            return self._get_inputplumber_profile_path() == str(
                self._get_home_button_override_profile_path()
            )

        if self._should_enable_runtime_input_profile(self._active_per_game_app_id):
            return self._get_inputplumber_profile_path() == str(
                self._get_runtime_inputplumber_profile_path()
            )

        return True

    def _clear_recovered_controller_status(self):
        if not self._is_recoverable_controller_status_failure():
            return

        previous_message = str(self._status.get("message") or "")
        try:
            if not self._is_current_controller_runtime_healthy():
                return
        except Exception as error:
            self.logger.warning(f"Failed to check recovered controller runtime: {error}")
            return

        self._set_status("applied", CONTROLLER_RUNTIME_RECOVERED_MESSAGE)
        self.logger.info(
            f"Cleared recovered controller startup failure: {previous_message}"
        )

    def get_settings(self):
        self._inputplumber_available = bool(self.probe_inputplumber_available())
        self._rumble_available = bool(self.probe_rumble_available())
        return self._current_settings()

    def get_debug_info(self):
        status = self.get_status()
        inputplumber_available = bool(self.probe_inputplumber_available())
        inputplumber_version = self._get_binary_version("inputplumber")
        gamescope_version = self._get_binary_version("gamescope")
        controller_mode_snapshot = self._get_controller_mode_snapshot()
        profile_name = None
        profile_path = None
        target_gamepad_path = None
        keyboard_path = None
        display_profile_settings = self._get_display_profile_settings()
        gamescope_paths = self._get_gamescope_support_paths()

        if inputplumber_available:
            try:
                profile_name = self._get_inputplumber_profile_name() or None
            except Exception:
                profile_name = None

            try:
                profile_path = self._get_inputplumber_profile_path() or None
            except Exception:
                profile_path = None

            try:
                target_gamepad_path = self._resolve_startup_gamepad_device_path() or None
            except Exception:
                target_gamepad_path = None

            try:
                keyboard_path = self._resolve_inputplumber_keyboard_device_path() or None
            except Exception:
                keyboard_path = None

        controller_runtime_state = self._get_controller_runtime_state(
            inputplumber_available=inputplumber_available,
            controller_mode_snapshot=controller_mode_snapshot,
            target_gamepad_path=target_gamepad_path,
            keyboard_path=keyboard_path,
        )

        return {
            "deviceIdentity": {
                "vendorName": self._read_optional_text(DMI_SYS_VENDOR_PATH),
                "productName": self._read_optional_text(DMI_PRODUCT_NAME_PATH),
                "boardName": self._read_optional_text(DMI_BOARD_NAME_PATH),
                "boardVendor": self._read_optional_text(DMI_BOARD_VENDOR_PATH),
                "supportedDevice": self.is_supported_device(),
                "dmiPaths": list(DMI_PATHS),
            },
            "osContext": {
                "prettyName": self._get_os_pretty_name(),
                "kernelRelease": self._get_kernel_release(),
                "osReleaseCandidatePaths": list(OS_RELEASE_CANDIDATE_PATHS),
            },
            "inputPlumber": {
                "available": inputplumber_available,
                "version": inputplumber_version,
                "profileName": profile_name,
                "profilePath": profile_path,
                "controllerMode": controller_mode_snapshot["mode"],
                "controllerModeAvailable": controller_mode_snapshot["available"],
                "targetGamepadPresent": target_gamepad_path is not None,
                "targetGamepadPath": target_gamepad_path,
                "keyboardPresent": keyboard_path is not None,
                "keyboardPath": keyboard_path,
                "controllerRuntimeState": controller_runtime_state,
                "compositeDeviceObjectPath": INPUTPLUMBER_DBUS_PATH,
            },
            "zotacZoneKernelDrivers": {
                "zotacZonePlatformLoaded": self._path_exists(ZOTAC_ZONE_PLATFORM_MODULE_PATH),
                "zotacZonePlatformPath": ZOTAC_ZONE_PLATFORM_MODULE_PATH,
                "zotacZoneHidLoaded": self._path_exists(ZOTAC_ZONE_HID_MODULE_PATH),
                "zotacZoneHidPath": ZOTAC_ZONE_HID_MODULE_PATH,
                "firmwareAttributesClassLoaded": self._path_exists(
                    FIRMWARE_ATTRIBUTES_CLASS_MODULE_PATH
                ),
                "firmwareAttributesClassPath": FIRMWARE_ATTRIBUTES_CLASS_MODULE_PATH,
                "firmwareAttributesNodePresent": self._path_exists(
                    FIRMWARE_ATTRIBUTES_NODE_PATH
                ),
                "firmwareAttributesNodePath": FIRMWARE_ATTRIBUTES_NODE_PATH,
                "hidConfigNodePath": self._resolve_zotac_hid_config_path(),
                "hidConfigSearchRoot": ZOTAC_HID_CONFIG_SEARCH_ROOT,
                "hidConfigMatchMarker": ZOTAC_HID_CONFIG_MATCH_MARKER,
            },
            "gamescope": {
                "version": gamescope_version,
                "builtInAvailable": bool(display_profile_settings["gamescopeZotacProfileBuiltIn"]),
                "managedProfileInstalled": bool(display_profile_settings["gamescopeZotacProfileInstalled"]),
                "greenTintFixEnabled": bool(display_profile_settings["gamescopeGreenTintFixEnabled"]),
                "verificationState": display_profile_settings["gamescopeZotacProfileVerificationState"],
                "baseAssetAvailable": bool(display_profile_settings["gamescopeZotacProfileBaseAssetAvailable"]),
                "greenTintAssetAvailable": bool(display_profile_settings["gamescopeZotacProfileGreenAssetAvailable"]),
                **gamescope_paths,
            },
            "deckyZoneStatus": {
                "message": status["message"],
            },
        }

    async def get_latest_version_num(self):
        try:
            return plugin_update.get_latest_version()
        except Exception as error:
            self.logger.error(f"Failed to fetch latest DeckyZone version: {error}")
            raise RuntimeError("Failed to fetch latest DeckyZone version.")

    async def ota_update(self):
        try:
            return bool(plugin_update.ota_update())
        except Exception as error:
            self.logger.error(f"Failed to update DeckyZone: {error}")
            return False

    def _set_status(self, state, message):
        self._status = {"state": state, "message": message}

    def _read_text(self, path):
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip()

    def _read_optional_text(self, path):
        try:
            value = self.read_text(path)
        except Exception:
            return None
        return value or None

    def _path_exists(self, path):
        return Path(path).exists()

    def _extract_version_from_output(self, binary_name, output):
        binary_prefix = f"{binary_name.lower()} "
        version_prefix = f"{binary_name.lower()} version "

        for raw_line in (output or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue

            normalized_line = line.lower()
            if normalized_line.startswith(version_prefix):
                version = line[len(binary_name) + len(" version ") :].strip()
                return version or line

            if normalized_line.startswith(binary_prefix):
                version = line[len(binary_name) + 1 :].strip()
                return version or line

            version_marker_index = normalized_line.find(" version ")
            if version_marker_index != -1:
                version = line[version_marker_index + len(" version ") :].strip()
                return version or line

            return line

        return None

    def _get_binary_version(self, binary_name):
        try:
            result = self.command_runner(
                [binary_name, "--version"],
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self.get_env(),
            )
        except Exception:
            return None

        output = "\n".join(
            part.strip()
            for part in (result.stdout, result.stderr)
            if isinstance(part, str) and part.strip()
        )
        return self._extract_version_from_output(binary_name, output)

    def _get_controller_runtime_state(
        self,
        *,
        inputplumber_available,
        controller_mode_snapshot,
        target_gamepad_path,
        keyboard_path,
    ):
        if not inputplumber_available:
            return "InputPlumber unavailable"

        if not self._path_exists(ZOTAC_ZONE_HID_MODULE_PATH):
            return "Zotac HID driver missing"

        if not controller_mode_snapshot["available"]:
            return "Controller mode interface unavailable"

        if controller_mode_snapshot["mode"] == ZOTAC_CONTROLLER_MODE_DESKTOP:
            return "Desktop mode"

        if controller_mode_snapshot["mode"] is None:
            return "Controller mode read failed"

        if not target_gamepad_path:
            return "Target gamepad missing"

        if not keyboard_path:
            return "InputPlumber keyboard missing"

        return "Healthy"

    def _get_kernel_release(self):
        try:
            return os.uname().release
        except Exception:
            return None

    def _get_os_pretty_name(self):
        for candidate_path in OS_RELEASE_CANDIDATE_PATHS:
            content = self._read_optional_text(candidate_path)
            if not content:
                continue

            for line in content.splitlines():
                if not line.startswith("PRETTY_NAME="):
                    continue

                value = line.split("=", 1)[1].strip()
                if (
                    len(value) >= 2
                    and value[0] == value[-1]
                    and value[0] in {'"', "'"}
                ):
                    value = value[1:-1]
                return value or None

        return None

    def _get_display_profile_settings(self):
        try:
            return self.gamescope_display_profiles.get_state()
        except Exception as error:
            self.logger.warning(f"Failed to read Gamescope display profile state: {error}")
            built_in_candidate_paths = []
            try:
                built_in_candidate_paths = list(
                    self.gamescope_display_profiles.system_profile_paths
                )
            except Exception:
                built_in_candidate_paths = list(
                    gamescope_display_profiles_module.DEFAULT_SYSTEM_PROFILE_PATHS
                )

            managed_profile_path = Path(decky.DECKY_USER_HOME) / ".config" / "gamescope" / "scripts" / "zotac.zone.oled.lua"
            base_asset_path = Path(decky.DECKY_PLUGIN_DIR) / "assets" / "gamescope" / "zotac.zone.oled.lua"
            green_asset_path = Path(decky.DECKY_PLUGIN_DIR) / "assets" / "gamescope" / "zotac.zone.green-tint.lua"
            return {
                "gamescopeZotacProfileBuiltIn": any(path.is_file() for path in built_in_candidate_paths),
                "gamescopeZotacProfileInstalled": managed_profile_path.is_file(),
                "gamescopeGreenTintFixEnabled": False,
                "gamescopeZotacProfileTargetPath": str(managed_profile_path),
                "gamescopeZotacProfileVerificationState": "error",
                "gamescopeZotacProfileBaseAssetAvailable": base_asset_path.is_file(),
                "gamescopeZotacProfileGreenAssetAvailable": green_asset_path.is_file(),
                "gamescopeZotacProfileAssetsAvailable": base_asset_path.is_file() and green_asset_path.is_file(),
            }

    def _get_gamescope_support_path(self, attribute_name, fallback):
        try:
            return str(getattr(self.gamescope_display_profiles, attribute_name))
        except Exception:
            return fallback

    def _get_gamescope_support_paths(self):
        try:
            built_in_candidate_paths = [
                str(path)
                for path in self.gamescope_display_profiles.system_profile_paths
            ]
        except Exception:
            built_in_candidate_paths = [
                str(path)
                for path in gamescope_display_profiles_module.DEFAULT_SYSTEM_PROFILE_PATHS
            ]

        return {
            "builtInCandidatePaths": built_in_candidate_paths,
            "managedProfilePath": self._get_gamescope_support_path(
                "managed_profile_path",
                str(
                    Path(decky.DECKY_USER_HOME)
                    / ".config"
                    / "gamescope"
                    / "scripts"
                    / "zotac.zone.oled.lua"
                ),
            ),
            "baseAssetPath": self._get_gamescope_support_path(
                "base_profile_asset_path",
                str(
                    Path(decky.DECKY_PLUGIN_DIR)
                    / "assets"
                    / "gamescope"
                    / "zotac.zone.oled.lua"
                ),
            ),
            "greenTintAssetPath": self._get_gamescope_support_path(
                "green_profile_asset_path",
                str(
                    Path(decky.DECKY_PLUGIN_DIR)
                    / "assets"
                    / "gamescope"
                    / "zotac.zone.green-tint.lua"
                ),
            ),
        }

    def _get_controller_mode_snapshot(self):
        controller_mode_device_path = self._resolve_zotac_controller_hidraw_path()
        return {
            "available": controller_mode_device_path is not None,
            "mode": self._get_controller_mode(controller_mode_device_path),
        }

    def _is_controller_mode_snapshot_safe(self, controller_mode_snapshot):
        return bool(
            controller_mode_snapshot["available"]
            and controller_mode_snapshot["mode"] == ZOTAC_CONTROLLER_MODE_GAMEPAD
        )

    def _current_settings(self):
        display_profile_settings = self._get_display_profile_settings()
        controller_mode_snapshot = self._get_controller_mode_snapshot()
        return {
            "startupApplyEnabled": self.settings_store.get_startup_apply_enabled(),
            "controllerMode": controller_mode_snapshot["mode"],
            "controllerModeAvailable": controller_mode_snapshot["available"],
            "homeButtonEnabled": self.settings_store.get_home_button_enabled(),
            "brightnessDialFixEnabled": self.settings_store.get_brightness_dial_fix_enabled(),
            "trackpadMode": self.settings_store.get_trackpad_mode(),
            "zotacGlyphsEnabled": self.settings_store.get_zotac_glyphs_enabled(),
            "gamescopeZotacProfileBuiltIn": display_profile_settings["gamescopeZotacProfileBuiltIn"],
            "gamescopeZotacProfileInstalled": display_profile_settings["gamescopeZotacProfileInstalled"],
            "gamescopeGreenTintFixEnabled": display_profile_settings["gamescopeGreenTintFixEnabled"],
            "gamescopeZotacProfileTargetPath": display_profile_settings["gamescopeZotacProfileTargetPath"],
            "gamescopeZotacProfileVerificationState": display_profile_settings["gamescopeZotacProfileVerificationState"],
            "inputplumberAvailable": self._inputplumber_available,
            "pluginVersionNum": decky.DECKY_PLUGIN_VERSION,
            "rumbleEnabled": self.settings_store.get_rumble_enabled(),
            "rumbleIntensity": self.settings_store.get_rumble_intensity(),
            "rumbleAvailable": self._rumble_available,
            "perGameSettings": self.settings_store.get_per_game_settings(),
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
            vendor = self.read_text(DMI_SYS_VENDOR_PATH)
            board = self.read_text(DMI_BOARD_NAME_PATH)
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

    def _get_inputplumber_profile_name(self):
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
        if not self._inputplumber_available:
            return ""
        return inputplumber_target_sync.parse_busctl_string_output(result.stdout)

    def probe_inputplumber_available(self):
        try:
            return self._probe_inputplumber_profile_name()
        except Exception:
            self._inputplumber_available = False
            return False

    def _apply_target_devices(self, target_mode, include_keyboard=True, include_mouse=True):
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
                    include_keyboard=include_keyboard,
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
        return inputplumber_target_sync.parse_busctl_string_output(result.stdout)

    def _get_inputplumber_target_device_paths(self):
        result = self.command_runner(
            self._busctl_args(
                "get-property",
                "org.shadowblip.InputPlumber",
                INPUTPLUMBER_DBUS_PATH,
                "org.shadowblip.Input.CompositeDevice",
                "TargetDevices",
            ),
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.get_env(),
        )
        self._inputplumber_available = True
        return inputplumber_target_sync.parse_busctl_array_output(result.stdout)

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
        return inputplumber_target_sync.parse_busctl_string_output(result.stdout)

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

    def _write_inputplumber_profile_file(self, filename, profile_yaml):
        profile_path = Path(decky.DECKY_PLUGIN_RUNTIME_DIR) / filename
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path.write_text(profile_yaml, encoding="utf-8")
        return str(profile_path)

    def _write_managed_inputplumber_file(self, directory_path, filename, content):
        path = Path(directory_path) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        current_content = None
        try:
            current_content = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            current_content = None

        if current_content == content:
            return False

        path.write_text(content, encoding="utf-8")
        return True

    def _remove_managed_inputplumber_file(self, directory_path, filename):
        path = Path(directory_path) / filename
        if not path.exists():
            return False

        path.unlink()
        return True

    def _get_effective_trackpad_mode(self, app_id=None):
        app_id = str(app_id or self._active_per_game_app_id or DEFAULT_APP_ID)
        global_mode = self.settings_store.get_trackpad_mode()

        if app_id == DEFAULT_APP_ID:
            return global_mode

        if not self.settings_store.get_per_game_settings_enabled(app_id):
            return global_mode

        return self.settings_store.get_per_game_trackpad_mode(app_id)

    def _should_disable_trackpads(self, app_id=None):
        return trackpad_modes.is_trackpad_mode_disabled(
            self._get_effective_trackpad_mode(app_id)
        )

    def _should_enable_directional_trackpads(self, app_id=None):
        return trackpad_modes.is_trackpad_mode_directional(
            self._get_effective_trackpad_mode(app_id)
        )

    def _get_effective_rumble_enabled(self, app_id=None):
        app_id = str(app_id or self._active_per_game_app_id or DEFAULT_APP_ID)
        global_enabled = self.settings_store.get_rumble_enabled()

        if app_id == DEFAULT_APP_ID:
            return global_enabled

        if not self.settings_store.get_per_game_settings_enabled(app_id):
            return global_enabled

        return self.settings_store.get_per_game_rumble_enabled(app_id)

    def _get_effective_rumble_intensity(self, app_id=None):
        app_id = str(app_id or self._active_per_game_app_id or DEFAULT_APP_ID)
        global_intensity = self.settings_store.get_rumble_intensity()

        if app_id == DEFAULT_APP_ID:
            return global_intensity

        if not self.settings_store.get_per_game_settings_enabled(app_id):
            return global_intensity

        return self.settings_store.get_per_game_rumble_intensity(app_id)

    def _should_include_mouse_target(self, app_id=None):
        return not self._should_enable_directional_trackpads(app_id)

    def _remove_directional_trackpad_capability_map(self):
        return self._remove_managed_inputplumber_file(
            MANAGED_INPUTPLUMBER_CAPABILITY_MAPS_DIR,
            MANAGED_DIRECTIONAL_TRACKPAD_CAPABILITY_MAP_FILENAME,
        )

    def _remove_directional_trackpad_device_override(self):
        return self._remove_managed_inputplumber_file(
            MANAGED_INPUTPLUMBER_DEVICES_DIR,
            MANAGED_DIRECTIONAL_TRACKPAD_DEVICE_OVERRIDE_FILENAME,
        )

    def _sync_directional_trackpad_source_files(self, app_id=None):
        del app_id
        return self._disable_directional_trackpad_source_files()

    def _disable_directional_trackpad_source_files(self):
        device_override_changed = self._remove_directional_trackpad_device_override()
        capability_map_changed = self._remove_directional_trackpad_capability_map()
        return capability_map_changed or device_override_changed

    def _has_directional_trackpad_source_files(self):
        return (
            (
                MANAGED_INPUTPLUMBER_DEVICES_DIR
                / MANAGED_DIRECTIONAL_TRACKPAD_DEVICE_OVERRIDE_FILENAME
            ).exists()
            or (
                MANAGED_INPUTPLUMBER_CAPABILITY_MAPS_DIR
                / MANAGED_DIRECTIONAL_TRACKPAD_CAPABILITY_MAP_FILENAME
            ).exists()
        )

    def _get_directional_trackpad_backup_path(self):
        return Path(decky.DECKY_PLUGIN_RUNTIME_DIR) / DIRECTIONAL_TRACKPAD_BACKUP_FILENAME

    def _has_directional_trackpad_backup(self):
        if self._directional_trackpad_backup is not None:
            return True

        return self._get_directional_trackpad_backup_path().is_file()

    def _has_directional_trackpad_runtime_state(self):
        return (
            self._has_directional_trackpad_backup()
            or self._has_directional_trackpad_source_files()
        )

    def _load_directional_trackpad_backup(self):
        if self._directional_trackpad_backup is not None:
            return dict(self._directional_trackpad_backup)

        backup_path = self._get_directional_trackpad_backup_path()
        if not backup_path.is_file():
            return None

        try:
            payload = json.loads(backup_path.read_text(encoding="utf-8"))
            mappings = {}
            for entry in payload.get("mappings", []):
                button_id = int(entry["buttonId"])
                mapping_payload = bytes(entry["payload"])
                if (
                    len(mapping_payload)
                    != trackpad_modes.ZOTAC_BUTTON_MAPPING_PAYLOAD_SIZE
                ):
                    raise ValueError(
                        f"Unexpected mapping payload length for button 0x{button_id:02x}"
                    )
                mappings[button_id] = mapping_payload
        except Exception as error:
            self.logger.warning(
                f"Failed to load directional trackpad backup mappings: {error}"
            )
            return None

        self._directional_trackpad_backup = dict(mappings)
        return dict(mappings)

    def _store_directional_trackpad_backup(self, mappings):
        serializable = {
            "mappings": [
                {
                    "buttonId": button_id,
                    "payload": list(mapping_payload),
                }
                for button_id, mapping_payload in sorted(mappings.items())
            ]
        }
        backup_path = self._get_directional_trackpad_backup_path()
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path.write_text(
            json.dumps(serializable, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self._directional_trackpad_backup = dict(mappings)

    def _clear_directional_trackpad_backup(self):
        backup_path = self._get_directional_trackpad_backup_path()
        if backup_path.exists():
            backup_path.unlink()
        self._directional_trackpad_backup = None

    def _get_runtime_inputplumber_profile_path(self):
        return Path(decky.DECKY_PLUGIN_RUNTIME_DIR) / RUNTIME_INPUTPLUMBER_PROFILE_FILENAME

    def _get_home_button_override_profile_path(self):
        return Path(decky.DECKY_PLUGIN_RUNTIME_DIR) / HOME_BUTTON_OVERRIDE_PROFILE_FILENAME

    def _write_runtime_inputplumber_profile_file(self, profile_yaml):
        return self._write_inputplumber_profile_file(
            RUNTIME_INPUTPLUMBER_PROFILE_FILENAME,
            profile_yaml,
        )

    def _write_home_button_override_profile_file(self, profile_yaml):
        return self._write_inputplumber_profile_file(
            HOME_BUTTON_OVERRIDE_PROFILE_FILENAME,
            profile_yaml,
        )

    def _build_keyboard_mapping_lines(self, indent, name, source_button, target_key):
        return [
            f"{indent}- name: {name}",
            f"{indent}  source_event:",
            f"{indent}    gamepad:",
            f"{indent}      button: {source_button}",
            f"{indent}  target_events:",
            f"{indent}    - keyboard: {target_key}",
        ]

    def _build_gamepad_button_mapping_lines(self, indent, name, source_button, target_button):
        return [
            f"{indent}- name: {name}",
            f"{indent}  source_event:",
            f"{indent}    gamepad:",
            f"{indent}      button: {source_button}",
            f"{indent}  target_events:",
            f"{indent}    - gamepad:",
            f"{indent}        button: {target_button}",
        ]

    def _build_home_button_override_profile_yaml(self, profile_yaml):
        profile_yaml = runtime_profile_utils.remove_gamepad_button_source_mappings(
            profile_yaml,
            {"QuickAccess2", "Keyboard"},
        )

        lines = profile_yaml.splitlines()
        trailing_newline = profile_yaml.endswith("\n")
        mapping_indent = ""
        insert_index = len(lines)

        for index, line in enumerate(lines):
            if line.strip() != "mapping:":
                continue

            mapping_indent = line[: len(line) - len(line.lstrip())]
            insert_index = len(lines)
            for candidate_index in range(index + 1, len(lines)):
                stripped = lines[candidate_index].lstrip()
                indent = lines[candidate_index][: len(lines[candidate_index]) - len(stripped)]
                if (
                    stripped
                    and not stripped.startswith("#")
                    and indent == mapping_indent
                    and not stripped.startswith("-")
                ):
                    insert_index = candidate_index
                    break
            break
        else:
            lines.append("mapping:")
            insert_index = len(lines)

        mapping_lines = self._build_keyboard_mapping_lines(
            mapping_indent,
            RUNTIME_PROFILE_HOME_BUTTON_MAPPING_NAME,
            "QuickAccess2",
            "KeyF18",
        )
        lines = lines[:insert_index] + mapping_lines + lines[insert_index:]

        override_yaml = "\n".join(lines)
        if trailing_newline or not override_yaml.endswith("\n"):
            override_yaml = f"{override_yaml}\n"
        return override_yaml

    def _reset_home_button_override_state(self):
        self._home_button_override_active = False
        self._home_button_original_profile_path = None
        self._home_button_original_profile_yaml = None

    def _is_home_button_override_profile_active(self):
        try:
            return self._get_inputplumber_profile_path() == str(
                self._get_home_button_override_profile_path()
            )
        except Exception:
            self._inputplumber_available = False
            return False

    def _ensure_home_button_original_profile(self):
        if self._home_button_original_profile_yaml is not None:
            return True

        self._home_button_original_profile_path = (
            self._get_inputplumber_profile_path() or None
        )
        self._home_button_original_profile_yaml = (
            self._get_inputplumber_profile_yaml()
        )
        return True

    def _load_home_button_override_profile(self):
        if (
            self._home_button_override_active
            and self._is_home_button_override_profile_active()
        ):
            return True

        self._reset_home_button_override_state()
        self._ensure_home_button_original_profile()
        base_profile_yaml = self._home_button_original_profile_yaml or ""
        override_profile_yaml = self._build_home_button_override_profile_yaml(
            base_profile_yaml
        )
        override_profile_path = self._write_home_button_override_profile_file(
            override_profile_yaml
        )
        self._load_inputplumber_profile_path(override_profile_path)
        self._home_button_override_active = True
        return True

    def _restore_home_button_profile(self):
        if not self._home_button_override_active:
            self._reset_home_button_override_state()
            return True

        if self._home_button_original_profile_path:
            self._load_inputplumber_profile_path(
                self._home_button_original_profile_path
            )
        elif self._home_button_original_profile_yaml:
            original_profile_path = self._write_home_button_override_profile_file(
                self._home_button_original_profile_yaml
            )
            self._load_inputplumber_profile_path(original_profile_path)
        else:
            self._load_inputplumber_profile_path(DEFAULT_INPUTPLUMBER_PROFILE_PATH)

        self._reset_home_button_override_state()
        return True

    def _get_active_per_game_runtime_mappings(self, app_id=None):
        active_app_id = str(app_id or self._active_per_game_app_id or DEFAULT_APP_ID)
        if (
            active_app_id == DEFAULT_APP_ID
            or self._temporary_target_mode != MISSING_GLYPH_FIX_TARGET
            or not self.settings_store.get_per_game_settings_enabled(active_app_id)
            or not self.settings_store.get_button_prompt_fix_enabled(active_app_id)
        ):
            return []

        mappings = []
        m1_target = self.settings_store.get_per_game_m1_remap_target(active_app_id)
        if m1_target != PER_GAME_REMAP_NONE:
            target_button = PER_GAME_REMAP_TARGET_TO_INPUTPLUMBER_BUTTON.get(m1_target)
            if target_button:
                mappings.append(
                    (
                        RUNTIME_PROFILE_M1_MAPPING_NAME,
                        PER_GAME_REMAP_SOURCE_BUTTON_M1,
                        target_button,
                    )
                )

        m2_target = self.settings_store.get_per_game_m2_remap_target(active_app_id)
        if m2_target != PER_GAME_REMAP_NONE:
            target_button = PER_GAME_REMAP_TARGET_TO_INPUTPLUMBER_BUTTON.get(m2_target)
            if target_button:
                mappings.append(
                    (
                        RUNTIME_PROFILE_M2_MAPPING_NAME,
                        PER_GAME_REMAP_SOURCE_BUTTON_M2,
                        target_button,
                    )
                )

        return mappings

    def _build_runtime_input_profile_mapping_lines(self, indent, app_id=None):
        mapping_lines = []

        for name, source_button, target_button in self._get_active_per_game_runtime_mappings(
            app_id
        ):
            mapping_lines.extend(
                self._build_gamepad_button_mapping_lines(
                    indent,
                    name,
                    source_button,
                    target_button,
                )
            )

        return mapping_lines

    def _build_runtime_input_profile_yaml(self, profile_yaml, app_id=None):
        lines = profile_yaml.splitlines()
        trailing_newline = profile_yaml.endswith("\n")
        mapping_indent = ""
        insert_index = len(lines)

        for index, line in enumerate(lines):
            if line.strip() != "mapping:":
                continue

            mapping_indent = line[: len(line) - len(line.lstrip())]
            insert_index = len(lines)
            for candidate_index in range(index + 1, len(lines)):
                stripped = lines[candidate_index].lstrip()
                indent = lines[candidate_index][: len(lines[candidate_index]) - len(stripped)]
                if (
                    stripped
                    and not stripped.startswith("#")
                    and indent == mapping_indent
                    and not stripped.startswith("-")
                ):
                    insert_index = candidate_index
                    break
            break
        else:
            lines.append("mapping:")
            insert_index = len(lines)

        mapping_lines = self._build_runtime_input_profile_mapping_lines(
            mapping_indent,
            app_id,
        )
        lines = lines[:insert_index] + mapping_lines + lines[insert_index:]

        override_yaml = "\n".join(lines)
        if trailing_newline or not override_yaml.endswith("\n"):
            override_yaml = f"{override_yaml}\n"
        return override_yaml

    def _reset_runtime_input_profile_state(self):
        self._runtime_input_profile_active = False
        self._runtime_input_profile_original_profile_path = None
        self._runtime_input_profile_original_profile_yaml = None

    def _reset_inputplumber_profile_state(self):
        self._reset_home_button_override_state()
        self._reset_runtime_input_profile_state()

    async def _restart_inputplumber_after_trackpad_source_update(self):
        try:
            self._release_zotac_mouse_device()
            self._startup_target_active = False
            self._temporary_target_mode = None
            self._reset_inputplumber_profile_state()
            self._restart_inputplumber()
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or str(error)).strip()
            self.logger.warning(
                f"Failed to restart InputPlumber after trackpad source update: {detail}"
            )
            return False
        except Exception as error:
            self.logger.warning(
                "Failed to restart InputPlumber after trackpad source update: "
                f"{error}"
            )
            return False

        return await self.wait_for_inputplumber_dbus_silently()

    async def _sync_directional_trackpad_source_runtime(self, app_id=None):
        try:
            changed = self._sync_directional_trackpad_source_files(app_id)
        except Exception as error:
            self.logger.warning(
                f"Failed to update directional trackpad source files: {error}"
            )
            return False

        if not changed:
            return self._sync_directional_trackpad_button_runtime(app_id)

        if not await self._restart_inputplumber_after_trackpad_source_update():
            return False

        return self._sync_directional_trackpad_button_runtime(app_id)

    async def _disable_directional_trackpad_source_runtime_result(
        self,
        force_restart=False,
        restore_only_with_runtime_state=False,
    ):
        had_runtime_state = False
        try:
            had_runtime_state = self._has_directional_trackpad_runtime_state()
            changed = self._disable_directional_trackpad_source_files()
        except Exception as error:
            message = f"Failed to remove directional trackpad source files: {error}"
            self.logger.warning(
                message
            )
            return self._cleanup_step_result(ok=False, message=message)

        if not changed and not force_restart:
            if restore_only_with_runtime_state and not had_runtime_state:
                return self._cleanup_step_result(
                    ok=True,
                    changed=False,
                    message="No directional trackpad runtime state; skipped HID restore.",
                )
            restored = self._restore_directional_trackpad_button_mappings()
            return self._cleanup_step_result(
                ok=restored,
                changed=False,
                message="" if restored else "Failed to restore trackpad mappings.",
            )

        if not await self._restart_inputplumber_after_trackpad_source_update():
            return self._cleanup_step_result(
                ok=False,
                changed=changed or force_restart,
                message="Failed to restart InputPlumber after trackpad cleanup.",
            )

        restored = self._restore_directional_trackpad_button_mappings()
        return self._cleanup_step_result(
            ok=restored,
            changed=changed or force_restart,
            message="" if restored else "Failed to restore trackpad mappings.",
        )

    async def _disable_directional_trackpad_source_runtime(self, force_restart=False):
        result = await self._disable_directional_trackpad_source_runtime_result(
            force_restart=force_restart
        )
        return result["ok"]

    def _sync_directional_trackpad_button_runtime(self, app_id=None):
        if self._should_enable_directional_trackpads(app_id):
            return self._apply_directional_trackpad_button_mappings()

        return self._restore_directional_trackpad_button_mappings()

    def _should_enable_runtime_input_profile(self, app_id=None):
        return bool(self._get_active_per_game_runtime_mappings(app_id))

    def _ensure_runtime_input_profile_original_profile(self):
        if self._runtime_input_profile_original_profile_yaml is not None:
            return True

        self._runtime_input_profile_original_profile_path = (
            self._get_inputplumber_profile_path() or None
        )
        self._runtime_input_profile_original_profile_yaml = (
            self._get_inputplumber_profile_yaml()
        )
        return True

    def _load_runtime_input_profile(self, app_id=None):
        self._ensure_runtime_input_profile_original_profile()
        base_profile_yaml = self._runtime_input_profile_original_profile_yaml or ""
        override_profile_yaml = self._build_runtime_input_profile_yaml(
            base_profile_yaml,
            app_id,
        )
        override_profile_path = self._write_runtime_inputplumber_profile_file(
            override_profile_yaml
        )
        self._load_inputplumber_profile_path(override_profile_path)
        self._runtime_input_profile_active = True
        return True

    def _restore_runtime_input_profile(self):
        if not self._runtime_input_profile_active:
            self._reset_runtime_input_profile_state()
            return True

        if self._runtime_input_profile_original_profile_path:
            self._load_inputplumber_profile_path(
                self._runtime_input_profile_original_profile_path
            )
        elif self._runtime_input_profile_original_profile_yaml:
            original_profile_path = self._write_runtime_inputplumber_profile_file(
                self._runtime_input_profile_original_profile_yaml
            )
            self._load_inputplumber_profile_path(original_profile_path)
        else:
            self._load_inputplumber_profile_path(DEFAULT_INPUTPLUMBER_PROFILE_PATH)

        self._reset_runtime_input_profile_state()
        return True

    def _sync_runtime_input_profile_state(self, app_id=None):
        try:
            if self._should_enable_runtime_input_profile(app_id):
                return self._load_runtime_input_profile(app_id)

            return self._restore_runtime_input_profile()
        except Exception as error:
            self.logger.warning(f"Failed to sync runtime InputPlumber profile: {error}")
            try:
                self._restore_runtime_input_profile()
            except Exception as restore_error:
                self.logger.warning(
                    f"Failed to restore runtime InputPlumber profile after error: {restore_error}"
                )
            return False

    def _sanitize_deckyzone_inputplumber_profile_yaml(self, profile_yaml):
        return runtime_profile_utils.remove_mapping_names(
            profile_yaml,
            {
                RUNTIME_PROFILE_HOME_BUTTON_MAPPING_NAME,
                RUNTIME_PROFILE_M1_MAPPING_NAME,
                RUNTIME_PROFILE_M2_MAPPING_NAME,
            },
        )

    def _restore_or_sanitize_inputplumber_profiles_for_reset(self):
        if not self.probe_inputplumber_available():
            return {
                "ok": True,
                "changed": False,
                "message": "InputPlumber unavailable; skipped live profile restore.",
            }

        changed = False
        if self._home_button_override_active:
            self._restore_home_button_profile()
            changed = True

        if self._runtime_input_profile_active:
            self._restore_runtime_input_profile()
            changed = True

        current_profile_path = self._get_inputplumber_profile_path() or ""
        managed_profile_paths = {
            str(self._get_runtime_inputplumber_profile_path()),
            str(self._get_home_button_override_profile_path()),
        }

        if current_profile_path in managed_profile_paths:
            self._load_inputplumber_profile_path(DEFAULT_INPUTPLUMBER_PROFILE_PATH)
            changed = True
        else:
            current_profile_yaml = self._get_inputplumber_profile_yaml()
            sanitized_profile_yaml = self._sanitize_deckyzone_inputplumber_profile_yaml(
                current_profile_yaml
            )
            if sanitized_profile_yaml != current_profile_yaml:
                self._load_inputplumber_profile_from_yaml(sanitized_profile_yaml)
                changed = True

        self._reset_inputplumber_profile_state()
        return {"ok": True, "changed": changed, "message": ""}

    def set_per_game_m1_remap_target(self, app_id, target):
        if app_id in (None, "", DEFAULT_APP_ID):
            return self._current_settings()

        if target != PER_GAME_REMAP_NONE and not self.probe_inputplumber_available():
            return self._current_settings()

        self.settings_store.set_per_game_m1_remap_target(app_id, target)
        return self._current_settings()

    def set_per_game_m2_remap_target(self, app_id, target):
        if app_id in (None, "", DEFAULT_APP_ID):
            return self._current_settings()

        if target != PER_GAME_REMAP_NONE and not self.probe_inputplumber_available():
            return self._current_settings()

        self.settings_store.set_per_game_m2_remap_target(app_id, target)
        return self._current_settings()

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

    def _resolve_input_device_path_by_name(self, target_device_name):
        for candidate_path in self._get_zotac_mouse_candidate_paths():
            try:
                device_name = self._read_input_device_name(candidate_path)
            except Exception:
                continue

            if device_name == target_device_name:
                return candidate_path

        return None

    def _resolve_input_device_path_by_match(self, match_device_name):
        for candidate_path in self._get_zotac_mouse_candidate_paths():
            try:
                device_name = self._read_input_device_name(candidate_path)
            except Exception:
                continue

            if match_device_name(device_name):
                return candidate_path

        return None

    def _resolve_zotac_mouse_device_path(self):
        return self._resolve_input_device_path_by_name(ZOTAC_MOUSE_DEVICE_NAME)

    def _resolve_zotac_keyboard_device_path(self):
        return self._resolve_input_device_path_by_name(ZOTAC_KEYBOARD_DEVICE_NAME)

    def _resolve_zotac_dials_device_path(self):
        return self._resolve_input_device_path_by_name(ZOTAC_DIALS_DEVICE_NAME)

    def _open_event_device(self, device_path):
        return os.open(device_path, os.O_RDONLY)

    def _open_nonblocking_event_device(self, device_path):
        return os.open(device_path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))

    def _close_event_device(self, fd):
        os.close(fd)

    def _resolve_inputplumber_keyboard_device_path(self):
        return self._resolve_input_device_path_by_name(INPUTPLUMBER_KEYBOARD_DEVICE_NAME)

    def _resolve_startup_gamepad_device_path(self):
        return self._resolve_input_device_path_by_match(
            controller_targets.is_startup_target_gamepad_device_name
        )

    async def _wait_for_resolved_input_device_path(
        self,
        resolve_device_path,
        timeout=inputplumber_target_sync.TARGET_SETTLE_TIMEOUT_SECONDS,
        interval=inputplumber_target_sync.TARGET_SETTLE_POLL_INTERVAL_SECONDS,
    ):
        elapsed = 0.0

        while elapsed < timeout:
            try:
                if resolve_device_path():
                    return True
            except Exception:
                pass

            await self.sleep(interval)
            elapsed += interval

        return False

    async def _wait_for_inputplumber_target_devices(
        self,
        expected_count,
        require_keyboard_device=True,
        timeout=inputplumber_target_sync.TARGET_SETTLE_TIMEOUT_SECONDS,
        interval=inputplumber_target_sync.TARGET_SETTLE_POLL_INTERVAL_SECONDS,
    ):
        return await inputplumber_target_sync.wait_for_target_devices(
            get_target_device_paths=self._get_inputplumber_target_device_paths,
            resolve_keyboard_device_path=self._resolve_inputplumber_keyboard_device_path,
            mark_unavailable=lambda: setattr(self, "_inputplumber_available", False),
            sleep=self.sleep,
            expected_count=expected_count,
            require_keyboard_device=require_keyboard_device,
            timeout=timeout,
            interval=interval,
        )

    async def _apply_target_devices_with_retries(
        self,
        target_mode,
        include_keyboard=True,
        include_mouse=True,
    ):
        return await inputplumber_target_sync.apply_target_devices_with_retries(
            apply_target_devices=self._apply_target_devices,
            wait_for_target_devices_fn=self._wait_for_inputplumber_target_devices,
            sleep=self.sleep,
            target_mode=target_mode,
            include_keyboard=include_keyboard,
            include_mouse=include_mouse,
        )

    async def _apply_verified_startup_target(self):
        if not await self._apply_target_devices_with_retries(
            STARTUP_MODE,
            include_mouse=self._should_include_mouse_target(),
        ):
            self._restart_inputplumber()
            self._startup_target_active = False
            return "InputPlumber target devices did not settle after retries."

        # The DBus target object can appear before the actual target gamepad
        # input device is created, so verify the real device before succeeding.
        if not await self._wait_for_resolved_input_device_path(
            self._resolve_startup_gamepad_device_path
        ):
            self._restart_inputplumber()
            self._startup_target_active = False
            return (
                "InputPlumber target gamepad device did not appear. "
                "Accepted names: "
                f"{controller_targets.describe_startup_target_gamepad_names()}."
            )

        self._startup_target_active = True
        return None

    def _is_runtime_input_profile_active(self):
        try:
            return self._get_inputplumber_profile_path() == str(
                self._get_runtime_inputplumber_profile_path()
            )
        except Exception:
            self._inputplumber_available = False
            return False

    def _is_runtime_input_profile_effective(self):
        if not self._should_enable_runtime_input_profile(self._active_per_game_app_id):
            return True

        if self._is_runtime_input_profile_active():
            return True

        return (
            self._is_home_button_override_profile_active()
            and self._home_button_original_profile_path
            == str(self._get_runtime_inputplumber_profile_path())
        )

    def _is_startup_runtime_ready(self):
        try:
            target_paths = self._get_inputplumber_target_device_paths()
        except Exception:
            self._inputplumber_available = False
            return False

        if len(target_paths) < len(
            controller_targets.build_target_devices(
                STARTUP_MODE,
                include_mouse=self._should_include_mouse_target(),
            )
        ):
            return False

        if not self._resolve_startup_gamepad_device_path():
            return False

        if not self._resolve_inputplumber_keyboard_device_path():
            return False

        if not self._is_runtime_input_profile_effective():
            return False

        if (
            self._should_enable_home_button_navigation()
            and not self._is_home_button_override_profile_active()
        ):
            return False

        return True

    async def _wait_for_startup_runtime_ready(
        self,
        timeout=STARTUP_RUNTIME_READY_TIMEOUT_SECONDS,
        interval=STARTUP_RUNTIME_READY_POLL_INTERVAL_SECONDS,
    ):
        elapsed = 0.0

        while elapsed < timeout:
            if self._is_startup_runtime_ready():
                return True

            await self.sleep(interval)
            elapsed += interval

        return False

    async def _reset_startup_runtime_attempt(self):
        self._startup_target_active = False
        self._temporary_target_mode = None
        self._release_zotac_mouse_device()
        await self._sync_brightness_dial_fixer_state()
        await self._sync_home_button_navigation_state()

    async def _apply_startup_runtime_once(self):
        if not await self._sync_directional_trackpad_source_runtime(
            self._active_per_game_app_id
        ):
            return "Directional trackpad source state did not apply."

        detail = await self._apply_verified_startup_target()
        if detail is not None:
            return detail

        self._temporary_target_mode = None
        trackpad_result = self._sync_trackpad_suppression_state()
        brightness_result = await self._sync_brightness_dial_fixer_state()
        rumble_result = await self._sync_rumble_state(self._active_per_game_app_id)
        profile_result = await self._sync_home_button_navigation_state()

        if not trackpad_result:
            return "Trackpad suppression state did not apply."

        if not brightness_result:
            return "Brightness dial listener did not activate."

        if not rumble_result:
            return "Rumble state did not apply."

        if not profile_result:
            return "Home button runtime profile did not activate."

        if not await self._wait_for_startup_runtime_ready():
            return "Startup runtime did not reach keyboard/profile-ready state."

        return None

    async def _apply_startup_runtime_with_retries(self):
        async def run_attempt():
            detail = await self._apply_startup_runtime_once()
            if detail is not None:
                await self._reset_startup_runtime_attempt()
            return detail

        return await inputplumber_target_sync.retry_detail_until_clear(
            run_attempt,
            self.sleep,
            attempts=STARTUP_APPLY_ATTEMPTS,
            backoff=STARTUP_APPLY_BACKOFF_SECONDS,
        )

    def _read_input_event_from_fd(self, fd):
        raw_event = os.read(fd, ctypes.sizeof(_InputEvent))
        if len(raw_event) != ctypes.sizeof(_InputEvent):
            raise OSError("Incomplete input event read.")
        return _InputEvent.from_buffer_copy(raw_event)

    async def _cancel_task(self, task, timeout=None):
        if task is None or task.done():
            return True

        task.cancel()
        if timeout is None:
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as error:
                self.logger.warning(f"Task cleanup failed: {error}")
                return False
            return True

        done, pending = await asyncio.wait({task}, timeout=timeout)
        if pending:
            return False

        completed_task = next(iter(done))
        try:
            completed_task.result()
        except asyncio.CancelledError:
            pass
        except Exception as error:
            self.logger.warning(f"Task cleanup failed: {error}")
            return False
        return True

    def _get_brightness_dial_direction(self, event):
        if event.type == EV_REL:
            # The Zotac source dials device emits the right dial as REL_WHEEL
            # and the left dial as REL_HWHEEL. Only the right dial drives
            # brightness changes in DeckyZone.
            if event.code != REL_WHEEL or event.value == 0:
                return None
            return "up" if event.value > 0 else "down"

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

    async def _stop_home_button_listener(self, timeout=None):
        self._home_button_running = False

        if self._home_button_task and not self._home_button_task.done():
            stopped = await self._cancel_task(self._home_button_task, timeout=timeout)
            if not stopped:
                return False

        self._home_button_task = None
        self._home_button_device_path = None
        return True

    async def stop_home_button_listener(self):
        return await self._stop_home_button_listener()

    async def stop_home_button_listener_for_unload(self):
        changed = self._home_button_task is not None and not self._home_button_task.done()
        self._home_button_running = False
        self._home_button_task = None
        self._home_button_device_path = None
        return self._cleanup_step_result(
            ok=True,
            changed=changed,
            message=(
                ""
                if not changed
                else "Home button listener stop requested without waiting."
            ),
        )

    async def _enable_home_button_navigation(self):
        try:
            await self.start_home_button_listener()
            return True
        except Exception as error:
            self.logger.warning(f"Failed to enable Home button navigation: {error}")
            try:
                await self.stop_home_button_listener()
            except Exception:
                pass
            return False

    async def _disable_home_button_navigation(self):
        try:
            await self.stop_home_button_listener()
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
        base_profile_result = self._sync_runtime_input_profile_state(
            self._active_per_game_app_id
        )
        if not base_profile_result:
            return False

        if self._should_enable_home_button_navigation():
            listener_result = await self._enable_home_button_navigation()
            if not listener_result:
                return False

            try:
                return self._load_home_button_override_profile()
            except Exception as error:
                self.logger.warning(
                    f"Failed to activate Home button override profile: {error}"
                )
                try:
                    await self.stop_home_button_listener()
                except Exception:
                    pass
                try:
                    self._restore_home_button_profile()
                except Exception as restore_error:
                    self.logger.warning(
                        "Failed to restore Home button override profile after error: "
                        f"{restore_error}"
                    )
                return False

        listener_result = await self._disable_home_button_navigation()
        if not listener_result:
            return False

        try:
            return self._restore_home_button_profile()
        except Exception as error:
            self.logger.warning(
                f"Failed to restore Home button override profile: {error}"
            )
            return False

    async def sync_home_button_navigation_state(self):
        return await self._sync_home_button_navigation_state()

    def _should_enable_brightness_dial_fixer(self):
        return self.settings_store.get_brightness_dial_fix_enabled() and (
            self._startup_target_active
            or self._temporary_target_mode == MISSING_GLYPH_FIX_TARGET
        )

    async def _sync_brightness_dial_fixer_state(self):
        if self._should_enable_brightness_dial_fixer():
            return await self.start_brightness_dial_fixer()

        return await self.stop_brightness_dial_fixer()

    async def sync_brightness_dial_fixer_state(self):
        return await self._sync_brightness_dial_fixer_state()

    async def _sync_rumble_state(self, app_id=None):
        effective_enabled = self._get_effective_rumble_enabled(app_id)

        if not effective_enabled:
            await self.stop_rumble_fixer()
            self._rumble_available = bool(self.probe_rumble_available())
            return True

        device_path = self._resolve_rumble_device_path()
        if not self._validate_rumble_device_path(device_path):
            self._rumble_device_path = None
            self._rumble_available = False
            await self.stop_rumble_fixer()
            return True

        self._rumble_device_path = device_path
        self._rumble_available = True

        if self._rumble_task and not self._rumble_task.done():
            return bool(await self._apply_rumble_gain_once(device_path, app_id=app_id))

        return bool(await self.start_rumble_fixer(app_id))

    def _sync_trackpad_suppression_state(self, app_id=None):
        if self._should_disable_trackpads(app_id) or self._should_enable_directional_trackpads(app_id):
            return self._grab_zotac_mouse_device()

        return self._release_zotac_mouse_device()

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

    def set_per_game_settings_enabled(self, app_id, enabled):
        if app_id in (None, "", DEFAULT_APP_ID):
            return self._current_settings()

        if enabled and not self.probe_inputplumber_available():
            return self._current_settings()

        self.settings_store.set_per_game_settings_enabled(app_id, enabled)
        return self._current_settings()

    def set_button_prompt_fix_enabled(self, app_id, enabled):
        if app_id in (None, "", DEFAULT_APP_ID):
            return self._current_settings()

        if enabled and not self.probe_inputplumber_available():
            return self._current_settings()

        self.settings_store.set_button_prompt_fix_enabled(app_id, enabled)
        return self._current_settings()

    def set_per_game_trackpads_disabled(self, app_id, disabled):
        if app_id in (None, "", DEFAULT_APP_ID):
            return self._current_settings()

        if disabled and not self.probe_inputplumber_available():
            return self._current_settings()

        self.settings_store.set_per_game_trackpads_disabled(app_id, disabled)
        return self._current_settings()

    def set_per_game_trackpad_mode(self, app_id, mode):
        if app_id in (None, "", DEFAULT_APP_ID):
            return self._current_settings()

        normalized_mode = trackpad_modes.normalize_trackpad_mode(mode)
        if (
            normalized_mode != trackpad_modes.TRACKPAD_MODE_DEFAULT
            and not self.probe_inputplumber_available()
        ):
            return self._current_settings()

        self.settings_store.set_per_game_trackpad_mode(app_id, normalized_mode)
        return self._current_settings()

    async def set_per_game_rumble_enabled(self, app_id, enabled):
        if app_id in (None, "", DEFAULT_APP_ID):
            return self._current_settings()

        self.settings_store.set_per_game_rumble_enabled(app_id, enabled)
        if str(app_id) == str(self._active_per_game_app_id):
            await self._sync_rumble_state(app_id)
        return self._current_settings()

    async def set_per_game_rumble_intensity(self, app_id, intensity):
        if app_id in (None, "", DEFAULT_APP_ID):
            return self._current_settings()

        intensity = max(0, min(100, int(intensity)))
        self.settings_store.set_per_game_rumble_intensity(app_id, intensity)
        if str(app_id) == str(self._active_per_game_app_id):
            await self._sync_rumble_state(app_id)
        return self._current_settings()

    async def sync_per_game_target(self, app_id):
        app_id = str(app_id or DEFAULT_APP_ID)
        self._active_per_game_app_id = app_id
        per_game_settings_enabled = (
            app_id != DEFAULT_APP_ID
            and self.settings_store.get_per_game_settings_enabled(app_id)
        )
        controller_mode_snapshot = self._get_controller_mode_snapshot()
        if not self._is_controller_mode_snapshot_safe(controller_mode_snapshot):
            await self._reconcile_controller_mode_runtime(controller_mode_snapshot)
            return False
        if not await self._sync_directional_trackpad_source_runtime(app_id):
            return False
        button_prompt_fix_enabled = (
            per_game_settings_enabled
            and self.settings_store.get_button_prompt_fix_enabled(app_id)
        )
        include_mouse = self._should_include_mouse_target(app_id)
        trackpad_result = self._sync_trackpad_suppression_state(app_id)
        rumble_result = await self._sync_rumble_state(app_id)

        if button_prompt_fix_enabled:
            try:
                if not await self.wait_for_inputplumber_dbus_silently():
                    return False
                if not await self._apply_target_devices_with_retries(
                    MISSING_GLYPH_FIX_TARGET,
                    include_mouse=include_mouse,
                ):
                    return False
                self._temporary_target_mode = MISSING_GLYPH_FIX_TARGET
                await self._sync_brightness_dial_fixer_state()
                profile_result = await self._sync_home_button_navigation_state()
                return trackpad_result and rumble_result and profile_result
            except subprocess.CalledProcessError as error:
                detail = (error.stderr or error.stdout or str(error)).strip()
                self.logger.warning(f"Failed to apply per-game controller override: {detail}")
                return False
            except Exception as error:
                self.logger.warning(f"Failed to apply per-game controller override: {error}")
                return False

        if self._temporary_target_mode != MISSING_GLYPH_FIX_TARGET:
            if self.settings_store.get_startup_apply_enabled() and not self._startup_target_active:
                try:
                    if not await self.wait_for_inputplumber_dbus_silently():
                        return False
                    detail = await self._apply_startup_runtime_with_retries()
                    if detail is not None:
                        self.logger.warning(
                            f"Failed to restore inherited controller target: {detail}"
                        )
                        return False
                except subprocess.CalledProcessError as error:
                    detail = (error.stderr or error.stdout or str(error)).strip()
                    self.logger.warning(
                        f"Failed to restore inherited controller target: {detail}"
                    )
                    return False
                except Exception as error:
                    self.logger.warning(
                        f"Failed to restore inherited controller target: {error}"
                    )
                    return False

            profile_result = await self._sync_home_button_navigation_state()
            return trackpad_result and rumble_result and profile_result

        try:
            if self.settings_store.get_startup_apply_enabled():
                if not await self.wait_for_inputplumber_dbus_silently():
                    return False
                detail = await self._apply_startup_runtime_with_retries()
                if detail is not None:
                    self.logger.warning(f"Failed to restore inherited controller target: {detail}")
                    return False
            else:
                self._restart_inputplumber()
                self._startup_target_active = False
                self._temporary_target_mode = None
                await self._sync_brightness_dial_fixer_state()
                await self._sync_rumble_state(app_id)
                await self._sync_home_button_navigation_state()
                return True
            return True
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or str(error)).strip()
            self.logger.warning(f"Failed to restore inherited controller target: {detail}")
            return False
        except Exception as error:
            self.logger.warning(f"Failed to restore inherited controller target: {error}")
            return False

    def set_missing_glyph_fix_enabled(self, app_id, enabled):
        return self.set_button_prompt_fix_enabled(app_id, enabled)

    def set_missing_glyph_fix_trackpads_disabled(self, app_id, disabled):
        return self.set_per_game_trackpads_disabled(app_id, disabled)

    async def sync_missing_glyph_fix_target(self, app_id):
        return await self.sync_per_game_target(app_id)

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

        return sorted(str(path) for path in hidraw_class_path.glob("hidraw*/device"))

    def _is_zotac_hid_config_path(self, config_path):
        return Path(config_path, "save_config").is_file()

    def _resolve_zotac_hid_config_path(self):
        for config_path in self._get_zotac_hid_config_paths():
            if self._is_zotac_hid_config_path(config_path):
                return str(Path(config_path) / ZOTAC_HID_CONFIG_MATCH_MARKER)

        return None

    def _get_zotac_controller_hidraw_paths(self):
        hidraw_class_root = Path("/sys/class/hidraw")
        if not hidraw_class_root.exists():
            return []

        matching_device_paths = []
        for hidraw_class_path in sorted(hidraw_class_root.glob("hidraw*")):
            try:
                if self._is_zotac_controller_hidraw_path(hidraw_class_path):
                    matching_device_paths.append(str(Path("/dev") / hidraw_class_path.name))
            except Exception:
                continue

        return matching_device_paths

    def _read_sysfs_attribute_upwards(self, start_path, attribute_name):
        for candidate_path in [start_path, *start_path.parents]:
            attribute_path = candidate_path / attribute_name
            try:
                if attribute_path.is_file():
                    return self._read_text(attribute_path)
            except Exception:
                continue

        return None

    def _is_zotac_controller_hidraw_path(self, hidraw_class_path):
        device_path = Path(hidraw_class_path, "device").resolve()
        vendor_id = (self._read_sysfs_attribute_upwards(device_path, "idVendor") or "").lower()
        product_id = (self._read_sysfs_attribute_upwards(device_path, "idProduct") or "").lower()
        interface_num = (self._read_sysfs_attribute_upwards(device_path, "bInterfaceNumber") or "").lower()
        return (
            vendor_id in ZOTAC_CONTROLLER_VENDOR_IDS
            and product_id == ZOTAC_CONTROLLER_PRODUCT_ID
            and interface_num == ZOTAC_CONTROLLER_INTERFACE_NUM
        )

    def _resolve_zotac_controller_hidraw_path(self):
        candidate_paths = self._get_zotac_controller_hidraw_paths()
        if candidate_paths:
            return candidate_paths[0]

        return None

    def _resolve_zotac_command_hidraw_path(self):
        return self._resolve_zotac_controller_hidraw_path()

    def _zotac_calc_crc(self, buffer):
        crc = 0
        for value in buffer[4:0x3E]:
            h1 = (crc ^ value) & 0xFF
            h2 = h1 & 0x0F
            h3 = (h2 << 4) ^ h1
            h4 = h3 >> 4
            crc = (((((h3 << 1) ^ h4) << 4) ^ h2) << 3) ^ h4 ^ (crc >> 8)
            crc &= 0xFFFF
        return crc

    def _zotac_make_packet(self, seq, command, data=b""):
        buffer = bytearray(ZOTAC_RAW_REPORT_SIZE)
        buffer[0] = ZOTAC_RAW_HEADER_TAG
        buffer[1] = 0x00
        buffer[2] = seq & 0xFF
        buffer[3] = ZOTAC_RAW_PAYLOAD_SIZE
        buffer[4] = command
        if data:
            buffer[5:5 + len(data)] = data
        else:
            buffer[5] = 0x00
        crc = self._zotac_calc_crc(buffer)
        buffer[0x3E] = (crc >> 8) & 0xFF
        buffer[0x3F] = crc & 0xFF
        return bytes(buffer)

    def _normalize_zotac_reply(self, raw_reply):
        if len(raw_reply) >= 65 and raw_reply[0] == 0x00 and raw_reply[1] == ZOTAC_RAW_HEADER_TAG:
            return raw_reply[1:65]
        if len(raw_reply) >= ZOTAC_RAW_REPORT_SIZE and raw_reply[0] == ZOTAC_RAW_HEADER_TAG:
            return raw_reply[:ZOTAC_RAW_REPORT_SIZE]
        raise RuntimeError("Unexpected Zotac HID reply.")

    def _read_zotac_raw_reply(self, fd, seq, expected_command=None):
        deadline = time.monotonic() + ZOTAC_RAW_REPLY_TIMEOUT_SECONDS
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError("Timed out waiting for Zotac HID reply.")

            readable, _, _ = select.select([fd], [], [], remaining)
            if not readable:
                raise RuntimeError("Timed out waiting for Zotac HID reply.")

            reply = self._normalize_zotac_reply(os.read(fd, 65))
            if reply[2] != (seq & 0xFF):
                continue
            if expected_command is not None and reply[4] != expected_command:
                continue
            return reply

    def _send_zotac_raw_command(self, device_path, command, data=b"", expected_command=None):
        fd = os.open(device_path, os.O_RDWR)
        seq = self._zotac_raw_command_seq & 0xFF
        self._zotac_raw_command_seq = (self._zotac_raw_command_seq + 1) & 0xFF
        try:
            packet = self._zotac_make_packet(seq, command, data)
            os.write(fd, b"\x00" + packet)
            return self._read_zotac_raw_reply(
                fd,
                seq,
                expected_command=expected_command if expected_command is not None else command,
            )
        finally:
            os.close(fd)

    def _get_zotac_button_mapping(self, device_path, button_id):
        reply = self._send_zotac_raw_command(
            device_path,
            ZOTAC_RAW_CMD_GET_BUTTON_MAPPING,
            bytes([button_id]),
            expected_command=ZOTAC_RAW_CMD_GET_BUTTON_MAPPING,
        )
        mapping_payload = bytes(
            reply[5:5 + trackpad_modes.ZOTAC_BUTTON_MAPPING_PAYLOAD_SIZE]
        )
        if len(mapping_payload) != trackpad_modes.ZOTAC_BUTTON_MAPPING_PAYLOAD_SIZE:
            raise RuntimeError(
                f"Incomplete trackpad mapping reply for button 0x{button_id:02x}"
            )
        if mapping_payload[trackpad_modes.ZOTAC_BUTTON_MAPPING_SOURCE_INDEX] != button_id:
            raise RuntimeError(
                f"Unexpected trackpad mapping source id for button 0x{button_id:02x}"
            )
        return mapping_payload

    def _set_zotac_button_mapping(self, device_path, mapping_payload):
        if (
            len(mapping_payload)
            != trackpad_modes.ZOTAC_BUTTON_MAPPING_PAYLOAD_SIZE
        ):
            raise RuntimeError("Unexpected Zotac trackpad mapping payload size.")

        reply = self._send_zotac_raw_command(
            device_path,
            ZOTAC_RAW_CMD_SET_BUTTON_MAPPING,
            mapping_payload,
            expected_command=ZOTAC_RAW_CMD_SET_BUTTON_MAPPING,
        )
        if len(reply) <= 6:
            raise RuntimeError("Incomplete Zotac trackpad mapping set reply.")
        if reply[6] != 0:
            raise RuntimeError(
                f"Trackpad mapping update rejected: 0x{reply[6]:02x}"
            )

    def _get_touch_button_mappings(self, device_path):
        button_ids = trackpad_modes.build_directional_trackpad_button_payloads().keys()
        return {
            button_id: self._get_zotac_button_mapping(device_path, button_id)
            for button_id in button_ids
        }

    def _apply_directional_trackpad_button_mappings(self):
        device_path = self._resolve_zotac_command_hidraw_path()
        if not device_path:
            self.logger.warning(
                "Unable to locate Zotac command HID node for directional trackpad mode."
            )
            return False

        desired_mappings = trackpad_modes.build_directional_trackpad_button_payloads()

        try:
            current_mappings = self._get_touch_button_mappings(device_path)
        except Exception as error:
            self.logger.warning(
                f"Failed to read current directional trackpad mappings: {error}"
            )
            return False

        backup_mappings = self._load_directional_trackpad_backup()
        if backup_mappings is None:
            if current_mappings == desired_mappings:
                backup_mappings = trackpad_modes.build_default_trackpad_button_payloads()
                self.logger.warning(
                    "Directional trackpad mappings were already active without a backup; "
                    "using the observed Zotac defaults for restoration."
                )
            else:
                backup_mappings = current_mappings
            try:
                self._store_directional_trackpad_backup(backup_mappings)
            except Exception as error:
                self.logger.warning(
                    f"Failed to store directional trackpad backup mappings: {error}"
                )
                return False

        try:
            for button_id, mapping_payload in desired_mappings.items():
                if current_mappings.get(button_id) == mapping_payload:
                    continue
                self._set_zotac_button_mapping(device_path, mapping_payload)
        except Exception as error:
            self.logger.warning(
                f"Failed to apply directional trackpad mappings: {error}"
            )
            return False

        return True

    def _restore_directional_trackpad_button_mappings(self):
        backup_mappings = self._load_directional_trackpad_backup()
        desired_mappings = backup_mappings or trackpad_modes.build_default_trackpad_button_payloads()

        device_path = self._resolve_zotac_command_hidraw_path()
        if not device_path:
            self.logger.warning(
                "Unable to locate Zotac command HID node while restoring trackpad mappings."
            )
            return False

        try:
            current_mappings = self._get_touch_button_mappings(device_path)
            if not backup_mappings and current_mappings != desired_mappings:
                self.logger.warning(
                    "Directional trackpad backup is missing; restoring observed Zotac defaults."
                )
            for button_id, mapping_payload in desired_mappings.items():
                if current_mappings.get(button_id) == mapping_payload:
                    continue
                self._set_zotac_button_mapping(device_path, mapping_payload)
            if backup_mappings:
                self._clear_directional_trackpad_backup()
        except Exception as error:
            self.logger.warning(
                f"Failed to restore directional trackpad mappings: {error}"
            )
            return False

        return True

    def _get_controller_mode(self, device_path=None):
        if device_path is None:
            device_path = self._resolve_zotac_controller_hidraw_path()
        if not device_path:
            return None

        try:
            reply = self._send_zotac_raw_command(device_path, ZOTAC_RAW_CMD_GET_PROFILE)
            if reply[4] != ZOTAC_RAW_CMD_GET_PROFILE:
                return None
            return ZOTAC_PROFILE_TO_CONTROLLER_MODE.get(reply[5])
        except Exception as error:
            self.logger.warning(f"Failed to read controller mode: {error}")
            return None

    async def set_controller_mode(self, mode):
        normalized_mode = str(mode or "").strip().lower()
        raw_profile = ZOTAC_CONTROLLER_MODE_TO_PROFILE.get(normalized_mode)
        if raw_profile is None:
            return self._current_settings()

        device_path = self._resolve_zotac_controller_hidraw_path()
        if not device_path:
            raise RuntimeError("Controller mode interface unavailable.")

        try:
            reply = self._send_zotac_raw_command(
                device_path,
                ZOTAC_RAW_CMD_SET_PROFILE,
                bytes([raw_profile]),
            )
            if reply[4] != ZOTAC_RAW_CMD_SET_PROFILE:
                raise RuntimeError("Unexpected controller mode reply.")
            if reply[5] != 0:
                raise RuntimeError(f"Controller mode change rejected: 0x{reply[5]:02x}")
        except Exception as error:
            self.logger.warning(f"Failed to set controller mode: {error}")
            raise RuntimeError("Failed to set controller mode.")

        await self._reconcile_controller_mode_runtime(
            self._get_controller_mode_snapshot(),
            update_status=True,
        )
        return self._current_settings()

    async def _disable_effective_controller_runtime(self):
        had_active_controller_target = (
            self._startup_target_active
            or self._temporary_target_mode == MISSING_GLYPH_FIX_TARGET
        )

        self._startup_target_active = False
        self._temporary_target_mode = None
        self._release_zotac_mouse_device()

        brightness_result = await self._sync_brightness_dial_fixer_state()
        profile_result = await self._sync_home_button_navigation_state()
        directional_result = await self._disable_directional_trackpad_source_runtime()

        if not had_active_controller_target:
            return brightness_result and profile_result and directional_result

        return brightness_result and profile_result and directional_result

    async def _reconcile_controller_mode_runtime(
        self,
        controller_mode_snapshot=None,
        update_status=False,
    ):
        controller_mode_snapshot = controller_mode_snapshot or self._get_controller_mode_snapshot()
        controller_mode_safe = self._is_controller_mode_snapshot_safe(
            controller_mode_snapshot
        )
        startup_apply_enabled = self.settings_store.get_startup_apply_enabled()

        if not controller_mode_safe:
            await self._disable_effective_controller_runtime()
            if update_status and startup_apply_enabled:
                self._set_status("idle", GAMEPAD_MODE_REQUIRED_MESSAGE)
            return controller_mode_snapshot

        if (
            not startup_apply_enabled
            or self._startup_target_active
            or self._temporary_target_mode == MISSING_GLYPH_FIX_TARGET
        ):
            return controller_mode_snapshot

        try:
            if not await self.wait_for_inputplumber_dbus_silently():
                if update_status:
                    self._set_status(
                        "failed",
                        f"InputPlumber D-Bus was not ready within {READY_TIMEOUT_SECONDS:.1f}s.",
                    )
                return controller_mode_snapshot

            detail = await self._apply_startup_runtime_with_retries()
            if detail is not None:
                if update_status:
                    self._set_status(
                        "failed",
                        f"Failed to apply startup mode: {detail}",
                    )
                else:
                    self.logger.warning(
                        f"Failed to apply startup mode after controller mode change: {detail}"
                    )
                return controller_mode_snapshot
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or str(error)).strip()
            if update_status:
                self._set_status("failed", f"Failed to apply startup mode: {detail}")
            else:
                self.logger.warning(
                    f"Failed to apply startup mode after controller mode change: {detail}"
                )
            return controller_mode_snapshot
        except Exception as error:
            if update_status:
                self._set_status("failed", f"Failed to apply startup mode: {error}")
            else:
                self.logger.warning(
                    "Failed to apply startup mode after controller mode change: "
                    f"{error}"
                )
            return controller_mode_snapshot

        self._startup_applied_this_session = True
        self._temporary_target_mode = None
        if update_status:
            self._set_status("applied", STARTUP_MODE_APPLIED_MESSAGE)
        return controller_mode_snapshot

    async def _controller_mode_monitor_loop(self):
        last_controller_mode_signature = None

        while self._controller_mode_monitor_running:
            try:
                controller_mode_snapshot = self._get_controller_mode_snapshot()
                controller_mode_signature = (
                    controller_mode_snapshot["available"],
                    controller_mode_snapshot["mode"],
                )
                if (
                    last_controller_mode_signature is not None
                    and controller_mode_signature != last_controller_mode_signature
                ):
                    await self._reconcile_controller_mode_runtime(
                        controller_mode_snapshot
                    )
                last_controller_mode_signature = controller_mode_signature
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self.logger.warning(f"Controller mode monitor failed: {error}")

            await self.sleep(CONTROLLER_MODE_MONITOR_INTERVAL_SECONDS)

    async def start_controller_mode_monitor(self):
        if self._controller_mode_monitor_task and not self._controller_mode_monitor_task.done():
            return True

        self._controller_mode_monitor_running = True
        self._controller_mode_monitor_task = asyncio.create_task(
            self._controller_mode_monitor_loop()
        )
        return True

    async def stop_controller_mode_monitor(self):
        self._controller_mode_monitor_running = False

        if (
            self._controller_mode_monitor_task
            and not self._controller_mode_monitor_task.done()
        ):
            self._controller_mode_monitor_task.cancel()
            try:
                await self._controller_mode_monitor_task
            except asyncio.CancelledError:
                pass

        self._controller_mode_monitor_task = None
        return True

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
        if enabled and not self.probe_inputplumber_available():
            return self._current_settings()

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
            await self._sync_brightness_dial_fixer_state()
            await self._sync_home_button_navigation_state()
            return False

        try:
            await self._sync_brightness_dial_fixer_state()
            await self._sync_home_button_navigation_state()
            if not await self._disable_directional_trackpad_source_runtime():
                return False
            self._reset_inputplumber_profile_state()
            self._restart_inputplumber()
            if not await self.wait_for_inputplumber_dbus_silently():
                return False
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
        if enabled and not self.settings_store.get_startup_apply_enabled():
            return self._current_settings()

        if enabled and not self.probe_inputplumber_available():
            return self._current_settings()

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

    async def _stop_brightness_dial_fixer(self, timeout=None):
        self._brightness_dial_running = False

        if self._brightness_dial_task and not self._brightness_dial_task.done():
            stopped = await self._cancel_task(
                self._brightness_dial_task,
                timeout=timeout,
            )
            if not stopped:
                return False

        self._brightness_dial_task = None
        self._brightness_dial_device_path = None
        return True

    async def stop_brightness_dial_fixer(self):
        return await self._stop_brightness_dial_fixer()

    async def stop_brightness_dial_fixer_for_unload(self):
        changed = (
            self._brightness_dial_task is not None
            and not self._brightness_dial_task.done()
        )
        self._brightness_dial_running = False
        self._brightness_dial_task = None
        self._brightness_dial_device_path = None
        return self._cleanup_step_result(
            ok=True,
            changed=changed,
            message=(
                ""
                if not changed
                else "Brightness dial listener stop requested without waiting."
            ),
        )

    async def set_brightness_dial_fix_enabled(self, enabled):
        if enabled and not self.settings_store.get_startup_apply_enabled():
            return self._current_settings()

        if enabled and not self.probe_inputplumber_available():
            return self._current_settings()

        self.settings_store.set_brightness_dial_fix_enabled(enabled)
        await self._sync_brightness_dial_fixer_state()

        return self._current_settings()

    def set_trackpad_mode(self, mode):
        normalized_mode = trackpad_modes.normalize_trackpad_mode(mode)
        if (
            normalized_mode != trackpad_modes.TRACKPAD_MODE_DEFAULT
            and not self.probe_inputplumber_available()
        ):
            return self._current_settings()

        self.settings_store.set_trackpad_mode(normalized_mode)
        return self._current_settings()

    def set_trackpads_disabled(self, disabled):
        return self.set_trackpad_mode(
            trackpad_modes.TRACKPAD_MODE_DISABLED
            if disabled
            else trackpad_modes.TRACKPAD_MODE_DEFAULT
        )

    async def set_zotac_glyphs_enabled(self, enabled):
        self.settings_store.set_zotac_glyphs_enabled(enabled)
        return self._current_settings()

    async def set_gamescope_zotac_profile_enabled(self, enabled):
        self.gamescope_display_profiles.set_zotac_profile_enabled(enabled)
        return self._current_settings()

    async def set_gamescope_green_tint_fix_enabled(self, enabled):
        self.gamescope_display_profiles.set_green_tint_fix_enabled(enabled)
        return self._current_settings()

    def remove_gamescope_display_profiles(self):
        try:
            self.gamescope_display_profiles.cleanup_managed_files()
        except Exception as error:
            self.logger.warning(f"Failed to remove Gamescope display profiles: {error}")
        return self._current_settings()

    # TODO: Keep using the current FF_GAIN path for now. Zotac may also support
    # a native HID/sysfs method via save_config, vibration_intensity, and
    # motor_test; a future change could evaluate that path or add a
    # compatibility/testing switch between methods if needed.
    async def _apply_rumble_gain_once(self, device_path=None, app_id=None):
        device_path = device_path or self._rumble_device_path
        if not device_path:
            return False

        try:
            self._write_event_to_device(
                device_path,
                self._build_gain_event(self._get_effective_rumble_intensity(app_id)),
            )
            return True
        except OSError as error:
            self.logger.warning(f"Failed to apply rumble intensity: {error}")
            return False

    async def _rumble_loop(self):
        while self._rumble_running:
            await self._apply_rumble_gain_once(
                self._rumble_device_path,
                app_id=self._active_per_game_app_id,
            )
            await self.sleep(DEFAULT_RUMBLE_REAPPLY_INTERVAL_SECONDS)

    async def start_rumble_fixer(self, app_id=None):
        if self._rumble_task and not self._rumble_task.done():
            return True

        if not self.probe_rumble_available():
            return False

        self._rumble_running = True
        await self._apply_rumble_gain_once(self._rumble_device_path, app_id=app_id)
        self._rumble_task = asyncio.create_task(self._rumble_loop())
        return True

    async def _stop_rumble_fixer(self, timeout=None):
        self._rumble_running = False

        if self._rumble_task and not self._rumble_task.done():
            stopped = await self._cancel_task(self._rumble_task, timeout=timeout)
            if not stopped:
                return False

        self._rumble_task = None
        return True

    async def stop_rumble_fixer(self):
        return await self._stop_rumble_fixer()

    async def stop_rumble_fixer_for_unload(self):
        changed = self._rumble_task is not None and not self._rumble_task.done()
        self._rumble_running = False
        self._rumble_task = None
        return self._cleanup_step_result(
            ok=True,
            changed=changed,
            message=(
                ""
                if not changed
                else "Rumble fixer stop requested without waiting."
            ),
        )

    async def set_rumble_enabled(self, enabled):
        self.settings_store.set_rumble_enabled(enabled)
        await self._sync_rumble_state()
        return self._current_settings()

    async def set_rumble_intensity(self, intensity):
        intensity = max(0, min(100, int(intensity)))
        self.settings_store.set_rumble_intensity(intensity)
        await self._sync_rumble_state()
        return self._current_settings()

    async def test_rumble(self):
        intensity = max(0.0, min(1.0, self._get_effective_rumble_intensity() / 100.0))
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

        controller_mode_snapshot = self._get_controller_mode_snapshot()
        if not self._is_controller_mode_snapshot_safe(controller_mode_snapshot):
            await self._reconcile_controller_mode_runtime(
                controller_mode_snapshot,
                update_status=True,
            )
            return self.get_status()

        if not await self.wait_for_inputplumber_dbus():
            return self.get_status()

        self.log_privilege_context()

        try:
            self._set_status("waiting", "Waiting for InputPlumber target attachment.")
            detail = await self._apply_startup_runtime_with_retries()
            if detail is not None:
                self._set_status(
                    "failed",
                    f"Failed to apply startup mode: {detail}",
                )
                return self.get_status()
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or str(error)).strip()
            self._set_status("failed", f"Failed to apply startup mode: {detail}")
            return self.get_status()
        except Exception as error:
            self._set_status("failed", f"Failed to apply startup mode: {error}")
            return self.get_status()

        self._startup_applied_this_session = True
        self._temporary_target_mode = None
        self._set_status("applied", STARTUP_MODE_APPLIED_MESSAGE)
        return self.get_status()

    def _cleanup_step_result(self, ok=True, changed=False, message=""):
        return {
            "ok": bool(ok),
            "changed": bool(changed),
            "message": str(message or ""),
        }

    def _normalize_cleanup_step_result(self, name, result):
        if isinstance(result, dict):
            return {
                "name": name,
                "ok": bool(result.get("ok", True)),
                "changed": bool(result.get("changed", False)),
                "message": str(result.get("message") or ""),
            }

        if isinstance(result, bool):
            return {
                "name": name,
                "ok": result,
                "changed": False,
                "message": "" if result else "Action reported failure.",
            }

        return {
            "name": name,
            "ok": True,
            "changed": False,
            "message": "",
        }

    async def _run_cleanup_step(self, steps, name, action):
        self.logger.info(f"DeckyZone cleanup step {name} starting")
        started_at = time.monotonic()
        try:
            result = action()
            if asyncio.iscoroutine(result):
                result = await result
            step = self._normalize_cleanup_step_result(name, result)
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or str(error)).strip()
            step = {
                "name": name,
                "ok": False,
                "changed": False,
                "message": detail,
            }
        except Exception as error:
            step = {
                "name": name,
                "ok": False,
                "changed": False,
                "message": str(error),
            }

        step["elapsedSeconds"] = time.monotonic() - started_at
        steps.append(step)
        _log_cleanup_step(self.logger, step)
        return step

    def _reset_runtime_flags_for_reset(self):
        changed = any(
            (
                self._startup_applied_this_session,
                self._startup_target_active,
                self._temporary_target_mode is not None,
                self._active_per_game_app_id != DEFAULT_APP_ID,
            )
        )
        self._startup_applied_this_session = False
        self._startup_target_active = False
        self._temporary_target_mode = None
        self._active_per_game_app_id = DEFAULT_APP_ID
        return self._cleanup_step_result(changed=changed)

    def _release_zotac_mouse_device_cleanup_result(self):
        changed = self._zotac_mouse_device_fd is not None
        released = self._release_zotac_mouse_device()
        return self._cleanup_step_result(
            ok=released,
            changed=changed,
            message="" if released else "Failed to release Zotac mouse input device.",
        )

    def _release_zotac_mouse_device_for_reset(self):
        return self._release_zotac_mouse_device_cleanup_result()

    def _reset_runtime_flags_for_unload(self):
        changed = any(
            (
                self._startup_target_active,
                self._temporary_target_mode is not None,
                self._active_per_game_app_id != DEFAULT_APP_ID,
            )
        )
        self._startup_target_active = False
        self._temporary_target_mode = None
        self._active_per_game_app_id = DEFAULT_APP_ID
        return self._cleanup_step_result(changed=changed)

    def _restore_inputplumber_profiles_for_unload(self):
        if not self.probe_inputplumber_available():
            return self._cleanup_step_result(
                ok=True,
                changed=False,
                message="InputPlumber unavailable; skipped live profile restore.",
            )

        changed = False
        if self._home_button_override_active:
            self._restore_home_button_profile()
            changed = True

        if self._runtime_input_profile_active:
            self._restore_runtime_input_profile()
            changed = True

        self._reset_inputplumber_profile_state()
        return self._cleanup_step_result(changed=changed)

    async def _remove_directional_trackpad_runtime_for_unload(self):
        result = await self._disable_directional_trackpad_source_runtime_result(
            restore_only_with_runtime_state=True
        )
        if not result["ok"] and not result["message"]:
            result["message"] = "Failed to restore directional trackpad runtime."
        return result

    async def _remove_directional_trackpad_runtime_for_reset(
        self,
        force_restart=False,
    ):
        result = await self._disable_directional_trackpad_source_runtime_result(
            force_restart=force_restart
        )
        if not result["ok"] and not result["message"]:
            result["message"] = "Failed to restore directional trackpad runtime."
        return result

    def _remove_plugin_runtime_files(self):
        changed = False
        runtime_dir = Path(decky.DECKY_PLUGIN_RUNTIME_DIR)
        for filename in (
            RUNTIME_INPUTPLUMBER_PROFILE_FILENAME,
            HOME_BUTTON_OVERRIDE_PROFILE_FILENAME,
            DIRECTIONAL_TRACKPAD_BACKUP_FILENAME,
        ):
            path = runtime_dir / filename
            if not path.exists():
                continue
            if path.is_dir():
                raise IsADirectoryError(str(path))
            path.unlink()
            changed = True

        self._directional_trackpad_backup = None

        try:
            runtime_dir.rmdir()
        except OSError:
            pass

        return self._cleanup_step_result(changed=changed)

    def _get_managed_gamescope_profile_paths(self):
        paths = []
        for attribute_name in (
            "managed_profile_path",
            "legacy_managed_green_tint_profile_path",
            "legacy_managed_base_profile_path",
        ):
            path = getattr(self.gamescope_display_profiles, attribute_name, None)
            if path is not None:
                paths.append(Path(path))
        return paths

    def _cleanup_gamescope_display_profiles_for_reset(self):
        changed = any(
            path.exists() for path in self._get_managed_gamescope_profile_paths()
        )
        self.gamescope_display_profiles.cleanup_managed_files()
        return self._cleanup_step_result(changed=changed)

    def _reset_settings_for_reset(self):
        self.settings_store.reset_settings()
        return self._cleanup_step_result(changed=True)

    async def reset_plugin_state(self):
        steps = []
        force_inputplumber_restart = bool(
            self._startup_target_active
            or self._temporary_target_mode is not None
        )

        await self._run_cleanup_step(
            steps,
            "stopControllerModeMonitor",
            self.stop_controller_mode_monitor,
        )
        await self._run_cleanup_step(
            steps,
            "resetRuntimeFlags",
            self._reset_runtime_flags_for_reset,
        )
        await self._run_cleanup_step(
            steps,
            "stopHomeButtonListener",
            self.stop_home_button_listener,
        )
        await self._run_cleanup_step(
            steps,
            "restoreInputPlumberProfile",
            self._restore_or_sanitize_inputplumber_profiles_for_reset,
        )
        await self._run_cleanup_step(
            steps,
            "stopBrightnessDialFixer",
            self.stop_brightness_dial_fixer,
        )
        await self._run_cleanup_step(
            steps,
            "releaseTrackpadMouseGrab",
            self._release_zotac_mouse_device_for_reset,
        )
        await self._run_cleanup_step(
            steps,
            "removeDirectionalTrackpadRuntime",
            lambda: self._remove_directional_trackpad_runtime_for_reset(
                force_restart=force_inputplumber_restart
            ),
        )
        await self._run_cleanup_step(
            steps,
            "stopRumbleFixer",
            self.stop_rumble_fixer,
        )
        await self._run_cleanup_step(
            steps,
            "removeRuntimeFiles",
            self._remove_plugin_runtime_files,
        )
        await self._run_cleanup_step(
            steps,
            "removeGamescopeDisplayProfiles",
            self._cleanup_gamescope_display_profiles_for_reset,
        )
        await self._run_cleanup_step(
            steps,
            "resetSettings",
            self._reset_settings_for_reset,
        )

        self._set_status("disabled", DISABLED_MESSAGE)
        ok = all(step["ok"] for step in steps)
        return {
            "ok": ok,
            "settings": self.get_settings(),
            "status": self.get_status(),
            "steps": steps,
        }

    async def cleanup_for_unload(self):
        steps = []
        await self._run_cleanup_step(
            steps,
            "stopControllerModeMonitor",
            self.stop_controller_mode_monitor,
        )
        await self._run_cleanup_step(
            steps,
            "resetRuntimeFlags",
            self._reset_runtime_flags_for_unload,
        )
        await self._run_cleanup_step(
            steps,
            "stopHomeButtonListener",
            self.stop_home_button_listener_for_unload,
        )
        await self._run_cleanup_step(
            steps,
            "restoreInputPlumberProfile",
            self._restore_inputplumber_profiles_for_unload,
        )
        await self._run_cleanup_step(
            steps,
            "stopBrightnessDialFixer",
            self.stop_brightness_dial_fixer_for_unload,
        )
        await self._run_cleanup_step(
            steps,
            "releaseTrackpadMouseGrab",
            self._release_zotac_mouse_device_cleanup_result,
        )
        await self._run_cleanup_step(
            steps,
            "removeDirectionalTrackpadRuntime",
            self._remove_directional_trackpad_runtime_for_unload,
        )
        await self._run_cleanup_step(
            steps,
            "stopRumbleFixer",
            self.stop_rumble_fixer_for_unload,
        )

        return {
            "ok": all(step["ok"] for step in steps),
            "steps": steps,
        }

    async def cleanup(self):
        return await self.cleanup_for_unload()


class Plugin:
    def __init__(self, service=None):
        self.loop = None
        self.startup_task = None
        self.service = service or DeckyZoneService()

    async def _cancel_startup_task(self, timeout=None):
        step = {
            "name": "cancelStartupTask",
            "ok": True,
            "changed": False,
            "message": "",
        }
        if self.startup_task is None:
            return step

        if self.startup_task.done():
            self.startup_task = None
            return step

        step["changed"] = True
        self.startup_task.cancel()
        if timeout is None:
            try:
                await self.startup_task
            except asyncio.CancelledError:
                pass
            except Exception as error:
                step["ok"] = False
                step["message"] = str(error)
                decky.logger.warning(f"Failed to cancel startup apply task: {error}")
            finally:
                self.startup_task = None
            return step

        done, pending = await asyncio.wait({self.startup_task}, timeout=timeout)
        if pending:
            step["ok"] = False
            step["message"] = "Startup apply task did not stop before cleanup timeout."
            return step

        try:
            next(iter(done)).result()
        except asyncio.CancelledError:
            pass
        except Exception as error:
            step["ok"] = False
            step["message"] = str(error)
            decky.logger.warning(f"Failed to cancel startup apply task: {error}")

        self.startup_task = None

        return step

    def _request_startup_task_cancel_for_unload(self):
        step = {
            "name": "cancelStartupTask",
            "ok": True,
            "changed": False,
            "message": "",
        }
        if self.startup_task is None:
            return step

        if self.startup_task.done():
            self.startup_task = None
            return step

        self.startup_task.cancel()
        self.startup_task = None
        step["changed"] = True
        step["message"] = "Startup apply task cancel requested without waiting."
        return step

    def _normalize_cleanup_step_result(self, name, result):
        if hasattr(self.service, "_normalize_cleanup_step_result"):
            return self.service._normalize_cleanup_step_result(name, result)

        if isinstance(result, dict):
            return {
                "name": name,
                "ok": bool(result.get("ok", True)),
                "changed": bool(result.get("changed", False)),
                "message": str(result.get("message") or ""),
            }

        if isinstance(result, bool):
            return {
                "name": name,
                "ok": result,
                "changed": False,
                "message": "" if result else "Action reported failure.",
            }

        return {
            "name": name,
            "ok": True,
            "changed": False,
            "message": "",
        }

    async def _run_cleanup_step(self, steps, name, action):
        decky.logger.info(f"DeckyZone cleanup step {name} starting")
        started_at = time.monotonic()
        try:
            result = action()
            if asyncio.iscoroutine(result):
                result = await result
            step = self._normalize_cleanup_step_result(name, result)
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or str(error)).strip()
            step = {
                "name": name,
                "ok": False,
                "changed": False,
                "message": detail,
            }
        except Exception as error:
            step = {
                "name": name,
                "ok": False,
                "changed": False,
                "message": str(error),
            }

        step["elapsedSeconds"] = time.monotonic() - started_at
        steps.append(step)
        _log_cleanup_step(decky.logger, step)
        return step

    async def _reset_plugin_cleanup(self):
        steps = []
        startup_step = await self._run_cleanup_step(
            steps,
            "cancelStartupTask",
            self._cancel_startup_task,
        )
        if hasattr(self.service, "reset_plugin_state"):
            result = await self.service.reset_plugin_state()
        else:
            if hasattr(self.service, "cleanup"):
                await self.service.cleanup()
            else:
                if hasattr(self.service, "stop_brightness_dial_fixer"):
                    await self.service.stop_brightness_dial_fixer()
                await self.service.stop_rumble_fixer()
            if hasattr(self.service, "remove_gamescope_display_profiles"):
                self.service.remove_gamescope_display_profiles()
            plugin_settings.reset_settings()
            result = {
                "ok": True,
                "settings": self.service.get_settings(),
                "status": self.service.get_status(),
                "steps": [],
            }

        steps = [startup_step, *result.get("steps", [])]
        result["steps"] = steps
        result["ok"] = bool(startup_step["ok"] and result.get("ok", True))
        return result

    def _log_cleanup_result(self, action_name, result):
        elapsed = sum(
            step.get("elapsedSeconds", 0)
            for step in result.get("steps", [])
            if isinstance(step.get("elapsedSeconds"), (int, float))
        )
        decky.logger.info(
            f"DeckyZone {action_name} cleanup finished: "
            f"ok={result.get('ok')} elapsed={elapsed:.3f}s"
        )

    async def get_status(self):
        return self.service.get_status()

    async def get_settings(self):
        return self.service.get_settings()

    async def get_debug_info(self):
        return self.service.get_debug_info()

    async def reset_plugin(self):
        result = await self._reset_plugin_cleanup()
        self._log_cleanup_result("reset", result)
        return result

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

    async def set_controller_mode(self, mode):
        return await self.service.set_controller_mode(mode)

    async def set_rumble_enabled(self, enabled):
        return await self.service.set_rumble_enabled(enabled)

    async def set_rumble_intensity(self, intensity):
        return await self.service.set_rumble_intensity(intensity)

    async def set_brightness_dial_fix_enabled(self, enabled):
        return await self.service.set_brightness_dial_fix_enabled(enabled)

    async def set_trackpad_mode(self, mode):
        return self.service.set_trackpad_mode(mode)

    async def set_trackpads_disabled(self, disabled):
        return self.service.set_trackpads_disabled(disabled)

    async def set_zotac_glyphs_enabled(self, enabled):
        return await self.service.set_zotac_glyphs_enabled(enabled)

    async def set_gamescope_zotac_profile_enabled(self, enabled):
        return await self.service.set_gamescope_zotac_profile_enabled(enabled)

    async def set_gamescope_green_tint_fix_enabled(self, enabled):
        return await self.service.set_gamescope_green_tint_fix_enabled(enabled)

    async def set_per_game_settings_enabled(self, app_id, enabled):
        return self.service.set_per_game_settings_enabled(app_id, enabled)

    async def set_button_prompt_fix_enabled(self, app_id, enabled):
        return self.service.set_button_prompt_fix_enabled(app_id, enabled)

    async def set_per_game_trackpad_mode(self, app_id, mode):
        return self.service.set_per_game_trackpad_mode(app_id, mode)

    async def set_per_game_trackpads_disabled(self, app_id, disabled):
        return self.service.set_per_game_trackpads_disabled(app_id, disabled)

    async def set_per_game_rumble_enabled(self, app_id, enabled):
        return await self.service.set_per_game_rumble_enabled(app_id, enabled)

    async def set_per_game_rumble_intensity(self, app_id, intensity):
        return await self.service.set_per_game_rumble_intensity(app_id, intensity)

    async def set_per_game_m1_remap_target(self, app_id, target):
        return self.service.set_per_game_m1_remap_target(app_id, target)

    async def set_per_game_m2_remap_target(self, app_id, target):
        return self.service.set_per_game_m2_remap_target(app_id, target)

    async def sync_per_game_target(self, app_id):
        if self.startup_task is not None:
            try:
                await self.startup_task
            except asyncio.CancelledError:
                pass
            finally:
                if self.startup_task.done():
                    self.startup_task = None
        if hasattr(self.service, "sync_per_game_target"):
            return await self.service.sync_per_game_target(app_id)
        return await self.service.sync_missing_glyph_fix_target(app_id)

    async def set_missing_glyph_fix_enabled(self, app_id, enabled):
        return await self.set_button_prompt_fix_enabled(app_id, enabled)

    async def set_missing_glyph_fix_trackpads_disabled(self, app_id, disabled):
        return await self.set_per_game_trackpads_disabled(app_id, disabled)

    async def sync_missing_glyph_fix_target(self, app_id):
        return await self.sync_per_game_target(app_id)

    async def test_rumble(self):
        return await self.service.test_rumble()

    async def get_latest_version_num(self):
        return await self.service.get_latest_version_num()

    async def ota_update(self):
        return await self.service.ota_update()

    async def _main(self):
        self.loop = asyncio.get_event_loop()
        decky.logger.info("DeckyZone starting")
        settings = self.service.get_settings()
        await self.service.start_controller_mode_monitor()
        if settings["rumbleEnabled"]:
            await self.service.start_rumble_fixer()
        if settings["startupApplyEnabled"]:
            self.startup_task = self.loop.create_task(self.service.apply_startup_mode())
        else:
            self.service.set_startup_apply_enabled(False)

    async def _unload(self):
        decky.logger.info("DeckyZone stopping")
        steps = []
        startup_step = await self._run_cleanup_step(
            steps,
            "cancelStartupTask",
            self._request_startup_task_cancel_for_unload,
        )

        if hasattr(self.service, "cleanup_for_unload"):
            result = await self.service.cleanup_for_unload()
        elif hasattr(self.service, "cleanup"):
            result = await self.service.cleanup()
        else:
            await self.service.stop_controller_mode_monitor()
            if hasattr(self.service, "stop_brightness_dial_fixer"):
                await self.service.stop_brightness_dial_fixer()
            await self.service.stop_rumble_fixer()
            result = {
                "ok": True,
                "steps": [],
            }

        result["steps"] = [startup_step, *result.get("steps", [])]
        result["ok"] = bool(startup_step["ok"] and result.get("ok", True))
        self._log_cleanup_result("unload", result)

    async def _uninstall(self):
        decky.logger.info("DeckyZone uninstall")
        result = await self._reset_plugin_cleanup()
        self._log_cleanup_result("uninstall", result)

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
