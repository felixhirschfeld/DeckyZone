import os

from settings import SettingsManager


STARTUP_APPLY_KEY = "startupApplyEnabled"
HOME_BUTTON_ENABLED_KEY = "homeButtonEnabled"
BRIGHTNESS_DIAL_FIX_ENABLED_KEY = "brightnessDialFixEnabled"
RUMBLE_ENABLED_KEY = "rumbleEnabled"
RUMBLE_INTENSITY_KEY = "rumbleIntensity"
PER_GAME_SETTINGS_KEY = "perGameSettings"
LEGACY_MISSING_GLYPH_FIX_GAMES_KEY = "missingGlyphFixGames"
ENABLED_KEY = "enabled"
BUTTON_PROMPT_FIX_ENABLED_KEY = "buttonPromptFixEnabled"
DISABLE_TRACKPADS_KEY = "disableTrackpads"
DEFAULT_STARTUP_APPLY_ENABLED = False
DEFAULT_HOME_BUTTON_ENABLED = False
DEFAULT_BRIGHTNESS_DIAL_FIX_ENABLED = False
DEFAULT_RUMBLE_ENABLED = False
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


def _default_per_game_settings_entry():
    return {
        ENABLED_KEY: False,
        BUTTON_PROMPT_FIX_ENABLED_KEY: False,
        DISABLE_TRACKPADS_KEY: True,
    }


def _normalize_legacy_missing_glyph_fix_entry(entry):
    if entry is True:
        return {
            ENABLED_KEY: True,
            BUTTON_PROMPT_FIX_ENABLED_KEY: True,
            DISABLE_TRACKPADS_KEY: True,
        }

    if isinstance(entry, dict):
        return {
            ENABLED_KEY: True,
            BUTTON_PROMPT_FIX_ENABLED_KEY: True,
            DISABLE_TRACKPADS_KEY: bool(entry.get(DISABLE_TRACKPADS_KEY, True)),
        }

    return None


def _normalize_per_game_settings_entry(entry):
    if not isinstance(entry, dict):
        return _normalize_legacy_missing_glyph_fix_entry(entry)

    if ENABLED_KEY not in entry and BUTTON_PROMPT_FIX_ENABLED_KEY not in entry:
        return _normalize_legacy_missing_glyph_fix_entry(entry)

    return {
        ENABLED_KEY: bool(entry.get(ENABLED_KEY, False)),
        BUTTON_PROMPT_FIX_ENABLED_KEY: bool(
            entry.get(BUTTON_PROMPT_FIX_ENABLED_KEY, False)
        ),
        DISABLE_TRACKPADS_KEY: bool(entry.get(DISABLE_TRACKPADS_KEY, True)),
    }


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


def get_per_game_settings():
    settings = _read_settings()
    normalized_games = {}
    games = settings.get(PER_GAME_SETTINGS_KEY, {})
    if isinstance(games, dict):
        for app_id, entry in games.items():
            normalized_entry = _normalize_per_game_settings_entry(entry)
            if normalized_entry is None:
                continue

            normalized_games[str(app_id)] = normalized_entry

    legacy_games = settings.get(LEGACY_MISSING_GLYPH_FIX_GAMES_KEY, {})
    if isinstance(legacy_games, dict):
        for app_id, entry in legacy_games.items():
            normalized_app_id = str(app_id)
            if normalized_app_id in normalized_games:
                continue

            normalized_entry = _normalize_legacy_missing_glyph_fix_entry(entry)
            if normalized_entry is None:
                continue

            normalized_games[normalized_app_id] = normalized_entry

    return normalized_games


def get_per_game_settings_enabled(app_id):
    if app_id is None:
        return False

    entry = get_per_game_settings().get(str(app_id))
    if not entry:
        return False

    return bool(entry.get(ENABLED_KEY, False))


def get_button_prompt_fix_enabled(app_id):
    if app_id is None:
        return False

    entry = get_per_game_settings().get(str(app_id))
    if not entry:
        return False

    return bool(entry.get(BUTTON_PROMPT_FIX_ENABLED_KEY, False))


def get_per_game_trackpads_disabled(app_id):
    if app_id is None:
        return False

    entry = get_per_game_settings().get(str(app_id))
    if not entry:
        return False

    return bool(entry.get(DISABLE_TRACKPADS_KEY, True))


def set_per_game_settings_enabled(app_id, enabled):
    if app_id is None:
        return get_per_game_settings()

    games = get_per_game_settings()
    app_id = str(app_id)
    entry = games.get(app_id)
    if entry is None and not enabled:
        return get_per_game_settings()

    current_entry = dict(entry or _default_per_game_settings_entry())
    current_entry[ENABLED_KEY] = bool(enabled)
    games[app_id] = current_entry

    _write_setting(PER_GAME_SETTINGS_KEY, games)
    return get_per_game_settings()


def set_button_prompt_fix_enabled(app_id, enabled):
    if app_id is None:
        return get_per_game_settings()

    games = get_per_game_settings()
    app_id = str(app_id)
    entry = games.get(app_id)
    if entry is None and not enabled:
        return get_per_game_settings()

    current_entry = dict(entry or _default_per_game_settings_entry())
    if enabled:
        current_entry[ENABLED_KEY] = True
    current_entry[BUTTON_PROMPT_FIX_ENABLED_KEY] = bool(enabled)
    games[app_id] = current_entry

    _write_setting(PER_GAME_SETTINGS_KEY, games)
    return get_per_game_settings()


def set_per_game_trackpads_disabled(app_id, disabled):
    if app_id is None:
        return get_per_game_settings()

    games = get_per_game_settings()
    app_id = str(app_id)
    entry = games.get(app_id)
    if not entry:
        return get_per_game_settings()

    current_entry = dict(entry)
    current_entry[DISABLE_TRACKPADS_KEY] = bool(disabled)
    games[app_id] = current_entry

    _write_setting(PER_GAME_SETTINGS_KEY, games)
    return get_per_game_settings()


def get_missing_glyph_fix_games():
    legacy_games = {}
    for app_id, entry in get_per_game_settings().items():
        if not entry.get(ENABLED_KEY) or not entry.get(BUTTON_PROMPT_FIX_ENABLED_KEY):
            continue

        legacy_games[app_id] = {
            DISABLE_TRACKPADS_KEY: bool(entry.get(DISABLE_TRACKPADS_KEY, True))
        }

    return legacy_games


def get_missing_glyph_fix_enabled(app_id):
    return get_button_prompt_fix_enabled(app_id)


def get_missing_glyph_fix_trackpads_disabled(app_id):
    return get_per_game_trackpads_disabled(app_id)


def set_missing_glyph_fix_enabled(app_id, enabled):
    return set_button_prompt_fix_enabled(app_id, enabled)


def set_missing_glyph_fix_trackpads_disabled(app_id, disabled):
    return set_per_game_trackpads_disabled(app_id, disabled)
