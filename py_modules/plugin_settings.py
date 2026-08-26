import os

from settings import SettingsManager
import trackpad_modes


STARTUP_APPLY_KEY = "startupApplyEnabled"
HOME_BUTTON_ENABLED_KEY = "homeButtonEnabled"
BRIGHTNESS_DIAL_FIX_ENABLED_KEY = "brightnessDialFixEnabled"
FIX_SLEEP_ENABLED_KEY = "fixSleepEnabled"
FIX_SLEEP_ORIGINAL_AMD_IOMMU_OFF_KEY = "fixSleepOriginalAmdIommuOff"
TRACKPAD_MODE_KEY = "trackpadMode"
LEGACY_TRACKPADS_DISABLED_KEY = "trackpadsDisabled"
ZOTAC_GLYPHS_ENABLED_KEY = "zotacGlyphsEnabled"
RUMBLE_ENABLED_KEY = "rumbleEnabled"
RUMBLE_INTENSITY_KEY = "rumbleIntensity"
PER_GAME_SETTINGS_KEY = "perGameSettings"
LEGACY_MISSING_GLYPH_FIX_GAMES_KEY = "missingGlyphFixGames"
ENABLED_KEY = "enabled"
BUTTON_PROMPT_FIX_ENABLED_KEY = "buttonPromptFixEnabled"
PER_GAME_TRACKPAD_MODE_KEY = "trackpadMode"
PER_GAME_RUMBLE_ENABLED_KEY = "rumbleEnabled"
PER_GAME_RUMBLE_INTENSITY_KEY = "rumbleIntensity"
LEGACY_DISABLE_TRACKPADS_KEY = "disableTrackpads"
M1_REMAP_TARGET_KEY = "m1RemapTarget"
M2_REMAP_TARGET_KEY = "m2RemapTarget"
DEFAULT_STARTUP_APPLY_ENABLED = False
DEFAULT_HOME_BUTTON_ENABLED = False
DEFAULT_BRIGHTNESS_DIAL_FIX_ENABLED = False
DEFAULT_FIX_SLEEP_ENABLED = False
DEFAULT_TRACKPAD_MODE = trackpad_modes.DEFAULT_TRACKPAD_MODE
DEFAULT_ZOTAC_GLYPHS_ENABLED = False
DEFAULT_RUMBLE_ENABLED = False
DEFAULT_RUMBLE_INTENSITY = 75
DEFAULT_PER_GAME_REMAP_TARGET = "none"
VALID_PER_GAME_REMAP_TARGETS = {
    DEFAULT_PER_GAME_REMAP_TARGET,
    "a",
    "b",
    "x",
    "y",
    "select",
    "start",
    "lb",
    "rb",
    "lt",
    "rt",
    "ls",
    "rs",
    "dpad_up",
    "dpad_down",
    "dpad_left",
    "dpad_right",
}


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


def _normalize_global_trackpad_mode(settings):
    return trackpad_modes.normalize_trackpad_mode(
        settings.get(TRACKPAD_MODE_KEY),
        legacy_disabled=bool(
            settings.get(
                LEGACY_TRACKPADS_DISABLED_KEY,
                trackpad_modes.is_trackpad_mode_disabled(DEFAULT_TRACKPAD_MODE),
            )
        ),
    )


def _normalize_global_rumble_enabled(settings):
    return bool(settings.get(RUMBLE_ENABLED_KEY, DEFAULT_RUMBLE_ENABLED))


def _normalize_global_rumble_intensity(settings):
    return int(settings.get(RUMBLE_INTENSITY_KEY, DEFAULT_RUMBLE_INTENSITY))


