#!/usr/bin/env python3
"""Drive an RPCS3/GT6 session for benchmarking (XWayland window, XTest input).

  gt6ctl.py start  --rpcs3 PATH --root DATAROOT --game ISO [--env K=V ...] [--cfg K.K=V ...]
  gt6ctl.py title                     # current window title (FPS etc.)
  gt6ctl.py key NAME [hold_ms]        # e.g. Return, x, Up, Down, Left, Right, Escape
  gt6ctl.py shot OUT.png
  gt6ctl.py sample SECONDS OUT.csv    # 1 Hz FPS samples from the title
  gt6ctl.py stop
  gt6ctl.py report                    # stall/patch counts from RPCS3.log
"""
import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

STATE = Path(os.environ.get("GT6CTL_STATE", os.path.join(__import__("tempfile").gettempdir(), "gt6ctl.json")))


def _x():
    from Xlib import X, XK, display
    from Xlib.ext import xtest
    return X, XK, display, xtest


def find_window():
    X, XK, display, xtest = _x()
    d = display.Display()
    root = d.screen().root
    ids = root.get_full_property(d.intern_atom("_NET_CLIENT_LIST"), X.AnyPropertyType)
    best = None
    for wid in (ids.value if ids else []):
        w = d.create_resource_object("window", wid)
        try:
            name = w.get_full_property(d.intern_atom("_NET_WM_NAME"), d.intern_atom("UTF8_STRING"))
            name = name.value.decode() if name else (w.get_wm_name() or "")
        except Exception:
            continue
        if "FPS:" in name:
            best = (w, name)
    return d, best


def cmd_start(a):
    env = dict(os.environ)
    env.update(XDG_CONFIG_HOME=f"{a.root}/xdg-config", XDG_CACHE_HOME=f"{a.root}/xdg-cache", QT_QPA_PLATFORM="xcb")
    for kv in a.env or []:
        k, v = kv.split("=", 1)
        env[k] = v
    sys.path.insert(0, str(Path(__file__).parent))
    import seed_gui
    seed_gui.seed(Path(a.root) / "xdg-config" / "rpcs3")
    log = open(f"{a.root}/bench-stdout.log", "w")
    p = subprocess.Popen([a.rpcs3, "--no-gui", a.game, *a.args], env=env, stdout=log, stderr=subprocess.STDOUT,
                         start_new_session=True)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"pid": p.pid, "root": a.root, "t0": time.time()}))
    print(p.pid)


def cmd_title(a):
    _, best = find_window()
    print(best[1] if best else "(no window)")


KEYMAP = {"enter": "Return", "start": "Return", "cross": "x", "circle": "c", "square": "z", "triangle": "v",
          "select": "space", "r1": "e", "l1": "q", "r2": "t", "l2": "r"}


def cmd_key(a):
    X, XK, display, xtest = _x()
    d, best = find_window()
    if not best:
        sys.exit("no window")
    w = best[0]
    w.set_input_focus(X.RevertToParent, X.CurrentTime)
    w.configure(stack_mode=X.Above)
    d.sync()
    time.sleep(0.15)
    name = KEYMAP.get(a.name.lower(), a.name)
    code = d.keysym_to_keycode(XK.string_to_keysym(name))
    if not code:
        sys.exit(f"unknown key {name}")
    xtest.fake_input(d, X.KeyPress, code)
    d.sync()
    time.sleep(a.hold / 1000)
    xtest.fake_input(d, X.KeyRelease, code)
    d.sync()


def cmd_shot(a):
    # spectacle: -b background, -n no notification, -a active window
    cmd_key_focus()
    subprocess.run(["spectacle", "-b", "-n", "-a", "-o", a.out], check=False, timeout=30,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(a.out if Path(a.out).exists() else "screenshot failed")


def cmd_key_focus():
    X, *_ = _x()
    d, best = find_window()
    if best:
        best[0].set_input_focus(X.RevertToParent, X.CurrentTime)
        best[0].configure(stack_mode=X.Above)
        d.sync()
        time.sleep(0.3)


def parse_fps(title):
    m = re.search(r"FPS:\s*([\d.]+)", title)
    return float(m.group(1)) if m else None


def cmd_sample(a):
    with open(a.out, "w") as f:
        f.write("t,fps,title\n")
        t0 = time.time()
        while time.time() - t0 < a.seconds:
            _, best = find_window()
            title = best[1] if best else ""
            f.write(f"{time.time() - t0:.1f},{parse_fps(title) or ''},\"{title}\"\n")
            f.flush()
            time.sleep(1)
    rows = [float(l.split(",")[1]) for l in open(a.out).read().splitlines()[1:] if l.split(",")[1]]
    if rows:
        rows.sort()
        print(json.dumps({"n": len(rows), "mean": round(sum(rows) / len(rows), 1), "min": rows[0],
                          "p5": rows[max(0, len(rows) // 20)], "below55": sum(r < 55 for r in rows)}))


def cmd_stop(a):
    st = json.loads(STATE.read_text())
    try:
        os.killpg(st["pid"], signal.SIGTERM)
        time.sleep(3)
        os.killpg(st["pid"], signal.SIGKILL)
    except ProcessLookupError:
        pass
    print("stopped")


def cmd_report(a):
    st = json.loads(STATE.read_text())
    lf = Path(st["root"]) / "xdg-cache" / "rpcs3" / "RPCS3.log"
    txt = lf.read_text(errors="replace")
    out = {
        "rsx_queue_stuck": txt.count("RSX queue appears to be stuck"),
        "applied_patches": len(set(re.findall(r"Applied patch \(hash='[^']+', description='([^']+)'", txt))),
        "fatal": len(re.findall(r"^·F ", txt, re.M)),
        "errors": len(re.findall(r"^·E ", txt, re.M)),
        "ppu_hash": (re.findall(r"PPU executable hash: (PPU-[0-9a-f]+)", txt) or [""])[-1],
        "version": (re.findall(r"Version: APP_VER=(\S+)", txt) or [""])[-1],
    }
    print(json.dumps(out))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("start")
    s.add_argument("--rpcs3", required=True)
    s.add_argument("--root", required=True)
    s.add_argument("--game", required=True)
    s.add_argument("--env", action="append")
    s.add_argument("args", nargs="*")
    sp.add_parser("title")
    k = sp.add_parser("key")
    k.add_argument("name")
    k.add_argument("hold", nargs="?", type=int, default=120)
    sh = sp.add_parser("shot")
    sh.add_argument("out")
    sa = sp.add_parser("sample")
    sa.add_argument("seconds", type=int)
    sa.add_argument("out")
    sp.add_parser("stop")
    sp.add_parser("report")
    a = ap.parse_args()
    globals()["cmd_" + a.cmd](a)


if __name__ == "__main__":
    main()
