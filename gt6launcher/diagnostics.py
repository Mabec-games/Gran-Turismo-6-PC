"""Crash reports and user-saved launcher/emulator logs."""
from __future__ import annotations

import os
import platform
import re
import shlex
import subprocess
import time
import zipfile
from datetime import datetime
from typing import Optional

from . import paths

_MAX_RPCS3_LOG_BYTES = 4 * 1024 * 1024


def _timestamp() -> str:
    return datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")


def _command_line(args) -> str:
    if isinstance(args, str):
        return args
    if not args:
        return "(unavailable)"
    return subprocess.list2cmdline(args) if paths.IS_WINDOWS else shlex.join(args)


def _copy_rpcs3_log(destination: str, source: Optional[str] = None) -> bool:
    source = source or paths.rpcs3_log_file()
    try:
        with open(source, "rb") as src:
            src.seek(0, os.SEEK_END)
            size = src.tell()
            start = max(0, size - _MAX_RPCS3_LOG_BYTES)
            src.seek(start)
            data = src.read()
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        temporary = destination + ".tmp"
        with open(temporary, "wb") as dst:
            if start:
                dst.write((f"[Launcher included the last {_MAX_RPCS3_LOG_BYTES} bytes of the RPCS3 log; "
                           f"{size - _MAX_RPCS3_LOG_BYTES} earlier bytes omitted.]\n\n").encode("utf-8"))
            dst.write(data)
        os.replace(temporary, destination)
        return True
    except OSError:
        return False


def _last_session_dir() -> str:
    return os.path.join(paths.logs_dir(), "last-session")


def direct_rpcs3_launch_marker() -> Optional[str]:
    """Return the latest direct-start marker emitted by the GT6-patched RPCS3 build."""
    source = paths.rpcs3_log_file()
    try:
        with open(source, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 1024 * 1024))
            lines = f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return None
    prefix = "GT6 launch origin: RPCS3 started directly; GT6 Launcher was bypassed"
    return next((line.strip() for line in reversed(lines) if prefix in line), None)


def record_direct_rpcs3_launch(marker: str) -> str:
    """Persist the external-launch finding for inclusion with user-saved logs."""
    path = os.path.join(paths.logs_dir(), "rpcs3-launch-origin.log")
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(f"{datetime.now().astimezone().isoformat(timespec='seconds')} {marker}\n")
    return path


def preserve_last_session_rpcs3() -> bool:
    """Snapshot RPCS3's current log before its next launch truncates that file."""
    folder = _last_session_dir()
    return _copy_rpcs3_log(os.path.join(folder, "RPCS3.log"))