def _default_per_game_settings_entry(settings=None):
    settings = settings or _read_settings()
    return {
        ENABLED_KEY: False,
        BUTTON_PROMPT_FIX_ENABLED_KEY: False,
        PER_GAME_TRACKPAD_MODE_KEY: _normalize_global_trackpad_mode(settings),
        PER_GAME_RUMBLE_ENABLED_KEY: _normalize_global_rumble_enabled(settings),
        PER_GAME_RUMBLE_INTENSITY_KEY: _normalize_global_rumble_intensity(settings),
        M1_REMAP_TARGET_KEY: DEFAULT_PER_GAME_REMAP_TARGET,
        M2_REMAP_TARGET_KEY: DEFAULT_PER_GAME_REMAP_TARGET,
    }


def _normalize_per_game_remap_target(target):
    normalized_target = str(target or "").strip().lower()
    if normalized_target in VALID_PER_GAME_REMAP_TARGETS:
        return normalized_target

    return DEFAULT_PER_GAME_REMAP_TARGET


def _normalize_legacy_missing_glyph_fix_entry(entry, settings):
    if entry is True:
        return {
            ENABLED_KEY: True,
            BUTTON_PROMPT_FIX_ENABLED_KEY: True,
            PER_GAME_TRACKPAD_MODE_KEY: trackpad_modes.TRACKPAD_MODE_DISABLED,
            PER_GAME_RUMBLE_ENABLED_KEY: _normalize_global_rumble_enabled(settings),
            PER_GAME_RUMBLE_INTENSITY_KEY: _normalize_global_rumble_intensity(settings),
            M1_REMAP_TARGET_KEY: DEFAULT_PER_GAME_REMAP_TARGET,
            M2_REMAP_TARGET_KEY: DEFAULT_PER_GAME_REMAP_TARGET,
        }

    if isinstance(entry, dict):
        return {
            ENABLED_KEY: True,
            BUTTON_PROMPT_FIX_ENABLED_KEY: True,
            PER_GAME_TRACKPAD_MODE_KEY: trackpad_modes.normalize_trackpad_mode(
                entry.get(PER_GAME_TRACKPAD_MODE_KEY),
                legacy_disabled=bool(entry.get(LEGACY_DISABLE_TRACKPADS_KEY, True)),
            ),
            PER_GAME_RUMBLE_ENABLED_KEY: bool(
                entry.get(
                    PER_GAME_RUMBLE_ENABLED_KEY,
                    _normalize_global_rumble_enabled(settings),
                )
            ),
            PER_GAME_RUMBLE_INTENSITY_KEY: int(
                entry.get(
                    PER_GAME_RUMBLE_INTENSITY_KEY,
                    _normalize_global_rumble_intensity(settings),
                )
            ),
            M1_REMAP_TARGET_KEY: _normalize_per_game_remap_target(
                entry.get(M1_REMAP_TARGET_KEY)
            ),
            M2_REMAP_TARGET_KEY: _normalize_per_game_remap_target(
                entry.get(M2_REMAP_TARGET_KEY)
            ),
        }

    return None


def _normalize_per_game_settings_entry(entry, settings):
    if not isinstance(entry, dict):
        return _normalize_legacy_missing_glyph_fix_entry(entry, settings)

    if ENABLED_KEY not in entry and BUTTON_PROMPT_FIX_ENABLED_KEY not in entry:
        return _normalize_legacy_missing_glyph_fix_entry(entry, settings)

    return {
        ENABLED_KEY: bool(entry.get(ENABLED_KEY, False)),
        BUTTON_PROMPT_FIX_ENABLED_KEY: bool(
            entry.get(BUTTON_PROMPT_FIX_ENABLED_KEY, False)
        ),
        PER_GAME_TRACKPAD_MODE_KEY: trackpad_modes.normalize_trackpad_mode(
            entry.get(PER_GAME_TRACKPAD_MODE_KEY),
            legacy_disabled=bool(entry.get(LEGACY_DISABLE_TRACKPADS_KEY, False)),
        ),
        PER_GAME_RUMBLE_ENABLED_KEY: bool(
            entry.get(
                PER_GAME_RUMBLE_ENABLED_KEY,
                _normalize_global_rumble_enabled(settings),
            )
        ),
        PER_GAME_RUMBLE_INTENSITY_KEY: int(
            entry.get(
                PER_GAME_RUMBLE_INTENSITY_KEY,
                _normalize_global_rumble_intensity(settings),
            )
        ),
        M1_REMAP_TARGET_KEY: _normalize_per_game_remap_target(
            entry.get(M1_REMAP_TARGET_KEY)
        ),
        M2_REMAP_TARGET_KEY: _normalize_per_game_remap_target(
            entry.get(M2_REMAP_TARGET_KEY)
        ),
    }


