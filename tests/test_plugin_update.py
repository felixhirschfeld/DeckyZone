import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

from .support import _CompletedProcess, plugin_update


class PluginUpdateHelperTests(unittest.TestCase):
    def test_release_api_url_uses_current_repository(self):
        self.assertEqual(
            plugin_update.RELEASE_API_URL,
            "https://api.github.com/repos/DeckFilter/DeckyZone/releases/latest",
        )

    def test_get_tarball_download_url_selects_deckyzone_tarball(self):
        release_metadata = {
            "assets": [
                {"name": "DeckyZone.zip", "browser_download_url": "https://example.com/DeckyZone.zip"},
                {"name": "OtherPlugin.tar.gz", "browser_download_url": "https://example.com/OtherPlugin.tar.gz"},
                {"name": "DeckyZone.tar.gz", "browser_download_url": "https://example.com/DeckyZone.tar.gz"},
            ]
        }

        self.assertEqual(
            plugin_update._get_tarball_download_url(release_metadata),
            "https://example.com/DeckyZone.tar.gz",
        )

    def test_get_tarball_download_url_raises_when_assets_is_null(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "Latest DeckyZone release tarball was not found.",
        ):
            plugin_update._get_tarball_download_url({"assets": None})

    def test_ota_update_replaces_existing_plugin_and_restarts_loader(self):
        with tempfile.TemporaryDirectory() as temp_home:
            plugin_root = Path(temp_home) / "homebrew" / "plugins"
            plugin_dir = plugin_root / "DeckyZone"
            plugin_dir.mkdir(parents=True)
            plugin_dir.joinpath("old.txt").write_text("old", encoding="utf-8")

            stage_root = Path(temp_home) / "stage"
            staged_plugin_dir = stage_root / "DeckyZone"
            staged_plugin_dir.mkdir(parents=True)
            staged_plugin_dir.joinpath("new.txt").write_text("new", encoding="utf-8")

            archive_path = Path(temp_home) / "DeckyZone.tar.gz"
            with tarfile.open(archive_path, "w:gz") as archive:
                archive.add(staged_plugin_dir, arcname="DeckyZone")

            original_home = plugin_update.decky.DECKY_USER_HOME
            original_download_latest_build = plugin_update._download_latest_build
            original_subprocess_run = plugin_update.subprocess.run
            commands = []

            def fake_run(command, **kwargs):
                commands.append((command, kwargs))
                return _CompletedProcess(returncode=0)

            plugin_update.decky.DECKY_USER_HOME = temp_home
            plugin_update._download_latest_build = lambda: str(archive_path)
            plugin_update.subprocess.run = fake_run
            try:
                result = plugin_update.ota_update()
            finally:
                plugin_update.decky.DECKY_USER_HOME = original_home
                plugin_update._download_latest_build = original_download_latest_build
                plugin_update.subprocess.run = original_subprocess_run

            self.assertTrue(result)
            self.assertFalse(plugin_dir.joinpath("old.txt").exists())
            self.assertEqual(plugin_dir.joinpath("new.txt").read_text(encoding="utf-8"), "new")
            self.assertEqual(commands[0][0], ["systemctl", "restart", "plugin_loader.service"])

    def test_ota_update_keeps_existing_plugin_when_unpack_fails(self):
        with tempfile.TemporaryDirectory() as temp_home:
            plugin_root = Path(temp_home) / "homebrew" / "plugins"
            plugin_dir = plugin_root / "DeckyZone"
            plugin_dir.mkdir(parents=True)
            plugin_dir.joinpath("old.txt").write_text("old", encoding="utf-8")

            archive_path = Path(temp_home) / "DeckyZone.tar.gz"
            archive_path.write_text("archive", encoding="utf-8")

            original_home = plugin_update.decky.DECKY_USER_HOME
            original_download_latest_build = plugin_update._download_latest_build
            original_unpack_archive = plugin_update.shutil.unpack_archive

            plugin_update.decky.DECKY_USER_HOME = temp_home
            plugin_update._download_latest_build = lambda: str(archive_path)

            def fake_unpack_archive(*args, **kwargs):
                raise RuntimeError("extract failed")

            plugin_update.shutil.unpack_archive = fake_unpack_archive
            try:
                with self.assertRaisesRegex(RuntimeError, "extract failed"):
                    plugin_update.ota_update()
            finally:
                plugin_update.decky.DECKY_USER_HOME = original_home
                plugin_update._download_latest_build = original_download_latest_build
                plugin_update.shutil.unpack_archive = original_unpack_archive

            self.assertTrue(plugin_dir.joinpath("old.txt").exists())
            self.assertEqual(plugin_dir.joinpath("old.txt").read_text(encoding="utf-8"), "old")

    def test_ota_update_restores_existing_plugin_when_staged_cutover_fails(self):
        with tempfile.TemporaryDirectory() as temp_home:
            plugin_root = Path(temp_home) / "homebrew" / "plugins"
            plugin_dir = plugin_root / "DeckyZone"
            plugin_dir.mkdir(parents=True)
            plugin_dir.joinpath("old.txt").write_text("old", encoding="utf-8")

            stage_root = Path(temp_home) / "stage"
            staged_plugin_dir = stage_root / "DeckyZone"
            staged_plugin_dir.mkdir(parents=True)
            staged_plugin_dir.joinpath("new.txt").write_text("new", encoding="utf-8")

            archive_path = Path(temp_home) / "DeckyZone.tar.gz"
            with tarfile.open(archive_path, "w:gz") as archive:
                archive.add(staged_plugin_dir, arcname="DeckyZone")

            original_home = plugin_update.decky.DECKY_USER_HOME
            original_download_latest_build = plugin_update._download_latest_build
            original_copytree = plugin_update.shutil.copytree
            original_subprocess_run = plugin_update.subprocess.run

            plugin_update.decky.DECKY_USER_HOME = temp_home
            plugin_update._download_latest_build = lambda: str(archive_path)

            def fake_copytree(*args, **kwargs):
                raise RuntimeError("cutover failed")

            plugin_update.shutil.copytree = fake_copytree
            plugin_update.subprocess.run = lambda *args, **kwargs: _CompletedProcess(returncode=0)
            try:
                with self.assertRaisesRegex(RuntimeError, "cutover failed"):
                    plugin_update.ota_update()
            finally:
                plugin_update.decky.DECKY_USER_HOME = original_home
                plugin_update._download_latest_build = original_download_latest_build
                plugin_update.shutil.copytree = original_copytree
                plugin_update.subprocess.run = original_subprocess_run

            self.assertEqual(plugin_dir.joinpath("old.txt").read_text(encoding="utf-8"), "old")
            self.assertFalse(plugin_dir.joinpath("new.txt").exists())

