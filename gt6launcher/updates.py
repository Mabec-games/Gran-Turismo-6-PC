"""Official game update chain: catalogue, resumable parallel download, SHA-1 check, install.

GT6 updates are deltas and must be installed strictly in order (RPCS3 refuses a
package whose prerequisite APP_VER is not installed). 1.01 was delisted and is
superseded by 1.02, which applies directly on top of the 1.00 disc.
"""
from __future__ import annotations

import json
import os
import shutil
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Optional

from . import paths
from .formats import read_pkg_header, verify_pkg
from .rpcs3 import RPCS3, installed_version

USER_AGENT = "GT6-Launcher/1.0"

# Versions that RPCS3 users commonly pick.
VERSION_PRESETS = {
    "01.22": "1.22 - latest. Needed for the Career/Spec II mods, LAN and online play. Needs Write/Read "
             "Color Buffers: lower FPS and some flicker (the patched RPCS3 build and AlexHaust fixes help).",
    "01.05": "1.05 - RPCS3 wiki's pick for best performance: higher FPS, no flicker (CPU blit), but weaker "
             "lighting / broken tunnel lighting. No mods, LAN or online. (1.00 crashes after races; 1.02 fixes it.)",
}
DEFAULT_TARGET = "01.22"


@dataclass
class UpdatePkg:
    title_id: str
    version: str
    url: str
    size: int

    @property
    def filename(self) -> str:
        return os.path.basename(self.url)

    @property
    def local_path(self) -> str:
        return os.path.join(paths.downloads_dir(self.title_id), self.filename)


def catalog() -> dict[str, list[UpdatePkg]]:
    with open(paths.resource("gt6_updates.json"), "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {tid: [UpdatePkg(tid, e["version"], e["url"], int(e["size"])) for e in entries]
            for tid, entries in raw.items()}


def chain(title_id: str, target: str = DEFAULT_TARGET, current: Optional[str] = None) -> list[UpdatePkg]:
    """Packages still needed to go from ``current`` (None = disc 01.00) to ``target``."""
    pkgs = catalog().get(title_id, [])
    cur = current or "01.00"
    return [p for p in pkgs if p.version != "01.01" and cur < p.version <= target]


def available_versions(title_id: str) -> list[str]:
    return [p.version for p in catalog().get(title_id, []) if p.version != "01.01"]


# --------------------------------------------------------------------------- download

ProgressFn = Callable[[str, int, int], None]  # (label, done_bytes, total_bytes)


class Cancelled(Exception):
    pass


class Downloader:
    def __init__(self, parallel: int = 4, progress: Optional[ProgressFn] = None,
                 log: Optional[Callable[[str], None]] = None):
        self.parallel = parallel
        self.progress = progress or (lambda *a: None)
        self.log = log or (lambda s: None)
        self._cancel = threading.Event()
        self._lock = threading.Lock()
        self._done: dict[str, int] = {}

    def cancel(self) -> None:
        self._cancel.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def _fetch(self, url: str, dest: str, size: int) -> None:
        part = dest + ".part"
        if os.path.exists(dest) and os.path.getsize(dest) == size:
            with self._lock:
                self._done[dest] = size
            return
        if os.path.exists(dest) and not os.path.exists(part) and (not size or os.path.getsize(dest) < size):
            os.replace(dest, part)  # an interrupted external download: resume it
        attempt = 0
        while True:
            if self._cancel.is_set():
                raise Cancelled()
            have = os.path.getsize(part) if os.path.exists(part) else 0
            if size and have > size:
                os.unlink(part)
                have = 0
            if size and have == size:
                break
            headers = {"User-Agent": USER_AGENT}
            if have:
                headers["Range"] = f"bytes={have}-"
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=60) as r:
                    if have and r.status != 206:  # server ignored range
                        have = 0
                        mode = "wb"
                    else:
                        mode = "ab" if have else "wb"
                    with open(part, mode) as f:
                        while True:
                            if self._cancel.is_set():
                                raise Cancelled()
                            chunk = r.read(1 << 20)
                            if not chunk:
                                break
                            f.write(chunk)
                            have += len(chunk)
                            with self._lock:
                                self._done[dest] = have
                if not size or have >= size:
                    break
            except Cancelled:
                raise
            except (urllib.error.URLError, OSError, TimeoutError) as e:
                attempt += 1
                if attempt > 8:
                    raise RuntimeError(f"download failed: {os.path.basename(dest)}: {e}") from e
                self.log(f"retry {attempt} {os.path.basename(dest)}: {e}")
                time.sleep(min(30, 2 * attempt))
        os.replace(part, dest)

    def download_all(self, pkgs: list[UpdatePkg]) -> None:
        total = sum(p.size for p in pkgs)
        def have(p: UpdatePkg) -> int:
            for f in (p.local_path, p.local_path + ".part"):
                if os.path.exists(f):
                    return min(os.path.getsize(f), p.size)
            return 0
        self._done = {p.local_path: have(p) for p in pkgs}
        stop = threading.Event()

        def reporter():
            while not stop.wait(0.5):
                with self._lock:
                    done = sum(self._done.values())
                self.progress("Downloading updates", done, total)

        t = threading.Thread(target=reporter, daemon=True)
        t.start()
        try:
            with ThreadPoolExecutor(max_workers=self.parallel) as ex:
                futs = {ex.submit(self._fetch, p.url, p.local_path, p.size): p for p in pkgs}
                for fut in as_completed(futs):
                    p = futs[fut]
                    fut.result()
                    self.log(f"downloaded {p.version} ({p.size // (1 << 20)} MiB)")
        except BaseException:
            self._cancel.set()
            raise
        finally:
            stop.set()
            t.join()
        self.progress("Downloading updates", total, total)


