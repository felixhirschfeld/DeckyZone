import os
import re
import stat
import subprocess
import tempfile
from pathlib import Path


STEAMOS_OS_RELEASE_PATHS = (Path("/etc/os-release"), Path("/usr/lib/os-release"))
GRUB_DEFAULT_PATH = Path("/etc/default/grub-steamos")
GRUB_CONFIG_PATH = Path("/boot/efi/EFI/steamos/grub.cfg")
GRUB_MKCONFIG_PATH = Path("/usr/bin/grub-mkconfig")
RUNTIME_CMDLINE_PATH = Path("/proc/cmdline")
ORIGINAL_GRUB_BACKUP_FILENAME = "grub-steamos-before-deckyzone"
AMD_IOMMU_OFF = "amd_iommu=off"

_CMDLINE_ASSIGNMENT_RE = re.compile(
    r'(?m)^(?P<prefix>[ \t]*GRUB_CMDLINE_LINUX=")'
    r'(?P<body>.*?)'
    r'(?P<closing>^[ \t]*"[ \t]*(?:#.*)?(?:\r?\n|$))',
    re.DOTALL,
)
_AMD_IOMMU_OFF_RE = re.compile(r"(?<!\S)amd_iommu=off(?!\S)")


class SleepFixConfigurationError(RuntimeError):
    pass


def parse_os_release(content):
    values = {}
    for raw_line in (content or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"'", '"'}
        ):
            value = value[1:-1]
        values[key] = value
    return values


def is_steamos_os_release(content):
    return parse_os_release(content).get("ID", "").lower() == "steamos"


def has_amd_iommu_off(content):
    return bool(_AMD_IOMMU_OFF_RE.search(content or ""))


def _get_cmdline_assignment(content):
    matches = list(_CMDLINE_ASSIGNMENT_RE.finditer(content or ""))
    if len(matches) != 1:
        raise SleepFixConfigurationError(
            "Expected exactly one GRUB_CMDLINE_LINUX assignment."
        )

    match = matches[0]
    body = match.group("body")
    if "\n" not in body:
        raise SleepFixConfigurationError(
            "GRUB_CMDLINE_LINUX is not in the expected multiline format."
        )

    last_line = next(
        (line for line in reversed(body.splitlines()) if line.strip()), None
    )
    if last_line is None or not last_line.rstrip().endswith("\\"):
        raise SleepFixConfigurationError(
            "GRUB_CMDLINE_LINUX does not end with an escaped continuation line."
        )

    return match


def _remove_amd_iommu_off(body):
    # Prefer removing a complete argument line so the known SteamOS layout stays
    # readable. The token replacement covers uncommon inline layouts as well.
    body = re.sub(
        r"(?m)^[ \t]*amd_iommu=off[ \t]*\\[ \t]*(?:\r?\n|$)",
        "",
        body,
    )
    return _AMD_IOMMU_OFF_RE.sub("", body)


def set_amd_iommu_disabled(grub_defaults, disabled):
    match = _get_cmdline_assignment(grub_defaults)
    body = match.group("body")
    off_count = len(_AMD_IOMMU_OFF_RE.findall(body))

    if disabled and off_count == 1:
        return grub_defaults, False
    if not disabled and off_count == 0:
        return grub_defaults, False

    updated_body = _remove_amd_iommu_off(body)
    if disabled:
        last_line = next(
            line for line in reversed(updated_body.splitlines()) if line.strip()
        )
        indentation = re.match(r"^[ \t]*", last_line).group(0)
        newline = "\r\n" if "\r\n" in updated_body else "\n"
        updated_body = f"{updated_body}{indentation}{AMD_IOMMU_OFF} \\{newline}"

    updated = (
        grub_defaults[: match.start("body")]
        + updated_body
        + grub_defaults[match.end("body") :]
    )
    return updated, updated != grub_defaults


