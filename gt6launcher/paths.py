"""Filesystem layout.

Linux  : ~/.local/share/gt6-launcher/        (XDG_DATA_HOME respected)
           config/rpcs3/   <- RPCS3's config dir (we point XDG_CONFIG_HOME at config/)
           cache/rpcs3/    <- RPCS3 cache (XDG_CACHE_HOME)
Windows: %LOCALAPPDATA%\\GT6Launcher\\
           rpcs3\\          <- portable RPCS3 install; RPCS3_CONFIG_DIR points here
"""
from __future__ import annotations

import os
import sys

IS_WINDOWS = sys.platform.startswith("win")
APP_NAME = "GT6 Launcher"
APP_ID = "gt6-launcher"


def data_dir() -> str:
    override = os.environ.get("GT6L_HOME")
    if override:
        d = override
    elif IS_WINDOWS:
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
    return _sub("rpcs3")


def rpcs3_config_dir() -> str:
    """The directory RPCS3 calls its config dir (contains config.yml, dev_hdd0 ...)."""
    if IS_WINDOWS:
        return rpcs3_windows_dir()
    return _sub("config", "rpcs3")


def rpcs3_cache_dir() -> str:
    if IS_WINDOWS:
        return os.path.join(rpcs3_windows_dir(), "cache")
    return _sub("cache", "rpcs3")


def rpcs3_log_file() -> str:
    if IS_WINDOWS:
        return os.path.join(rpcs3_windows_dir(), "log", "RPCS3.log")
    return os.path.join(rpcs3_cache_dir(), "RPCS3.log")


def hdd_game_dir(title_id: str) -> str:
    return os.path.join(rpcs3_config_dir(), "dev_hdd0", "game", title_id)


def custom_config_file(title_id: str) -> str:
    return os.path.join(rpcs3_config_dir(), "custom_configs", f"config_{title_id}.yml")


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