def free_space(path: str) -> int:
    return shutil.disk_usage(path).free


def bytes_h(n: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return str(n)


def install_chain(rpcs3: RPCS3, title_id: str, target: str = DEFAULT_TARGET, parallel: int = 4,
                  delete_after: bool = False, progress: Optional[ProgressFn] = None,
                  log: Optional[Callable[[str], None]] = None,
                  downloader: Optional[Downloader] = None) -> str:
    """Download + verify + install every missing update up to ``target``. Returns the
    final installed version. Safe to re-run (resumes downloads, skips installed)."""
    log = log or (lambda s: None)
    progress = progress or (lambda *a: None)
    current = installed_version(title_id)
    todo = chain(title_id, target, current)
    if not todo:
        log(f"{title_id}: already at {current or '01.00'}")
        return current or "01.00"
    need = sum(p.size for p in todo if not os.path.exists(p.local_path))
    if free_space(paths.data_dir()) < need * 2.1:
        raise RuntimeError(f"Not enough disk space: need about {bytes_h(need * 2.1)} free "
                           f"in {paths.data_dir()} (downloads + installed data).")
    log(f"{title_id}: {current or '01.00 (disc)'} -> {target}: {len(todo)} packages, {bytes_h(sum(p.size for p in todo))}")
    dl = downloader or Downloader(parallel=parallel, progress=progress, log=log)
    dl.download_all(todo)
    for i, p in enumerate(todo):
        if dl.cancelled:
            raise Cancelled()
        label = f"Verifying {p.version}"
        if not verify_pkg(p.local_path, lambda d, t: progress(label, d, t)):
            os.unlink(p.local_path)
            raise RuntimeError(f"{p.filename} is corrupt (SHA-1 mismatch) - deleted, run the installer again.")
        info = read_pkg_header(p.local_path)
        if info.title_id != title_id or info.app_version != p.version:
            raise RuntimeError(f"{p.filename}: unexpected package ({info.title_id} {info.app_version})")
        progress(f"Installing update {p.version} ({i + 1}/{len(todo)})", i, len(todo))
        log(f"installing {p.version} ...")
        if not rpcs3.install_pkg(p.local_path, title_id, p.version):
            raise RuntimeError(f"RPCS3 failed to install {p.version} (installed: {installed_version(title_id)}). "
                               f"See {paths.rpcs3_log_file()}")
        log(f"installed {p.version}")
        if delete_after:
            try:
                os.unlink(p.local_path)
            except OSError:
                pass
    progress("Updates installed", len(todo), len(todo))
    return installed_version(title_id) or target
