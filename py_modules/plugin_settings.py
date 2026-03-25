import os

from settings import SettingsManager


STARTUP_APPLY_KEY = "startupApplyEnabled"
HOME_BUTTON_ENABLED_KEY = "homeButtonEnabled"
BRIGHTNESS_DIAL_FIX_ENABLED_KEY = "brightnessDialFixEnabled"
RUMBLE_ENABLED_KEY = "rumbleEnabled"
RUMBLE_INTENSITY_KEY = "rumbleIntensity"
MISSING_GLYPH_FIX_GAMES_KEY = "missingGlyphFixGames"
DISABLE_TRACKPADS_KEY = "disableTrackpads"
DEFAULT_STARTUP_APPLY_ENABLED = True
DEFAULT_HOME_BUTTON_ENABLED = True
DEFAULT_BRIGHTNESS_DIAL_FIX_ENABLED = True
DEFAULT_RUMBLE_ENABLED = True
DEFAULT_RUMBLE_INTENSITY = 75


settings_directory = os.environ["DECKY_PLUGIN_SETTINGS_DIR"]
setting_file = SettingsManager(name="settings", settings_directory=settings_directory)
setting_file.read()


def _read_settings():
    setting_file.read()
    return setting_file.settings


def _write_setting(name, value):
    setting_file.setSetting(name, value)
    setting_file.commit()
    return value


def reset_settings():
    setting_file.read()
    setting_file.settings = {}
    setting_file.commit()
    return {}


def _normalize_missing_glyph_fix_entry(entry):
    if entry is True:
        return {DISABLE_TRACKPADS_KEY: True}

    if isinstance(entry, dict):
        return {
            DISABLE_TRACKPADS_KEY: bool(entry.get(DISABLE_TRACKPADS_KEY, True)),
        }

    return None


def get_startup_apply_enabled():
    settings = _read_settings()
    return bool(settings.get(STARTUP_APPLY_KEY, DEFAULT_STARTUP_APPLY_ENABLED))


def set_startup_apply_enabled(enabled):
    _write_setting(STARTUP_APPLY_KEY, bool(enabled))
    return get_startup_apply_enabled()


def get_home_button_enabled():
    settings = _read_settings()
    return bool(settings.get(HOME_BUTTON_ENABLED_KEY, DEFAULT_HOME_BUTTON_ENABLED))


def set_home_button_enabled(enabled):
    _write_setting(HOME_BUTTON_ENABLED_KEY, bool(enabled))
    return get_home_button_enabled()


def get_brightness_dial_fix_enabled():
    settings = _read_settings()
    return bool(
        settings.get(BRIGHTNESS_DIAL_FIX_ENABLED_KEY, DEFAULT_BRIGHTNESS_DIAL_FIX_ENABLED)
    )


def set_brightness_dial_fix_enabled(enabled):
    _write_setting(BRIGHTNESS_DIAL_FIX_ENABLED_KEY, bool(enabled))
    return get_brightness_dial_fix_enabled()


def get_rumble_enabled():
    settings = _read_settings()
    return bool(settings.get(RUMBLE_ENABLED_KEY, DEFAULT_RUMBLE_ENABLED))


def set_rumble_enabled(enabled):
    _write_setting(RUMBLE_ENABLED_KEY, bool(enabled))
    return get_rumble_enabled()


def get_rumble_intensity():
    settings = _read_settings()
    return int(settings.get(RUMBLE_INTENSITY_KEY, DEFAULT_RUMBLE_INTENSITY))


def set_rumble_intensity(intensity):
    _write_setting(RUMBLE_INTENSITY_KEY, int(intensity))
    return get_rumble_intensity()


def get_missing_glyph_fix_games():
    settings = _read_settings()
    games = settings.get(MISSING_GLYPH_FIX_GAMES_KEY, {})
    if not isinstance(games, dict):
        return {}

    normalized_games = {}
    for app_id, entry in games.items():
        normalized_entry = _normalize_missing_glyph_fix_entry(entry)
        if normalized_entry is None:
            continue

        normalized_games[str(app_id)] = normalized_entry

    return normalized_games


def get_missing_glyph_fix_enabled(app_id):
    if app_id is None:
        return False

    return bool(get_missing_glyph_fix_games().get(str(app_id), False))


def get_missing_glyph_fix_trackpads_disabled(app_id):
    if app_id is None:
        return False

    entry = get_missing_glyph_fix_games().get(str(app_id))
    if not entry:
        return False

    return bool(entry.get(DISABLE_TRACKPADS_KEY, True))


def set_missing_glyph_fix_enabled(app_id, enabled):
    games = get_missing_glyph_fix_games()
    app_id = str(app_id)

    if enabled:
        current_entry = games.get(app_id)
        games[app_id] = current_entry or {DISABLE_TRACKPADS_KEY: True}
    else:
        games.pop(app_id, None)

    _write_setting(MISSING_GLYPH_FIX_GAMES_KEY, games)
    return get_missing_glyph_fix_games()


def set_missing_glyph_fix_trackpads_disabled(app_id, disabled):
    games = get_missing_glyph_fix_games()
    app_id = str(app_id)
    entry = games.get(app_id)

    if not entry:
        return get_missing_glyph_fix_games()

    games[app_id] = {
        DISABLE_TRACKPADS_KEY: bool(disabled),
    }

    _write_setting(MISSING_GLYPH_FIX_GAMES_KEY, games)
    return get_missing_glyph_fix_games()
