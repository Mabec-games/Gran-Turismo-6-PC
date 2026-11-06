"""Game patch catalogue + RPCS3 patch_config.yml writer.

Patch sources, all copied into RPCS3's ``patches/`` folder:

* ``patch.yml``            - RPCS3's official patch database (Develop Settings etc.)
* ``imported_patch.yml``   - AlexHaust's GT5/GT6 graphics/camera patches
* ``<TITLE>_patch.yml``    - patches maintained by this launcher (LAN mode fixes)

RPCS3 resolves duplicate (hash, name) pairs by Patch Version, so we only need
to tell it *which* patches are enabled via ``patch_config.yml``.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import urllib.request
from dataclasses import dataclass, field, asdict
from typing import Any, Iterable, Optional

from . import paths
from .yamlio import atomic_write, dump_yaml, load_patch_yaml

GAME_NAME = "Gran Turismo 6"

PATCH_SOURCES = {
    # file name in RPCS3/patches : update URL (None = shipped with launcher only)
    "patch.yml": "https://rpcs3.net/compatibility?patch&api=v1&v=1.2",
    "imported_patch.yml": "https://raw.githubusercontent.com/AlexHaust/granturismo-RPCS3-patches/main/imported_patch.yml",
}


@dataclass
class ConfigValue:
    name: str
    type: str
    default: float
    min: Optional[float] = None
    max: Optional[float] = None
    allowed: dict[str, float] = field(default_factory=dict)


@dataclass
class PatchInfo:
    hash: str
    name: str
    serial: str
    version: str
    author: str = ""
    notes: str = ""
    group: str = ""
    patch_version: str = ""
    source: str = ""
    config: list[ConfigValue] = field(default_factory=list)

    @property
    def key(self) -> str:
        return self.name


def _f(v: Any) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _extract(data: dict[str, Any], source: str) -> list[PatchInfo]:
    out: list[PatchInfo] = []
    for top, body in data.items():
        if not str(top).startswith("PPU-") or not isinstance(body, dict):
            continue
        for name, p in body.items():
            if not isinstance(p, dict):
                continue
            games = p.get("Games") or {}
            serials = games.get(GAME_NAME)
            if not isinstance(serials, dict):
                continue
            cfg: list[ConfigValue] = []
            for cname, c in (p.get("Configurable Values") or {}).items():
                if not isinstance(c, dict):
                    continue
                allowed = {str(k): _f(v) for k, v in (c.get("Allowed Values") or {}).items()}
                cfg.append(ConfigValue(str(cname), str(c.get("Type", "")), _f(c.get("Value")) or 0.0,
                                       _f(c.get("Min")), _f(c.get("Max")), allowed))
            for serial, versions in serials.items():
                if isinstance(versions, str):
                    versions = [versions]
                for ver in versions or []:
                    out.append(PatchInfo(hash=str(top), name=str(name), serial=str(serial), version=str(ver),
                                         author=str(p.get("Author") or ""),
                                         notes=" ".join(str(p.get("Notes") or "").split()),
                                         group=str(p.get("Group") or ""),
                                         patch_version=str(p.get("Patch Version") or ""),
                                         source=source, config=cfg))
    return out


def _cache_path() -> str:
    return os.path.join(paths.cache_dir(), "patch_index.json")


def _sources_dir() -> str:
    """Where the launcher keeps the current copies of patch files."""
    d = os.path.join(paths.data_dir(), "patches")
    os.makedirs(d, exist_ok=True)
    bundled = paths.bundled_patches_dir()
    # Third-party patch databases are not redistributed with the launcher (no license to do so);
    # they are downloaded from their official sources - see ensure_sources().
    for fn in (os.listdir(bundled) if os.path.isdir(bundled) else []):
        dst = os.path.join(d, fn)
        if not os.path.exists(dst):
            shutil.copy2(os.path.join(paths.bundled_patches_dir(), fn), dst)
    return d


def _fingerprint(files: Iterable[str]) -> str:
    h = hashlib.sha1()
    for f in sorted(files):
        st = os.stat(f)
        h.update(f"{os.path.basename(f)}:{st.st_size}:{int(st.st_mtime)}".encode())
    return h.hexdigest()


def patch_files() -> list[str]:
    d = _sources_dir()
    return [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.endswith(".yml")]


def load_index(force: bool = False) -> list[PatchInfo]:
    """Return every GT6 patch from every source (cached as JSON - parsing the
    official database in pure python takes several seconds)."""
    files = patch_files()
    fp = _fingerprint(files)
    cp = _cache_path()
    if not force and os.path.exists(cp):
        try:
            with open(cp, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if cached.get("fp") == fp:
                return [PatchInfo(**{**p, "config": [ConfigValue(**c) for c in p["config"]]})
                        for p in cached["patches"]]
        except (OSError, ValueError, KeyError, TypeError):
            pass
    allp: list[PatchInfo] = []
    for f in files:
        try:
            allp.extend(_extract(load_patch_yaml(f), os.path.basename(f)))
        except Exception as e:  # a broken download must not brick the launcher
            print(f"[patches] failed to parse {f}: {e}")
    os.makedirs(os.path.dirname(cp), exist_ok=True)
    atomic_write(cp, json.dumps({"fp": fp, "patches": [asdict(p) for p in allp]}))
    return allp


def extract_from_text(text: str, source: str) -> list[PatchInfo]:
    """Index entries from an in-memory patch file (the launcher's own <TITLE>_patch.yml)."""
    import yaml
    from .yamlio import StrLoader
    return _extract(yaml.load(text, Loader=StrLoader) or {}, source)


def patches_for(serial: str, version: str, index: Optional[list[PatchInfo]] = None) -> list[PatchInfo]:
    """Patches applicable to serial/version, de-duplicated by name (first source wins
    in the order: launcher LAN file, AlexHaust, official)."""
    index = index if index is not None else load_index()
    prio = {"imported_patch.yml": 1, "patch.yml": 2}
    found: dict[str, PatchInfo] = {}
    for p in sorted(index, key=lambda p: prio.get(p.source, 0)):
        if p.serial != serial or p.version not in (version, "All"):
            continue
        found.setdefault(p.name, p)
    return list(found.values())


def missing_sources() -> list[str]:
    d = _sources_dir()
    return [fn for fn in PATCH_SOURCES if not os.path.exists(os.path.join(d, fn))]


def ensure_sources() -> list[str]:
    """Download patch databases that are not present yet (first start). Never raises."""
    if not missing_sources():
        return []
    try:
        return update_sources()
    except Exception as e:  # offline etc. - the game still runs, just without those patches
        return [f"patch download failed: {e}"]


def update_sources(progress=None) -> list[str]:
    """Download the latest patch files. Returns a list of human readable results."""
    results = []
    d = _sources_dir()
    for fn, url in PATCH_SOURCES.items():
        if not url:
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GT6-Launcher"})
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
            if fn == "patch.yml":
                payload = json.loads(body)
                if payload.get("return_code") != 0:
                    raise RuntimeError(f"api return_code {payload.get('return_code')}")
                body = payload["patch"].encode("utf-8")
            text = body.decode("utf-8")
            if "Version:" not in text[:200]:
                raise RuntimeError("unexpected content")
            atomic_write(os.path.join(d, fn), text)
            results.append(f"{fn}: updated ({len(body) // 1024} KiB)")
        except Exception as e:
            results.append(f"{fn}: failed ({e})")
    load_index(force=True)
    return results


def install_patch_files(rpcs3_cfg_dir: str, extra_title_files: dict[str, str]) -> None:
    """Copy patch databases into RPCS3's patches folder."""
    dst = os.path.join(rpcs3_cfg_dir, "patches")
    os.makedirs(dst, exist_ok=True)
    for f in patch_files():
        shutil.copy2(f, os.path.join(dst, os.path.basename(f)))
    for fn, text in extra_title_files.items():
        atomic_write(os.path.join(dst, fn), text)


def write_patch_config(rpcs3_cfg_dir: str, selections: list[tuple[PatchInfo, dict[str, float]]],
                       keep_foreign: bool = True) -> None:
    """Write patch_config.yml. ``selections`` = [(patch, {config name: value})].

    Entries for other games are preserved; GT6 entries are fully owned by the launcher."""
    path = os.path.join(rpcs3_cfg_dir, "patch_config.yml")
    existing: dict[str, Any] = {}
    if keep_foreign and os.path.exists(path):
        try:
            existing = load_patch_yaml(path) or {}
        except Exception:
            existing = {}
    # drop all GT6 entries (we rewrite them)
    cleaned: dict[str, Any] = {}
    for h, names in existing.items():
        if not isinstance(names, dict):
            continue
        keep = {}
        for n, games in names.items():
            if isinstance(games, dict):
                games = {g: v for g, v in games.items() if g != GAME_NAME}
                if games:
                    keep[n] = games
        if keep:
            cleaned[h] = keep
    for p, values in selections:
        entry: dict[str, Any] = {"Enabled": True}
        if values:
            entry["Configurable Values"] = {k: float(v) for k, v in values.items()}
        cleaned.setdefault(p.hash, {}).setdefault(p.name, {}).setdefault(GAME_NAME, {}) \
            .setdefault(p.serial, {})[p.version] = entry
    atomic_write(path, dump_yaml(cleaned))