class SteamOSSleepFix:
    def __init__(
        self,
        command_runner=subprocess.run,
        runtime_dir=None,
        env=None,
        os_release_paths=STEAMOS_OS_RELEASE_PATHS,
        grub_default_path=GRUB_DEFAULT_PATH,
        grub_config_path=GRUB_CONFIG_PATH,
        grub_mkconfig_path=GRUB_MKCONFIG_PATH,
        runtime_cmdline_path=RUNTIME_CMDLINE_PATH,
    ):
        self.command_runner = command_runner
        self.runtime_dir = Path(runtime_dir) if runtime_dir else None
        self.env = env
        self.os_release_paths = tuple(Path(path) for path in os_release_paths)
        self.grub_default_path = Path(grub_default_path)
        self.grub_config_path = Path(grub_config_path)
        self.grub_mkconfig_path = Path(grub_mkconfig_path)
        self.runtime_cmdline_path = Path(runtime_cmdline_path)

    def _read_os_release(self):
        for path in self.os_release_paths:
            try:
                return path.read_text(encoding="utf-8")
            except OSError:
                continue
        raise SleepFixConfigurationError("SteamOS os-release metadata is unavailable.")

    def _validate_paths(self):
        if not is_steamos_os_release(self._read_os_release()):
            raise SleepFixConfigurationError("Fix Sleep is only supported on SteamOS.")

        for path, label in (
            (self.grub_default_path, "SteamOS GRUB defaults"),
            (self.grub_config_path, "generated SteamOS GRUB configuration"),
        ):
            if path.is_symlink() or not path.is_file():
                raise SleepFixConfigurationError(f"Expected {label} is unavailable.")

        if not self.grub_mkconfig_path.is_file() or not os.access(
            self.grub_mkconfig_path, os.X_OK
        ):
            raise SleepFixConfigurationError("/usr/bin/grub-mkconfig is unavailable.")

    def _read_grub_defaults(self):
        self._validate_paths()
        try:
            content = self.grub_default_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise SleepFixConfigurationError(
                f"Failed to read SteamOS GRUB defaults: {error}"
            ) from error
        _get_cmdline_assignment(content)
        return content

    def get_state(self):
        state = {
            "available": False,
            "message": "",
            "configIommuDisabled": None,
            "runtimeIommuDisabled": None,
        }
        try:
            grub_defaults = self._read_grub_defaults()
            state["available"] = True
            state["configIommuDisabled"] = has_amd_iommu_off(grub_defaults)
        except SleepFixConfigurationError as error:
            state["message"] = str(error)
            return state

        try:
            cmdline = self.runtime_cmdline_path.read_text(encoding="utf-8")
            state["runtimeIommuDisabled"] = has_amd_iommu_off(cmdline)
        except (OSError, UnicodeDecodeError):
            state["message"] = "Current kernel command line is unavailable."
        return state

    def _get_backup_path(self):
        if self.runtime_dir is None:
            raise SleepFixConfigurationError("DeckyZone runtime directory is unavailable.")
        return self.runtime_dir / ORIGINAL_GRUB_BACKUP_FILENAME

    def _atomic_write(self, path, contents, mode=None, owner=None):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_path = tempfile.mkstemp(
            prefix=f".{path.name}.deckyzone-", dir=str(path.parent)
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(contents)
                handle.flush()
                os.fsync(handle.fileno())
            if mode is not None:
                os.chmod(temporary_path, stat.S_IMODE(mode))
            if owner is not None and hasattr(os, "chown"):
                os.chown(temporary_path, owner.st_uid, owner.st_gid)
            os.replace(temporary_path, path)
        except Exception:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass
            raise

    def _store_original_backup(self, original_contents):
        backup_path = self._get_backup_path()
        if backup_path.exists():
            if backup_path.is_file() and not backup_path.is_symlink():
                return
            raise SleepFixConfigurationError(
                "DeckyZone GRUB backup path is not a regular file."
            )
        self._atomic_write(backup_path, original_contents)

    def apply_iommu_disabled(self, disabled):
        original_defaults = self._read_grub_defaults()
        updated_defaults, changed = set_amd_iommu_disabled(original_defaults, disabled)
        if not changed:
            return False

        try:
            original_config = self.grub_config_path.read_bytes()
            default_stat = self.grub_default_path.stat()
            config_stat = self.grub_config_path.stat()
        except OSError as error:
            raise SleepFixConfigurationError(
                f"Failed to snapshot existing GRUB files: {error}"
            ) from error

        self._store_original_backup(original_defaults.encode("utf-8"))
        self._atomic_write(
            self.grub_default_path,
            updated_defaults.encode("utf-8"),
            mode=default_stat.st_mode,
            owner=default_stat,
        )
        try:
            self.command_runner(
                [str(self.grub_mkconfig_path), "-o", str(self.grub_config_path)],
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self.env,
            )
        except Exception as error:
            rollback_errors = []
            try:
                self._atomic_write(
                    self.grub_default_path,
                    original_defaults.encode("utf-8"),
                    mode=default_stat.st_mode,
                    owner=default_stat,
                )
            except Exception as rollback_error:
                rollback_errors.append(f"defaults: {rollback_error}")
            try:
                self._atomic_write(
                    self.grub_config_path,
                    original_config,
                    mode=config_stat.st_mode,
                    owner=config_stat,
                )
            except Exception as rollback_error:
                rollback_errors.append(f"generated config: {rollback_error}")

            detail = "; ".join(rollback_errors)
            if detail:
                raise SleepFixConfigurationError(
                    f"Failed to regenerate SteamOS GRUB configuration ({error}); rollback failed for {detail}."
                ) from error
            raise SleepFixConfigurationError(
                f"Failed to regenerate SteamOS GRUB configuration: {error}"
            ) from error

        return True
