"""Gamepad detection + RPCS3 input configuration.

RPCS3 binds a player to a device by exact name. For its SDL handler the name is
"<SDL gamepad name> <n>" (n counts devices with the same name, starting at 1 -
see rpcs3/Input/sdl_pad_handler.cpp). We ask SDL3 itself (ctypes, no Python
bindings needed) so the names match RPCS3 exactly.

RPCS3 first applies the handler's default button mapping and then overlays the
file, so writing only Handler + Device gives a fully mapped pad.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import glob
import os
import sys
from typing import Optional

from . import paths
from .yamlio import atomic_write, dump_cfg, load_cfg

SDL_INIT_GAMEPAD = 0x00002000


def _load_sdl3() -> Optional[ctypes.CDLL]:
    names = []
    base = getattr(sys, "_MEIPASS", None)
    if paths.IS_WINDOWS:
        if base:
            names.append(os.path.join(base, "SDL3.dll"))
        names += [os.path.join(os.path.dirname(sys.executable), "SDL3.dll"), "SDL3.dll"]
    else:
        if base:
            names += glob.glob(os.path.join(base, "libSDL3.so*"))
        names += ["libSDL3.so.0", "libSDL3.so", ctypes.util.find_library("SDL3") or ""]
    for n in filter(None, names):
        try:
            return ctypes.CDLL(n)
        except OSError:
            continue
    return None


def list_gamepads() -> Optional[list[str]]:
    """RPCS3-style SDL device names of connected gamepads, or None if SDL3 is unavailable."""
    sdl = _load_sdl3()
    if sdl is None:
        return None
    sdl.SDL_Init.argtypes = [ctypes.c_uint32]
    sdl.SDL_Init.restype = ctypes.c_bool
    sdl.SDL_GetGamepads.argtypes = [ctypes.POINTER(ctypes.c_int)]
    sdl.SDL_GetGamepads.restype = ctypes.POINTER(ctypes.c_uint32)
    sdl.SDL_GetGamepadNameForID.argtypes = [ctypes.c_uint32]
    sdl.SDL_GetGamepadNameForID.restype = ctypes.c_char_p
    sdl.SDL_free.argtypes = [ctypes.c_void_p]
    sdl.SDL_SetHint.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    # same hints RPCS3 sets (they can change which driver - and name - SDL uses)
    for k, v in ((b"SDL_JOYSTICK_HIDAPI_PS3_SIXAXIS_DRIVER", b"1"), (b"SDL_JOYSTICK_HIDAPI_PS3", b"1"),
                 (b"SDL_JOYSTICK_HIDAPI_LG4FF", b"0")):
        sdl.SDL_SetHint(k, v)
    if not sdl.SDL_Init(SDL_INIT_GAMEPAD):
        return None
    try:
        count = ctypes.c_int(0)
        ids = sdl.SDL_GetGamepads(ctypes.byref(count))
        seen: dict[str, int] = {}
        out = []
        for i in range(count.value):
            raw = sdl.SDL_GetGamepadNameForID(ids[i])
            name = raw.decode("utf-8", "replace") if raw else "Gamepad"
            seen[name] = seen.get(name, 0) + 1
            out.append(f"{name} {seen[name]}")
        if ids:
            sdl.SDL_free(ids)
        return out
    finally:
        sdl.SDL_QuitSubSystem.argtypes = [ctypes.c_uint32]
        sdl.SDL_QuitSubSystem(SDL_INIT_GAMEPAD)


def input_config_path() -> str:
    # global profile "Default" (system_utils.cpp: <config>/input_configs/global/Default.yml)
    return os.path.join(paths.rpcs3_config_dir(), "input_configs", "global", "Default.yml")


def current_player1() -> tuple[str, str]:
    cfg = load_cfg(input_config_path())
    p = cfg.get("Player 1 Input", {}) or {}
    return str(p.get("Handler", "")), str(p.get("Device", ""))


def configure(mode: str, device: str = "", log=print) -> str:
    """mode: 'auto' (first gamepad, else keyboard), 'pad' (given device), 'keyboard',
    'manual' (leave RPCS3's own input config alone). Returns a description."""
    if mode == "manual":
        return "Controller setup managed in RPCS3"
    pads = list_gamepads()
    if mode == "auto":
        if pads:
            device = pads[0]
            mode = "pad"
        elif pads is None:
            return "SDL3 not found - controller config unchanged"
        else:
            mode = "keyboard"
    cfg = load_cfg(input_config_path())
    p1 = dict(cfg.get("Player 1 Input", {}) or {})
    if mode == "pad" and device:
        new = {"Handler": "SDL", "Device": device}
    else:
        new = {"Handler": "Keyboard", "Device": "Keyboard"}
    if p1.get("Handler") != new["Handler"] or p1.get("Device") != new["Device"]:
        # handler changed -> drop the old button map so RPCS3 applies the new handler's defaults
        p1 = new
        cfg["Player 1 Input"] = p1
        atomic_write(input_config_path(), dump_cfg(cfg))
        log(f"controller: player 1 -> {new['Handler']} / {new['Device']}")
    return f"Player 1: {new['Device']}" if new["Handler"] == "SDL" else "Player 1: keyboard (no gamepad found)"


# =========================================================================== racing wheels
# RPCS3 emulates a Logitech G27 (natively supported by GT6) driven by any SDL joystick.
# Its mapping file is <config>/LogitechG27.yml (Emu/Io/LogitechG27Config.h). Each control
# names a device by "device_type_id" = num_buttons<<52 | num_hats<<42 | num_axes<<32 |
# vendor<<16 | product, plus a button/hat/axis index. Pedal axes: released must read as the
# axis minimum, so a pedal that rests at +32767 needs reverse: true.

SDL_INIT_JOYSTICK = 0x00000200
SDL_JOYSTICK_TYPE_WHEEL = 2

G27_KEYS = ["steering", "throttle", "brake", "clutch", "shift_up", "shift_down", "up", "down", "left", "right",
            "triangle", "cross", "square", "circle", "l2", "l3", "r2", "r3", "plus", "minus", "dial_clockwise",
            "dial_anticlockwise", "dial_center", "select", "pause", "ps", "shifter_1", "shifter_2", "shifter_3",
            "shifter_4", "shifter_5", "shifter_6", "shifter_r"]


def type_id(vendor: int, product: int, axes: int, hats: int, buttons: int) -> int:
    m = (1 << 10) - 1
    return product | (vendor << 16) | ((axes & m) << 32) | ((hats & m) << 42) | ((buttons & m) << 52)


class Joysticks:
    """Live access to all SDL joysticks (for detection and the wheel set-up wizard)."""

    def __init__(self):
        self.sdl = _load_sdl3()
        if self.sdl is None:
            raise RuntimeError("SDL3 library not found")
        s = self.sdl
        for name, args, res in (
                ("SDL_Init", [ctypes.c_uint32], ctypes.c_bool),
                ("SDL_GetJoysticks", [ctypes.POINTER(ctypes.c_int)], ctypes.POINTER(ctypes.c_uint32)),
                ("SDL_OpenJoystick", [ctypes.c_uint32], ctypes.c_void_p),
                ("SDL_CloseJoystick", [ctypes.c_void_p], None),
                ("SDL_GetJoystickName", [ctypes.c_void_p], ctypes.c_char_p),
                ("SDL_GetJoystickVendor", [ctypes.c_void_p], ctypes.c_uint16),
                ("SDL_GetJoystickProduct", [ctypes.c_void_p], ctypes.c_uint16),
                ("SDL_GetJoystickType", [ctypes.c_void_p], ctypes.c_int),
                ("SDL_GetNumJoystickAxes", [ctypes.c_void_p], ctypes.c_int),
                ("SDL_GetNumJoystickHats", [ctypes.c_void_p], ctypes.c_int),
                ("SDL_GetNumJoystickButtons", [ctypes.c_void_p], ctypes.c_int),
                ("SDL_GetJoystickAxis", [ctypes.c_void_p, ctypes.c_int], ctypes.c_int16),
                ("SDL_GetJoystickHat", [ctypes.c_void_p, ctypes.c_int], ctypes.c_uint8),
                ("SDL_GetJoystickButton", [ctypes.c_void_p, ctypes.c_int], ctypes.c_bool),
                ("SDL_UpdateJoysticks", [], None),
                ("SDL_free", [ctypes.c_void_p], None),
                ("SDL_QuitSubSystem", [ctypes.c_uint32], None)):
            fn = getattr(s, name)
            fn.argtypes, fn.restype = args, res
        if not s.SDL_Init(SDL_INIT_JOYSTICK):
            raise RuntimeError("SDL joystick init failed")
        self.devices: list[dict] = []
        self.refresh()

    def refresh(self) -> list[dict]:
        self.close_all()
        s = self.sdl
        n = ctypes.c_int(0)
        ids = s.SDL_GetJoysticks(ctypes.byref(n))
        for i in range(n.value):
            h = s.SDL_OpenJoystick(ids[i])
            if not h:
                continue
            raw = s.SDL_GetJoystickName(h)
            d = {"handle": h, "name": raw.decode("utf-8", "replace") if raw else "Joystick",
                 "vendor": s.SDL_GetJoystickVendor(h), "product": s.SDL_GetJoystickProduct(h),
                 "axes": s.SDL_GetNumJoystickAxes(h), "hats": s.SDL_GetNumJoystickHats(h),
                 "buttons": s.SDL_GetNumJoystickButtons(h)}
            d["is_wheel"] = s.SDL_GetJoystickType(h) == SDL_JOYSTICK_TYPE_WHEEL or "wheel" in d["name"].lower()
            d["type_id"] = type_id(d["vendor"], d["product"], d["axes"], d["hats"], d["buttons"])
            self.devices.append(d)
        if ids:
            s.SDL_free(ids)
        return self.devices

    def state(self) -> list[dict]:
        """Snapshot of every axis/hat/button of every device."""
        s = self.sdl
        s.SDL_UpdateJoysticks()
        out = []
        for d in self.devices:
            h = d["handle"]
            out.append({"axes": [s.SDL_GetJoystickAxis(h, i) for i in range(d["axes"])],
                        "hats": [s.SDL_GetJoystickHat(h, i) for i in range(d["hats"])],
                        "buttons": [bool(s.SDL_GetJoystickButton(h, i)) for i in range(d["buttons"])]})
        return out

    def close_all(self) -> None:
        for d in self.devices:
            self.sdl.SDL_CloseJoystick(d["handle"])
        self.devices = []

    def close(self) -> None:
        self.close_all()
        self.sdl.SDL_QuitSubSystem(SDL_INIT_JOYSTICK)


HAT_BITS = {1: "up", 2: "right", 4: "down", 8: "left"}


def detect_change(base: list[dict], now: list[dict], devices: list[dict], want: str,
                  exclude: set = frozenset()) -> Optional[dict]:
    """Return the first clear input change between two snapshots.
    want: 'axis' (moved > 50 % of the range), 'button' (button/hat pressed), 'any'."""
    best = None
    for di, (b, n) in enumerate(zip(base, now)):
        tid = devices[di]["type_id"]
        if want in ("axis", "any"):
            for i, (bv, nv) in enumerate(zip(b["axes"], n["axes"])):
                if (tid, "axis", i) in exclude:
                    continue
                delta = nv - bv
                if abs(delta) > 0x7FFF * 0.5 and (best is None or abs(delta) > best["delta"]):
                    best = {"device_type_id": tid, "type": "axis", "id": i, "hat": "", "delta": abs(delta),
                            "rest": bv, "moved": nv}
        if want in ("button", "any") and best is None:
            for i, (bv, nv) in enumerate(zip(b["buttons"], n["buttons"])):
                if nv and not bv and (tid, "button", i) not in exclude:
                    return {"device_type_id": tid, "type": "button", "id": i, "hat": "", "delta": 1}
            for i, (bv, nv) in enumerate(zip(b["hats"], n["hats"])):
                new = nv & ~bv
                for bit, comp in HAT_BITS.items():
                    if new & bit and (tid, "hat", i, comp) not in exclude:
                        return {"device_type_id": tid, "type": "hat", "id": i, "hat": comp, "delta": 1}
    return best


def g27_config_path() -> str:
    # fs::get_config_dir(true): on Windows RPCS3 keeps this in the "config" sub-folder
    sub = "config" if paths.IS_WINDOWS else ""
    return os.path.join(paths.rpcs3_config_dir(), sub, "LogitechG27.yml")


def write_g27_config(mapping: dict[str, dict], enabled: bool, ffb_device: int = 0) -> str:
    """mapping: G27 key -> {device_type_id, type, id, hat, reverse}. Unmapped keys point to
    device 0 (never present -> neutral / not pressed)."""
    cfg: dict = {}
    for k in G27_KEYS:
        m = mapping.get(k)
        if m:
            cfg[k] = {"device_type_id": int(m["device_type_id"]), "type": m["type"], "id": int(m["id"]),
                      "hat": m.get("hat", ""), "reverse": bool(m.get("reverse", False))}
        else:
            cfg[k] = {"device_type_id": 0, "type": "button", "id": 0, "hat": "", "reverse": False}
    cfg.update({"reverse_effects": False, "ffb_direction_type": "steering_axis", "compatibility_limit": 4,
                "ffb_device_type_id": int(ffb_device), "led_device_type_id": 0, "enabled": bool(enabled)})
    p = g27_config_path()
    atomic_write(p, dump_cfg(cfg))
    return p