def remember_last_session(launcher_text: str) -> bool:
    """Keep a stable copy of the completed session, independent of RPCS3's live log."""
    folder = _last_session_dir()
    os.makedirs(folder, exist_ok=True)
    launcher_tmp = os.path.join(folder, "launcher.log.tmp")
    launcher_path = os.path.join(folder, "launcher.log")
    try:
        with open(launcher_tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(launcher_text.rstrip() + "\n")
        os.replace(launcher_tmp, launcher_path)
    except OSError:
        return False
    rpcs3_snapshot = os.path.join(folder, "RPCS3.log")
    copied = _copy_rpcs3_log(rpcs3_snapshot)
    if not copied:
        try:
            os.unlink(rpcs3_snapshot)
        except OSError:
            pass
    return copied


def _cpu_model() -> str:
    if paths.IS_WINDOWS:
        value = os.environ.get("PROCESSOR_IDENTIFIER", "").strip()
        if value:
            return value
    else:
        try:
            with open("/proc/cpuinfo", "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if line.lower().startswith(("model name", "hardware")) and ":" in line:
                        return line.split(":", 1)[1].strip()
        except OSError:
            pass
    return platform.processor().strip() or "unknown"


def _ram_total() -> str:
    try:
        if paths.IS_WINDOWS:
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("memory_load", ctypes.c_ulong),
                            ("total_phys", ctypes.c_ulonglong), ("avail_phys", ctypes.c_ulonglong),
                            ("total_page_file", ctypes.c_ulonglong), ("avail_page_file", ctypes.c_ulonglong),
                            ("total_virtual", ctypes.c_ulonglong), ("avail_virtual", ctypes.c_ulonglong),
                            ("avail_extended_virtual", ctypes.c_ulonglong)]

            status = MemoryStatus()
            status.length = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return f"{status.total_phys / (1024 ** 3):.1f} GiB"
        else:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            return f"{pages * page_size / (1024 ** 3):.1f} GiB"
    except (AttributeError, OSError, ValueError):
        pass
    return "unknown"


def _rpcs3_hardware() -> dict[str, str]:
    """Prefer RPCS3's detected CPU/GPU details, with host queries as fallback."""
    found = {"CPU": "", "GPU": "", "RAM": ""}
    try:
        with open(paths.rpcs3_log_file(), "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i >= 500:
                    break
                if not found["GPU"]:
                    match = re.search(r"Found Vulkan-compatible GPU:\s*'([^']+)'", line)
                    if match:
                        found["GPU"] = match.group(1).strip()
                if not found["CPU"] or not found["RAM"]:
                    match = re.search(r"^SYS:\s*(.*?)\s*\|\s*\d+\s+Threads\s*\|\s*([\d.]+\s+\w+\s+RAM)", line)
                    if match:
                        found["CPU"] = found["CPU"] or match.group(1).strip()
                        found["RAM"] = found["RAM"] or match.group(2).strip()
    except OSError:
        pass
    found["CPU"] = found["CPU"] or _cpu_model()
    found["RAM"] = found["RAM"] or _ram_total()
    found["GPU"] = found["GPU"] or "not reported by RPCS3"
    return found


def _read_rpcs3_log_bytes(source: str) -> Optional[bytes]:
    try:
        with open(source, "rb") as src:
            src.seek(0, os.SEEK_END)
            size = src.tell()
            start = max(0, size - _MAX_RPCS3_LOG_BYTES)
            src.seek(start)
            data = src.read()
        if start:
            header = (f"[Launcher included the last {_MAX_RPCS3_LOG_BYTES} bytes of the RPCS3 log; "
                      f"{size - _MAX_RPCS3_LOG_BYTES} earlier bytes omitted.]\n\n").encode("utf-8")
            return header + data
        return data
    except OSError:
        return None


def save_logs_archive(dest_zip: str, launcher_text: str) -> tuple[str, bool]:
    """Bundle the current session's launcher log and RPCS3 log into a user-chosen .zip file."""
    if not dest_zip.lower().endswith(".zip"):
        dest_zip += ".zip"
    parent = os.path.dirname(os.path.abspath(dest_zip))
    if parent:
        os.makedirs(parent, exist_ok=True)

    last_dir = _last_session_dir()
    if launcher_text.strip():
        launcher_bytes = (launcher_text.rstrip() + "\n").encode("utf-8")
    else:
        saved_launcher = os.path.join(last_dir, "launcher.log")
        try:
            with open(saved_launcher, "rb") as f:
                launcher_bytes = f.read()
        except OSError:
            launcher_bytes = b""

    live_rpcs3 = paths.rpcs3_log_file()
    saved_rpcs3 = os.path.join(last_dir, "RPCS3.log")
    rpcs3_bytes = None
    if os.path.isfile(live_rpcs3) and os.path.getsize(live_rpcs3) > 0:
        rpcs3_bytes = _read_rpcs3_log_bytes(live_rpcs3)
    elif os.path.isfile(saved_rpcs3):
        rpcs3_bytes = _read_rpcs3_log_bytes(saved_rpcs3)

    tmp = dest_zip + ".tmp"
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("launcher.log", launcher_bytes)
        if rpcs3_bytes is not None:
            zf.writestr("RPCS3.log", rpcs3_bytes)
        origin_log = os.path.join(paths.logs_dir(), "rpcs3-launch-origin.log")
        if os.path.isfile(origin_log):
            try:
                zf.write(origin_log, "rpcs3-launch-origin.log")
            except OSError:
                pass
    os.replace(tmp, dest_zip)
    return dest_zip, rpcs3_bytes is not None


def save_logs(launcher_text: str, active_session: bool = False) -> tuple[str, Optional[str]]:
    """Save a copy of the current session's launcher log and RPCS3 log for bug reports."""
    root = paths.logs_dir()
    os.makedirs(root, exist_ok=True)
    stamp = _timestamp()
    folder = os.path.join(root, f"session-{stamp}")
    suffix = 1
    while True:
        try:
            os.mkdir(folder)
            break
        except FileExistsError:
            folder = os.path.join(root, f"session-{stamp}-{suffix}")
            suffix += 1

    last_dir = _last_session_dir()
    launcher_path = os.path.join(folder, "launcher.log")
    if launcher_text.strip():
        with open(launcher_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(launcher_text.rstrip() + "\n")
    else:
        saved_launcher = os.path.join(last_dir, "launcher.log")
        if os.path.isfile(saved_launcher):
            with open(saved_launcher, "rb") as src, open(launcher_path, "wb") as dst:
                dst.write(src.read())
        else:
            with open(launcher_path, "w", encoding="utf-8", newline="\n") as f:
                f.write("")

    origin_log = os.path.join(root, "rpcs3-launch-origin.log")
    if os.path.isfile(origin_log):
        try:
            with open(origin_log, "rb") as src, open(os.path.join(folder, "rpcs3-launch-origin.log"), "wb") as dst:
                dst.write(src.read())
        except OSError:
            pass

    live_rpcs3 = paths.rpcs3_log_file()
    saved_rpcs3 = os.path.join(last_dir, "RPCS3.log")
    rpcs3_path = os.path.join(folder, "RPCS3.log")
    if os.path.isfile(live_rpcs3) and os.path.getsize(live_rpcs3) > 0:
        copied = _copy_rpcs3_log(rpcs3_path, live_rpcs3)
    elif os.path.isfile(saved_rpcs3):
        copied = _copy_rpcs3_log(rpcs3_path, saved_rpcs3)
    else:
        copied = False
    return launcher_path, rpcs3_path if copied else None


def collect_crash(entry, proc: subprocess.Popen, started: float, rpcs3_path: str) -> str:
    """Write a small, privacy-conscious report plus an RPCS3 log snapshot."""
    code = proc.returncode
    stamp = _timestamp()
    folder = os.path.join(paths.logs_dir(), "crashes", f"{stamp}-{entry.title_id}-{proc.pid}")
    os.makedirs(folder, exist_ok=True)
    report_path = os.path.join(folder, "report.txt")
    log_path = os.path.join(folder, "RPCS3.log")
    has_log = _copy_rpcs3_log(log_path)
    elapsed = max(0.0, time.time() - started)
    hardware = _rpcs3_hardware()
    from . import __version__

    if code is None:
        status = "unavailable"
    elif code < 0:
        status = f"{code} (terminated by signal {-code})"
    else:
        status = f"{code} (0x{code:08X})"
    details = [
        "GT6 Launcher crash/abnormal-exit report",
        f"Time: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"Launcher version: {__version__}",
        f"Game: {entry.title_id} version {entry.installed or '01.00 (disc)'}",
        f"CPU: {hardware['CPU']}",
        f"GPU: {hardware['GPU']}",
        f"RAM: {hardware['RAM']}",
        f"RPCS3 executable: {rpcs3_path}",
        f"Exit status: {status}",
        f"Run duration: {elapsed:.1f} seconds",
        f"Process ID: {proc.pid}",
        f"Command: {_command_line(proc.args)}",
        f"Operating system: {platform.platform()}",
        f"Architecture: {platform.machine() or 'unknown'}",
        f"Python: {platform.python_version()}",
        f"Launcher data directory: {paths.data_dir()}",
        f"RPCS3 log snapshot: {log_path if has_log else 'not available'}",
        "",
        "The launcher did not capture RPCS3 stdout/stderr. The attached RPCS3 log is the emulator's own log.",
    ]
    with open(report_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(details) + "\n")
    return report_path