def get_startup_apply_enabled():
    settings = _read_settings()
    return bool(settings.get(STARTUP_APPLY_KEY, DEFAULT_STARTUP_APPLY_ENABLED))


def set_startup_apply_enabled(enabled):
    enabled = bool(enabled)
    setting_file.read()
    setting_file.setSetting(STARTUP_APPLY_KEY, enabled)
    if not enabled:
        setting_file.setSetting(HOME_BUTTON_ENABLED_KEY, False)
        setting_file.setSetting(BRIGHTNESS_DIAL_FIX_ENABLED_KEY, False)
    setting_file.commit()
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


def get_fix_sleep_enabled():
    settings = _read_settings()
    return bool(settings.get(FIX_SLEEP_ENABLED_KEY, DEFAULT_FIX_SLEEP_ENABLED))


def set_fix_sleep_enabled(enabled):
    _write_setting(FIX_SLEEP_ENABLED_KEY, bool(enabled))
    return get_fix_sleep_enabled()


def get_fix_sleep_original_amd_iommu_off():
    settings = _read_settings()
    value = settings.get(FIX_SLEEP_ORIGINAL_AMD_IOMMU_OFF_KEY)
    return value if isinstance(value, bool) else None


def set_fix_sleep_original_amd_iommu_off(disabled):
    _write_setting(FIX_SLEEP_ORIGINAL_AMD_IOMMU_OFF_KEY, bool(disabled))
    return get_fix_sleep_original_amd_iommu_off()


def clear_fix_sleep_original_amd_iommu_off():
    setting_file.read()
    setting_file.settings.pop(FIX_SLEEP_ORIGINAL_AMD_IOMMU_OFF_KEY, None)
    setting_file.commit()


def get_trackpad_mode():
    settings = _read_settings()
    return _normalize_global_trackpad_mode(settings)


def set_trackpad_mode(mode):
    normalized_mode = trackpad_modes.normalize_trackpad_mode(mode)
    _write_setting(TRACKPAD_MODE_KEY, normalized_mode)
    return get_trackpad_mode()


def get_trackpads_disabled():
    return trackpad_modes.is_trackpad_mode_disabled(get_trackpad_mode())


def set_trackpads_disabled(disabled):
    return set_trackpad_mode(
        trackpad_modes.TRACKPAD_MODE_DISABLED if disabled else trackpad_modes.TRACKPAD_MODE_DEFAULT
    )


def get_zotac_glyphs_enabled():
    settings = _read_settings()
    return bool(settings.get(ZOTAC_GLYPHS_ENABLED_KEY, DEFAULT_ZOTAC_GLYPHS_ENABLED))


def set_zotac_glyphs_enabled(enabled):
    _write_setting(ZOTAC_GLYPHS_ENABLED_KEY, bool(enabled))
    return get_zotac_glyphs_enabled()


def get_rumble_enabled():
    settings = _read_settings()
    return _normalize_global_rumble_enabled(settings)


def set_rumble_enabled(enabled):
    _write_setting(RUMBLE_ENABLED_KEY, bool(enabled))
    return get_rumble_enabled()


def get_rumble_intensity():
    settings = _read_settings()
    return _normalize_global_rumble_intensity(settings)


def set_rumble_intensity(intensity):
    _write_setting(RUMBLE_INTENSITY_KEY, int(intensity))
    return get_rumble_intensity()


