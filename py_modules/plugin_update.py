import json
import os
import shutil
import ssl
import stat
import subprocess
import tempfile
import urllib.request

import decky


PACKAGE_NAME = "DeckyZone"
RELEASE_API_URL = "https://api.github.com/repos/DeckFilter/DeckyZone/releases/latest"
TARBALL_ASSET_NAME = f"{PACKAGE_NAME}.tar.gz"


def get_env():
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = ""
    return env


def _fetch_latest_release():
    ssl_context = ssl.SSLContext()

    with urllib.request.urlopen(RELEASE_API_URL, context=ssl_context) as response:
        return json.load(response)


def _get_tarball_download_url(release_metadata):
    for asset in release_metadata.get("assets") or []:
        if asset.get("name") == TARBALL_ASSET_NAME:
            return asset.get("browser_download_url")

    raise RuntimeError("Latest DeckyZone release tarball was not found.")


def get_latest_version():
    release_metadata = _fetch_latest_release()
    tag_name = release_metadata.get("tag_name") or ""

    if not tag_name:
        raise RuntimeError("Latest DeckyZone release tag was not found.")

    return tag_name[1:] if tag_name.startswith("v") else tag_name


def _download_latest_build():
    release_metadata = _fetch_latest_release()
    download_url = _get_tarball_download_url(release_metadata)
    file_descriptor, archive_path = tempfile.mkstemp(
        prefix=f"{PACKAGE_NAME}-", suffix=".tar.gz"
    )
    os.close(file_descriptor)

    ssl_context = ssl.SSLContext()
    with urllib.request.urlopen(download_url, context=ssl_context) as response, open(
        archive_path, "wb"
    ) as output_file:
        output_file.write(response.read())

    return archive_path


def _recursive_chmod(path, perms):
    if not os.path.exists(path):
        return

    for dirpath, _, filenames in os.walk(path):
        current_dir_perms = os.stat(dirpath).st_mode
        os.chmod(dirpath, current_dir_perms | perms)
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            current_file_perms = os.stat(file_path).st_mode
            os.chmod(file_path, current_file_perms | perms)


def ota_update():
    archive_path = _download_latest_build()
    plugins_dir = f"{decky.DECKY_USER_HOME}/homebrew/plugins"
    plugin_dir = f"{plugins_dir}/{PACKAGE_NAME}"
    backup_dir = f"{plugins_dir}/.{PACKAGE_NAME}.backup"

    try:
        os.makedirs(plugins_dir, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f"{PACKAGE_NAME}-staging-") as staging_dir:
            shutil.unpack_archive(archive_path, staging_dir)
            staged_plugin_dir = os.path.join(staging_dir, PACKAGE_NAME)

            if not os.path.isdir(staged_plugin_dir):
                raise RuntimeError(
                    "Downloaded DeckyZone release did not contain a top-level plugin directory."
                )

            if os.path.exists(backup_dir):
                _recursive_chmod(backup_dir, stat.S_IWUSR)
                shutil.rmtree(backup_dir)

            if os.path.exists(plugin_dir):
                _recursive_chmod(plugin_dir, stat.S_IWUSR)
                os.replace(plugin_dir, backup_dir)

            try:
                shutil.copytree(staged_plugin_dir, plugin_dir)
            except Exception:
                if os.path.exists(plugin_dir):
                    _recursive_chmod(plugin_dir, stat.S_IWUSR)
                    shutil.rmtree(plugin_dir)
                if os.path.exists(backup_dir):
                    os.replace(backup_dir, plugin_dir)
                raise

            if os.path.exists(backup_dir):
                _recursive_chmod(backup_dir, stat.S_IWUSR)
                shutil.rmtree(backup_dir)

        subprocess.run(
            ["systemctl", "restart", "plugin_loader.service"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=get_env(),
        )
        return True
    finally:
        if os.path.exists(archive_path):
            os.remove(archive_path)
