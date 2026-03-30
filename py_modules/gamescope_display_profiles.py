from pathlib import Path


DEFAULT_SYSTEM_PROFILE_PATHS = (
    Path("/usr/share/gamescope/scripts/00-gamescope/displays/zotac.zone.oled.lua"),
    Path("/etc/gamescope/scripts/00-gamescope/displays/zotac.zone.oled.lua"),
)
ZOTAC_PROFILE_KEY = "gamescope.config.known_displays.zotac_amoled"
ZOTAC_PROFILE_IDENTIFIERS = ("DXQ7D0023", "ZDZ0501")
PROFILE_VARIANT_ABSENT = "absent"
PROFILE_VARIANT_BASE = "base"
PROFILE_VARIANT_GREEN = "green"
PROFILE_VARIANT_UNEXPECTED = "unexpected"
PROFILE_VARIANT_ERROR = "error"


class GamescopeDisplayProfiles:
    def __init__(self, user_home, plugin_dir, system_profile_paths=None):
        self.user_home = Path(user_home)
        self.plugin_dir = Path(plugin_dir)
        self.system_profile_paths = tuple(
            Path(path)
            for path in (system_profile_paths or DEFAULT_SYSTEM_PROFILE_PATHS)
        )

    @property
    def assets_dir(self):
        return self.plugin_dir / "assets" / "gamescope"

    @property
    def managed_scripts_dir(self):
        return self.user_home / ".config" / "gamescope" / "scripts"

    @property
    def managed_profile_path(self):
        return self.managed_scripts_dir / "zotac.zone.oled.lua"

    @property
    def legacy_managed_scripts_dir(self):
        return self.managed_scripts_dir / "90-deckyzone" / "displays"

    @property
    def legacy_managed_base_profile_path(self):
        return self.legacy_managed_scripts_dir / "10-zotac-zone-oled.lua"

    @property
    def legacy_managed_green_tint_profile_path(self):
        return self.legacy_managed_scripts_dir / "20-zotac-zone-green-tint.lua"

    def _read_file(self, path):
        return Path(path).read_text(encoding="utf-8")

    def _read_asset(self, filename):
        return self._read_file(self.assets_dir / filename)

    def _expected_base_profile_text(self):
        return self._read_asset("zotac.zone.oled.lua")

    def _expected_green_profile_text(self):
        return self._read_asset("zotac.zone.green-tint.lua")

    def _is_valid_zotac_profile(self, text):
        return ZOTAC_PROFILE_KEY in text and any(
            identifier in text for identifier in ZOTAC_PROFILE_IDENTIFIERS
        )

    def _resolve_builtin_profile_path(self):
        for path in self.system_profile_paths:
            if not path.is_file():
                continue

            try:
                text = self._read_file(path)
            except OSError:
                continue

            if self._is_valid_zotac_profile(text):
                return path

        return None

    def _write_managed_profile(self, path, contents):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")

    def _remove_managed_profile(self, path):
        if path.exists():
            path.unlink()

    def _remove_managed_profile_tolerant(self, path):
        try:
            self._remove_managed_profile(path)
        except OSError:
            pass

    def _remove_legacy_managed_profiles(self):
        self._remove_managed_profile(self.legacy_managed_green_tint_profile_path)
        self._remove_managed_profile(self.legacy_managed_base_profile_path)

    def _remove_legacy_managed_profiles_tolerant(self):
        self._remove_managed_profile_tolerant(self.legacy_managed_green_tint_profile_path)
        self._remove_managed_profile_tolerant(self.legacy_managed_base_profile_path)

    def _cleanup_empty_directories(self):
        cleanup_paths = (
            self.legacy_managed_scripts_dir,
            self.legacy_managed_scripts_dir.parent,
            self.managed_scripts_dir,
            self.managed_scripts_dir.parent,
        )
        for path in cleanup_paths:
            if not path.exists():
                continue
            try:
                path.rmdir()
            except OSError:
                pass

    def _migrate_legacy_managed_profiles(self):
        if self.managed_profile_path.is_file():
            self._remove_legacy_managed_profiles()
            self._cleanup_empty_directories()
            return

        variant = None
        if self.legacy_managed_green_tint_profile_path.is_file():
            variant = PROFILE_VARIANT_GREEN
        elif self.legacy_managed_base_profile_path.is_file():
            variant = PROFILE_VARIANT_BASE

        if variant == PROFILE_VARIANT_GREEN:
            self._write_managed_profile(
                self.managed_profile_path,
                self._expected_green_profile_text(),
            )
        elif variant == PROFILE_VARIANT_BASE:
            self._write_managed_profile(
                self.managed_profile_path,
                self._expected_base_profile_text(),
            )

        self._remove_legacy_managed_profiles()
        self._cleanup_empty_directories()

    def _fallback_state(self, verification_state=PROFILE_VARIANT_ERROR):
        return {
            "gamescopeZotacProfileBuiltIn": False,
            "gamescopeZotacProfileInstalled": verification_state in (
                PROFILE_VARIANT_BASE,
                PROFILE_VARIANT_GREEN,
                PROFILE_VARIANT_UNEXPECTED,
            ),
            "gamescopeGreenTintFixEnabled": verification_state == PROFILE_VARIANT_GREEN,
            "gamescopeZotacProfileTargetPath": str(self.managed_profile_path),
            "gamescopeZotacProfileVerificationState": verification_state,
        }

    def _get_managed_profile_verification_state(self):
        if not self.managed_profile_path.is_file():
            return PROFILE_VARIANT_ABSENT

        try:
            text = self._read_file(self.managed_profile_path)
        except OSError:
            return PROFILE_VARIANT_UNEXPECTED

        if text == self._expected_base_profile_text():
            return PROFILE_VARIANT_BASE
        if text == self._expected_green_profile_text():
            return PROFILE_VARIANT_GREEN
        return PROFILE_VARIANT_UNEXPECTED

    def is_builtin_profile_available(self):
        return self._resolve_builtin_profile_path() is not None

    def is_managed_base_profile_installed(self):
        self._migrate_legacy_managed_profiles()
        return self.managed_profile_path.is_file()

    def is_green_tint_fix_enabled(self):
        self._migrate_legacy_managed_profiles()
        return self._get_managed_profile_verification_state() == PROFILE_VARIANT_GREEN

    def is_base_profile_available(self):
        return self.is_builtin_profile_available() or self.is_managed_base_profile_installed()

    def get_state(self):
        try:
            self._migrate_legacy_managed_profiles()
            verification_state = self._get_managed_profile_verification_state()
            return {
                "gamescopeZotacProfileBuiltIn": self.is_builtin_profile_available(),
                "gamescopeZotacProfileInstalled": verification_state != PROFILE_VARIANT_ABSENT,
                "gamescopeGreenTintFixEnabled": verification_state == PROFILE_VARIANT_GREEN,
                "gamescopeZotacProfileTargetPath": str(self.managed_profile_path),
                "gamescopeZotacProfileVerificationState": verification_state,
            }
        except OSError:
            return self._fallback_state()

    def set_zotac_profile_enabled(self, enabled):
        self._migrate_legacy_managed_profiles()
        if enabled:
            self._write_managed_profile(
                self.managed_profile_path,
                self._expected_base_profile_text(),
            )
            return self.get_state()

        self._remove_managed_profile(self.managed_profile_path)
        self._cleanup_empty_directories()
        return self.get_state()

    def set_green_tint_fix_enabled(self, enabled):
        self._migrate_legacy_managed_profiles()
        if enabled:
            if not self.is_base_profile_available():
                return self.get_state()

            self._write_managed_profile(
                self.managed_profile_path,
                self._expected_green_profile_text(),
            )
            return self.get_state()

        if self.is_builtin_profile_available():
            self._remove_managed_profile(self.managed_profile_path)
        elif self.managed_profile_path.is_file():
            self._write_managed_profile(
                self.managed_profile_path,
                self._expected_base_profile_text(),
            )
        else:
            self._remove_managed_profile(self.managed_profile_path)

        self._cleanup_empty_directories()
        return self.get_state()

    def cleanup_managed_files(self):
        self._remove_managed_profile_tolerant(self.managed_profile_path)
        self._remove_legacy_managed_profiles_tolerant()
        self._cleanup_empty_directories()
        return self.get_state()