def get_per_game_settings():
    settings = _read_settings()
    normalized_games = {}
    games = settings.get(PER_GAME_SETTINGS_KEY, {})
    if isinstance(games, dict):
        for app_id, entry in games.items():
            normalized_entry = _normalize_per_game_settings_entry(entry, settings)
            if normalized_entry is None:
                continue

            normalized_games[str(app_id)] = normalized_entry

    legacy_games = settings.get(LEGACY_MISSING_GLYPH_FIX_GAMES_KEY, {})
    if isinstance(legacy_games, dict):
        for app_id, entry in legacy_games.items():
            normalized_app_id = str(app_id)
            if normalized_app_id in normalized_games:
                continue

            normalized_entry = _normalize_legacy_missing_glyph_fix_entry(entry, settings)
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


def get_per_game_trackpad_mode(app_id):
    if app_id is None:
        return DEFAULT_TRACKPAD_MODE

    entry = get_per_game_settings().get(str(app_id))
    if not entry:
        return DEFAULT_TRACKPAD_MODE

    return trackpad_modes.normalize_trackpad_mode(
        entry.get(PER_GAME_TRACKPAD_MODE_KEY),
        legacy_disabled=bool(entry.get(LEGACY_DISABLE_TRACKPADS_KEY, False)),
    )


def get_per_game_trackpads_disabled(app_id):
    return trackpad_modes.is_trackpad_mode_disabled(get_per_game_trackpad_mode(app_id))


def get_per_game_rumble_enabled(app_id):
    if app_id is None:
        return DEFAULT_RUMBLE_ENABLED

    entry = get_per_game_settings().get(str(app_id))
    if not entry:
        return DEFAULT_RUMBLE_ENABLED

    return bool(entry.get(PER_GAME_RUMBLE_ENABLED_KEY, DEFAULT_RUMBLE_ENABLED))


def get_per_game_rumble_intensity(app_id):
    if app_id is None:
        return DEFAULT_RUMBLE_INTENSITY

    entry = get_per_game_settings().get(str(app_id))
    if not entry:
        return DEFAULT_RUMBLE_INTENSITY

    return int(entry.get(PER_GAME_RUMBLE_INTENSITY_KEY, DEFAULT_RUMBLE_INTENSITY))


def get_per_game_m1_remap_target(app_id):
    if app_id is None:
        return DEFAULT_PER_GAME_REMAP_TARGET

    entry = get_per_game_settings().get(str(app_id))
    if not entry:
        return DEFAULT_PER_GAME_REMAP_TARGET

    return _normalize_per_game_remap_target(
        entry.get(M1_REMAP_TARGET_KEY, DEFAULT_PER_GAME_REMAP_TARGET)
    )


def get_per_game_m2_remap_target(app_id):
    if app_id is None:
        return DEFAULT_PER_GAME_REMAP_TARGET

    entry = get_per_game_settings().get(str(app_id))
    if not entry:
        return DEFAULT_PER_GAME_REMAP_TARGET

    return _normalize_per_game_remap_target(
        entry.get(M2_REMAP_TARGET_KEY, DEFAULT_PER_GAME_REMAP_TARGET)
    )


def set_per_game_settings_enabled(app_id, enabled):
    if app_id is None:
        return get_per_game_settings()

    games = get_per_game_settings()
    settings = _read_settings()
    app_id = str(app_id)
    entry = games.get(app_id)
    if entry is None and not enabled:
        return get_per_game_settings()

    current_entry = dict(entry or _default_per_game_settings_entry(settings))
    current_entry[ENABLED_KEY] = bool(enabled)
    games[app_id] = current_entry

    _write_setting(PER_GAME_SETTINGS_KEY, games)
    return get_per_game_settings()


