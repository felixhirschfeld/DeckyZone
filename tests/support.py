import os
import sys
import types
from pathlib import Path


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

_VALID_ZOTAC_SYSTEM_PROFILE = """gamescope.config.known_displays.zotac_amoled = {
    pretty_name = "DXQ7D0023 AMOLED",
}
-- Match DXQ7D0023
"""

_DECKYZONE_BASE_PROFILE = """gamescope.config.known_displays.zotac_amoled = {
    colorimetry = {
        w = {
            x = 0.3095,
            y = 0.3095,
        },
    },
}
"""

_DECKYZONE_GREEN_TINT_PROFILE = """gamescope.config.known_displays.zotac_amoled = {
    colorimetry = {
        w = {
            x = 0.3070,
            y = 0.3235,
        },
    },
}
"""


def _write_gamescope_display_assets(plugin_dir: Path):
    assets_dir = plugin_dir / "assets" / "gamescope"
    assets_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.joinpath("zotac.zone.oled.lua").write_text(
        _DECKYZONE_BASE_PROFILE,
        encoding="utf-8",
    )
    assets_dir.joinpath("zotac.zone.green-tint.lua").write_text(
        _DECKYZONE_GREEN_TINT_PROFILE,
        encoding="utf-8",
    )


def _write_executable(path: Path, content: str):
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


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
    module.DECKY_PLUGIN_VERSION = "0.0.1-test"
    module.emit = _async_noop
    module.migrate_logs = _noop
    module.migrate_settings = _noop
    module.migrate_runtime = _noop
    return module


os.environ.setdefault("DECKY_PLUGIN_SETTINGS_DIR", "/tmp/deckyzone-settings")
sys.modules.setdefault("settings", _fake_settings_module())
sys.modules.setdefault("decky", _fake_decky_module())

REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (REPO_ROOT, REPO_ROOT / "py_modules"):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

import main  # noqa: E402
import plugin_update  # noqa: E402


class _CompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def reset_test_state():
    _FAKE_SETTINGS_STORE.clear()
    main.plugin_settings.setting_file.settings = {}

