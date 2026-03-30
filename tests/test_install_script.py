import os
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

from .support import _write_executable


class InstallScriptTests(unittest.TestCase):
    def test_install_script_handles_null_assets_when_jq_is_present(self):
        with tempfile.TemporaryDirectory() as temp_home:
            temp_home_path = Path(temp_home)
            temp_home_path.joinpath("homebrew", "plugins").mkdir(parents=True)
            bin_dir = temp_home_path / "bin"
            bin_dir.mkdir()

            _write_executable(
                bin_dir / "curl",
                """#!/usr/bin/env bash
if [ "$1" = "-s" ]; then
  printf '%s' '{"tag_name":"v1.2.3","assets":null}'
  exit 0
fi

echo "unexpected curl invocation: $*" >&2
exit 2
""",
            )
            _write_executable(
                bin_dir / "sudo",
                """#!/usr/bin/env bash
exec "$@"
""",
            )
            _write_executable(
                bin_dir / "jq",
                """#!/usr/bin/env python3
import json
import sys

query = sys.argv[-1]
payload = json.load(sys.stdin)

if query == ".message":
    value = payload.get("message")
    print("null" if value is None else value)
    sys.exit(0)

if query == ".tag_name":
    value = payload.get("tag_name")
    print("null" if value is None else value)
    sys.exit(0)

def print_matching_urls(assets):
    for asset in assets:
        if asset.get("name", "").endswith(".tar.gz"):
            print(asset.get("browser_download_url", ""))

if query == '.assets[] | select(.name | endswith(".tar.gz")) | .browser_download_url':
    assets = payload.get("assets")
    if assets is None:
        sys.stderr.write("jq: error (at <stdin>:0): Cannot iterate over null (null)\\n")
        sys.exit(5)
    print_matching_urls(assets)
    sys.exit(0)

if query == '(.assets // [])[] | select(.name | endswith(".tar.gz")) | .browser_download_url':
    print_matching_urls(payload.get("assets") or [])
    sys.exit(0)

sys.stderr.write(f"unsupported jq query: {query}\\n")
sys.exit(2)
""",
            )

            install_script = Path(__file__).resolve().parents[1] / "install.sh"
            env = os.environ.copy()
            env["HOME"] = temp_home
            env["PATH"] = f"{bin_dir}:{env['PATH']}"

            result = subprocess.run(
                ["bash", str(install_script)],
                cwd=temp_home,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("Failed to get latest release tarball", result.stderr)
            self.assertNotIn("Cannot iterate over null", result.stderr)

    def test_install_script_follows_github_release_redirects(self):
        with tempfile.TemporaryDirectory() as temp_home:
            temp_home_path = Path(temp_home)
            plugins_dir = temp_home_path / "homebrew" / "plugins"
            plugins_dir.mkdir(parents=True)
            bin_dir = temp_home_path / "bin"
            bin_dir.mkdir()

            archive_root = temp_home_path / "archive-root"
            archive_plugin_dir = archive_root / "DeckyZone"
            archive_plugin_dir.mkdir(parents=True)
            archive_plugin_dir.joinpath("installed.txt").write_text(
                "redirect-safe install",
                encoding="utf-8",
            )

            archive_path = temp_home_path / "DeckyZone.tar.gz"
            with tarfile.open(archive_path, "w:gz") as archive:
                archive.add(archive_plugin_dir, arcname="DeckyZone")

            download_url = "https://downloads.example/DeckyZone.tar.gz"

            _write_executable(
                bin_dir / "curl",
                f"""#!/usr/bin/env bash
set -e

metadata_url="https://api.github.com/repos/DeckFilter/DeckyZone/releases/latest"
download_url="https://downloads.example/DeckyZone.tar.gz"

if [ "$#" -ge 2 ] && [ "$1" = "-s" ] && [ "$2" = "$metadata_url" ]; then
  printf '%s' '{{"message":"Moved Permanently","url":"https://api.github.com/repositories/1188026497/releases/latest"}}'
  exit 0
fi

if [ "$#" -ge 3 ] && [ "$1" = "-s" ] && [ "$2" = "-L" ] && [ "$3" = "$metadata_url" ]; then
  printf '%s' '{{"tag_name":"v1.2.3","assets":[{{"name":"DeckyZone.tar.gz","browser_download_url":"{download_url}"}}]}}'
  exit 0
fi

if [ "$#" -ge 4 ] && [ "$1" = "-L" ] && [ "$2" = "$download_url" ] && [ "$3" = "-o" ]; then
  cp "{archive_path}" "$4"
  exit 0
fi

echo "unexpected curl invocation: $*" >&2
exit 2
""",
            )
            _write_executable(
                bin_dir / "sudo",
                """#!/usr/bin/env bash
exec "$@"
""",
            )
            _write_executable(
                bin_dir / "rsync",
                """#!/usr/bin/env bash
set -e

src=""
dest=""
for arg in "$@"; do
  case "$arg" in
    -*)
      ;;
    *)
      if [ -z "$src" ]; then
        src="$arg"
      elif [ -z "$dest" ]; then
        dest="$arg"
      fi
      ;;
  esac
done

if [ -z "$src" ] || [ -z "$dest" ]; then
  echo "unexpected rsync invocation: $*" >&2
  exit 2
fi

mkdir -p "$dest"
cp -R "$src/." "$dest/"
""",
            )
            _write_executable(
                bin_dir / "systemctl",
                """#!/usr/bin/env bash
if [ "$1" = "restart" ] && [ "$2" = "plugin_loader.service" ]; then
  exit 0
fi

echo "unexpected systemctl invocation: $*" >&2
exit 2
""",
            )

            install_script = Path(__file__).resolve().parents[1] / "install.sh"
            env = os.environ.copy()
            env["HOME"] = temp_home
            env["PATH"] = f"{bin_dir}:{env['PATH']}"

            result = subprocess.run(
                ["bash", str(install_script)],
                cwd=temp_home,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            installed_file = plugins_dir / "DeckyZone" / "installed.txt"
            self.assertTrue(installed_file.exists())
            self.assertEqual(
                installed_file.read_text(encoding="utf-8"),
                "redirect-safe install",
            )
            self.assertIn("Downloading DeckyZone v1.2.3", result.stdout)