def set_button_prompt_fix_enabled(app_id, enabled):
    if app_id is None:
        return get_per_game_settings()

    games = get_per_game_settings()
    settings = _read_settings()
    app_id = str(app_id)
    entry = games.get(app_id)
    if entry is None and not enabled:
        return get_per_game_settings()

    current_entry = dict(entry or _default_per_game_settings_entry(settings))
    if enabled:
        current_entry[ENABLED_KEY] = True
    current_entry[BUTTON_PROMPT_FIX_ENABLED_KEY] = bool(enabled)
    games[app_id] = current_entry

    _write_setting(PER_GAME_SETTINGS_KEY, games)
    return get_per_game_settings()


def set_per_game_trackpad_mode(app_id, mode):
    if app_id is None:
        return get_per_game_settings()

    games = get_per_game_settings()
    app_id = str(app_id)
    entry = games.get(app_id)
    if not entry:
        return get_per_game_settings()

    current_entry = dict(entry)
    current_entry[PER_GAME_TRACKPAD_MODE_KEY] = trackpad_modes.normalize_trackpad_mode(
        mode
    )
    games[app_id] = current_entry

    _write_setting(PER_GAME_SETTINGS_KEY, games)
    return get_per_game_settings()


def set_per_game_trackpads_disabled(app_id, disabled):
    return set_per_game_trackpad_mode(
        app_id,
        trackpad_modes.TRACKPAD_MODE_DISABLED if disabled else trackpad_modes.TRACKPAD_MODE_DEFAULT,
    )


def set_per_game_rumble_enabled(app_id, enabled):
    if app_id is None:
        return get_per_game_settings()

    games = get_per_game_settings()
    app_id = str(app_id)
    entry = games.get(app_id)
    if not entry:
        return get_per_game_settings()

    current_entry = dict(entry)
    current_entry[PER_GAME_RUMBLE_ENABLED_KEY] = bool(enabled)
    games[app_id] = current_entry

    _write_setting(PER_GAME_SETTINGS_KEY, games)
    return get_per_game_settings()


def set_per_game_rumble_intensity(app_id, intensity):
    if app_id is None:
        return get_per_game_settings()

    games = get_per_game_settings()
    app_id = str(app_id)
    entry = games.get(app_id)
    if not entry:
        return get_per_game_settings()

    current_entry = dict(entry)
    current_entry[PER_GAME_RUMBLE_INTENSITY_KEY] = max(0, min(100, int(intensity)))
    games[app_id] = current_entry

    _write_setting(PER_GAME_SETTINGS_KEY, games)
    return get_per_game_settings()


def set_per_game_m1_remap_target(app_id, target):
    if app_id is None:
        return get_per_game_settings()

    games = get_per_game_settings()
    app_id = str(app_id)
    entry = games.get(app_id)
    if not entry:
        return get_per_game_settings()

    current_entry = dict(entry)
    current_entry[M1_REMAP_TARGET_KEY] = _normalize_per_game_remap_target(target)
    games[app_id] = current_entry

    _write_setting(PER_GAME_SETTINGS_KEY, games)
    return get_per_game_settings()


def set_per_game_m2_remap_target(app_id, target):
    if app_id is None:
        return get_per_game_settings()

    games = get_per_game_settings()
    app_id = str(app_id)
    entry = games.get(app_id)
    if not entry:
        return get_per_game_settings()

    current_entry = dict(entry)
    current_entry[M2_REMAP_TARGET_KEY] = _normalize_per_game_remap_target(target)
    games[app_id] = current_entry

    _write_setting(PER_GAME_SETTINGS_KEY, games)
    return get_per_game_settings()


def get_missing_glyph_fix_games():
    legacy_games = {}
    for app_id, entry in get_per_game_settings().items():
        if not entry.get(ENABLED_KEY) or not entry.get(BUTTON_PROMPT_FIX_ENABLED_KEY):
            continue

        legacy_games[app_id] = {
            LEGACY_DISABLE_TRACKPADS_KEY: trackpad_modes.is_trackpad_mode_disabled(
                entry.get(PER_GAME_TRACKPAD_MODE_KEY)
            )
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
