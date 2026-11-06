"""Small, dependency-free readers for the PS3 file formats the launcher touches.

* PARAM.SFO  - title id / version metadata
* ISO 9660   - locate PS3_GAME/PARAM.SFO inside a disc image without mounting it
* PKG        - header fields + footer SHA-1 integrity check for update packages
"""
from __future__ import annotations

import hashlib
import os
import struct
from dataclasses import dataclass
from typing import BinaryIO, Callable, Optional

# --------------------------------------------------------------------------- SFO


def parse_sfo(data: bytes) -> dict[str, object]:
    """Parse a PARAM.SFO blob into a {key: value} dict."""
    if len(data) < 20 or data[:4] != b"\0PSF":
        raise ValueError("not a PARAM.SFO")
    _magic, _ver, key_tbl, data_tbl, count = struct.unpack_from("<4sIIII", data, 0)
    out: dict[str, object] = {}
    for i in range(count):
        key_off, fmt, length, _max, data_off = struct.unpack_from("<HHIII", data, 20 + i * 16)
        k_start = key_tbl + key_off
        key = data[k_start:data.index(b"\0", k_start)].decode("ascii", "replace")
        raw = data[data_tbl + data_off:data_tbl + data_off + length]
        if fmt == 0x0404:
            out[key] = struct.unpack("<I", raw[:4])[0]
        else:
            out[key] = raw.split(b"\0", 1)[0].decode("utf-8", "replace")
    return out


def read_sfo(path: str | os.PathLike) -> dict[str, object]:
    with open(path, "rb") as f:
        return parse_sfo(f.read())


# --------------------------------------------------------------------------- ISO 9660

SECTOR = 2048


@dataclass
class IsoEntry:
    name: str
    lba: int
    size: int
    is_dir: bool


def _iso_read_dir(f: BinaryIO, lba: int, size: int) -> list[IsoEntry]:
    f.seek(lba * SECTOR)
    buf = f.read(size)
    entries: list[IsoEntry] = []
    pos = 0
    while pos < len(buf):
        rec_len = buf[pos]
        if rec_len == 0:
            # records never straddle sectors; skip to next sector
            pos = (pos // SECTOR + 1) * SECTOR
            continue
        rec = buf[pos:pos + rec_len]
        ext_lba = struct.unpack_from("<I", rec, 2)[0]
        ext_size = struct.unpack_from("<I", rec, 10)[0]
        flags = rec[25]
        name_len = rec[32]
        raw_name = rec[33:33 + name_len]
        pos += rec_len
        if raw_name in (b"\0", b"\1"):
            continue
        name = raw_name.decode("ascii", "replace").split(";", 1)[0]
        entries.append(IsoEntry(name, ext_lba, ext_size, bool(flags & 2)))
    return entries


def iso_read_file(iso_path: str | os.PathLike, inner_path: str, max_size: int = 1 << 20) -> bytes:
    """Return the contents of a (small) file inside an ISO 9660 image."""
    with open(iso_path, "rb") as f:
        f.seek(16 * SECTOR)
        pvd = f.read(SECTOR)
        if pvd[1:6] != b"CD001":
            raise ValueError("not an ISO 9660 image")
        root = pvd[156:156 + 34]
        lba = struct.unpack_from("<I", root, 2)[0]
        size = struct.unpack_from("<I", root, 10)[0]
        parts = [p for p in inner_path.replace("\\", "/").split("/") if p]
        for i, part in enumerate(parts):
            entries = _iso_read_dir(f, lba, size)
            match = next((e for e in entries if e.name.upper() == part.upper()), None)
            if match is None:
                raise FileNotFoundError(inner_path)
            if i == len(parts) - 1:
                if match.is_dir:
                    raise IsADirectoryError(inner_path)
                f.seek(match.lba * SECTOR)
                return f.read(min(match.size, max_size))
            if not match.is_dir:
                raise NotADirectoryError(part)
            lba, size = match.lba, match.size
    raise FileNotFoundError(inner_path)


@dataclass
class GameImage:
    path: str
    title_id: str
    title: str
    disc_version: str  # APP_VER on the disc (normally 01.00)

    @property
    def region(self) -> str:
        return REGION_BY_PREFIX.get(self.title_id[:4], "?")


REGION_BY_PREFIX = {"BCES": "EU", "BCUS": "US", "BCJS": "JP", "BCAS": "ASIA", "BCKS": "KR",
                    "NPEA": "EU", "NPUA": "US", "NPJA": "JP", "NPHA": "ASIA"}


def identify_iso(iso_path: str | os.PathLike) -> GameImage:
    sfo = parse_sfo(iso_read_file(iso_path, "PS3_GAME/PARAM.SFO"))
    return GameImage(str(iso_path), str(sfo.get("TITLE_ID", "")), str(sfo.get("TITLE", "")),
                     str(sfo.get("APP_VER", "")))


def identify_folder(folder: str | os.PathLike) -> GameImage:
    """Identify an extracted disc folder (the one containing PS3_GAME)."""
    sfo = read_sfo(os.path.join(folder, "PS3_GAME", "PARAM.SFO"))
    return GameImage(str(folder), str(sfo.get("TITLE_ID", "")), str(sfo.get("TITLE", "")),
                     str(sfo.get("APP_VER", "")))


# --------------------------------------------------------------------------- PKG


@dataclass
class PkgInfo:
    content_id: str
    title_id: str
    size: int
    app_version: Optional[str]
    requires_version: Optional[str]  # APP_VER that must already be installed (patch chain)


def read_pkg_header(path: str | os.PathLike) -> PkgInfo:
    with open(path, "rb") as f:
        hdr = f.read(0x100)
        if hdr[:4] != b"\x7fPKG":
            raise ValueError("not a PS3 PKG")
        meta_offset, meta_count, _meta_size = struct.unpack_from(">III", hdr, 8)
        total_size = struct.unpack_from(">Q", hdr, 0x18)[0]
        content_id = hdr[0x30:0x60].split(b"\0", 1)[0].decode("ascii", "replace")
        f.seek(meta_offset)
        app_ver = req_ver = None
        for _ in range(meta_count):
            mtype, msize = struct.unpack(">II", f.read(8))
            body = f.read(msize)
            if mtype == 0x8 and msize >= 8:  # software revision: unk, fw(2), version(2), app_version(2) - BCD
                app_ver = f"{body[6]:02x}.{body[7]:02x}"
            elif mtype == 0xB and msize >= 2 and body[:2] != b"\0\0":  # prerequisite app version (BCD)
                req_ver = f"{body[0]:02x}.{body[1]:02x}"
    return PkgInfo(content_id, content_id[7:16], total_size, app_ver, req_ver)


def verify_pkg(path: str | os.PathLike, progress: Optional[Callable[[int, int], None]] = None) -> bool:
    """A retail PKG ends with a 0x20 byte footer whose first 20 bytes are the
    SHA-1 of everything before it. Returns True if the file is intact."""
    size = os.path.getsize(path)
    if size < 0x100:
        return False
    try:
        declared = read_pkg_header(path).size
    except ValueError:
        return False
    if declared != size:
        return False
    h = hashlib.sha1()
    remaining = size - 0x20
    done = 0
    with open(path, "rb") as f:
        while remaining > 0:
            chunk = f.read(min(8 << 20, remaining))
            if not chunk:
                return False
            h.update(chunk)
            remaining -= len(chunk)
            done += len(chunk)
            if progress:
                progress(done, size - 0x20)
        footer = f.read(0x20)
    return footer[:20] == h.digest()
