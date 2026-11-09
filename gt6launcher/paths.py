"""Filesystem layout.

Linux  : ~/.local/share/gt6-launcher/        (XDG_DATA_HOME respected)
           config/rpcs3/   <- RPCS3's config dir (we point XDG_CONFIG_HOME at config/)
           cache/rpcs3/    <- RPCS3 cache (XDG_CACHE_HOME)
Windows portable build: <launcher folder>\\data\\
Windows source run: %LOCALAPPDATA%\\GT6Launcher\\
           rpcs3\\          <- managed RPCS3 executable; config follows RPCS3's portable/ precedence
"""
from __future__ import annotations

import os
import sys

IS_WINDOWS = sys.platform.startswith("win")
APP_NAME = "GT6 Launcher"
APP_ID = "gt6-launcher"
_RPCS3_BINARY: str | None = None


def set_rpcs3_binary(binary: str | None) -> None:
    """Set the RPCS3 executable whose config directory this launcher must share."""
    global _RPCS3_BINARY
    _RPCS3_BINARY = os.path.abspath(binary) if binary else None


def data_dir() -> str:
    override = os.environ.get("GT6L_HOME")
    if override:
        d = override
    elif IS_WINDOWS:
        if getattr(sys, "frozen", False):
            # The Windows zip is portable: keep launcher data, RPCS3 config/cache,
            # game data, downloads, and saves beside the executable. Do not write
            # user state under AppData, which makes the package easy to move/back up.
            d = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "data")
        else:
            # Keep source/developer runs out of the Python installation directory.
            d = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "GT6Launcher")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
        d = os.path.join(base, APP_ID)
    os.makedirs(d, exist_ok=True)
    return d


def _sub(*parts: str) -> str:
    d = os.path.join(data_dir(), *parts)
    os.makedirs(d, exist_ok=True)
    return d


def downloads_dir(title_id: str | None = None) -> str:
    return _sub("downloads", title_id) if title_id else _sub("downloads")


def mods_dir() -> str:
    return _sub("mods")


def backups_dir() -> str:
    return _sub("backups")


def cache_dir() -> str:
    return _sub("launcher-cache")


def logs_dir() -> str:
    return _sub("logs")


def settings_file() -> str:
    return os.path.join(data_dir(), "launcher.json")


# ---- RPCS3 locations ------------------------------------------------------------------

def rpcs3_xdg_config_home() -> str:
    return _sub("config")


def rpcs3_xdg_cache_home() -> str:
    return _sub("cache")


def rpcs3_windows_dir() -> str:
    """Directory for the launcher-managed RPCS3 executable on Windows."""
    return _sub("rpcs3")


def rpcs3_config_dir() -> str:
    """RPCS3's base dir, fs::get_config_dir(): dev_hdd0, dev_flash, patches/, GuiConfigs/ ..."""
    if IS_WINDOWS:
        # RPCS3 gives its executable-adjacent portable/ directory precedence over
        # RPCS3_CONFIG_DIR. Match that rule so every launcher writer and RPCS3
        # itself use the same files when a portable RPCS3 install is selected.
        if _RPCS3_BINARY:
            portable = os.path.join(os.path.dirname(_RPCS3_BINARY), "portable")
            if os.path.isdir(portable):
                return portable
        return rpcs3_windows_dir()
    return _sub("config", "rpcs3")


def rpcs3_settings_dir(cfg_dir: str | None = None) -> str:
    """Where RPCS3 reads its settings, fs::get_config_dir(true): config.yml, custom_configs/,
    input_configs/, patch_config.yml, LogitechG27.yml, rpcn.yml ...

    On Windows that is the "config" sub-folder of the base dir (Utilities/File.cpp); on Linux
    it is the base dir itself. Files written next to it are silently ignored by RPCS3."""
    base = cfg_dir or rpcs3_config_dir()
    if IS_WINDOWS:
        return os.path.join(base, "config")
    return base


def rpcs3_cache_dir() -> str:
    if IS_WINDOWS:
        return os.path.join(rpcs3_config_dir(), "cache")
    return _sub("cache", "rpcs3")


def rpcs3_log_file() -> str:
    if IS_WINDOWS:
        return os.path.join(rpcs3_config_dir(), "log", "RPCS3.log")
    return os.path.join(rpcs3_cache_dir(), "RPCS3.log")


def hdd_game_dir(title_id: str) -> str:
    return os.path.join(rpcs3_config_dir(), "dev_hdd0", "game", title_id)


def custom_config_file(title_id: str) -> str:
    return os.path.join(rpcs3_settings_dir(), "custom_configs", f"config_{title_id}.yml")


# ---- bundled resources -------------------------------------------------------------

def resource_dir() -> str:
    """Folder holding bundled data (works from source and from PyInstaller)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, "gt6launcher", "data")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def bundled_patches_dir() -> str:
    return os.path.join(resource_dir(), "patches")


def resource(name: str) -> str:
    return os.path.join(resource_dir(), name)
