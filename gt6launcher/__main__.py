"""Entry point.  `gt6-launcher` opens the GUI; sub-commands allow scripted use:

  gt6-launcher status
  gt6-launcher add-game <iso|folder>
  gt6-launcher firmware [PUP]
  gt6-launcher updates [TITLE] [--target 01.22]
  gt6-launcher prepare [TITLE]          write RPCS3 config + patches only
  gt6-launcher play [TITLE]
  gt6-launcher mod-import <zip|folder> | mod-install [TITLE] | mod-uninstall [TITLE]
"""
from __future__ import annotations

import argparse
import sys


def _progress(label: str, done: int, total: int) -> None:
    if total:
        sys.stdout.write(f"\r{label}: {100 * done / total:5.1f}%   ")
    else:
        sys.stdout.write(f"\r{label}...   ")
    sys.stdout.flush()


def cli(argv: list[str]) -> int:
    from . import mods
    from .core import Core
    from .rpcs3 import STOCK_BUILD_WARNING, is_patched_build

    ap = argparse.ArgumentParser(prog="gt6-launcher")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    p = sub.add_parser("add-game"); p.add_argument("path")
    p = sub.add_parser("firmware"); p.add_argument("pup", nargs="?")
    p = sub.add_parser("updates"); p.add_argument("title", nargs="?"); p.add_argument("--target")
    for c in ("prepare", "play", "mod-install", "mod-uninstall"):
        p = sub.add_parser(c); p.add_argument("title", nargs="?")
    p = sub.add_parser("mod-import"); p.add_argument("path")
    a = ap.parse_args(argv)
    core = Core()

    def entry(tid):
        games = core.games()
        g = next((g for g in games if g.title_id == tid), None) if tid else core.active()
        if not g:
            raise SystemExit("no such game - use add-game first")
        return g

    if a.cmd == "status":
        rp = core.rpcs3_path()
        print("RPCS3:", rp or "not found", "" if not rp or is_patched_build(rp) else f"\n  ! {STOCK_BUILD_WARNING}")
        if rp:
            print("Firmware:", core.rpcs3().firmware_version() or "not installed")
        for g in core.games():
            print(f"{g.label}: {g.image.path}\n  installed {g.installed or '01.00'}, target {core.target_version(g.title_id)}, "
                  f"mods {mods.installed_stack(g.title_id) or '-'}")
    elif a.cmd == "add-game":
        print(core.add_game(a.path).label)
    elif a.cmd == "firmware":
        if a.pup:
            core.data["firmware_path"] = a.pup
        core.ensure_firmware(_progress)
        print("\nfirmware", core.rpcs3().firmware_version())
    elif a.cmd == "updates":
        g = entry(a.title)
        if a.target:
            core.set_target_version(g.title_id, a.target)
        print("\nnow at", core.install_updates(g.title_id, _progress))
    elif a.cmd == "prepare":
        print("\n".join(core.prepare(entry(a.title))))
    elif a.cmd == "play":
        return core.launch(entry(a.title)).wait()
    elif a.cmd == "mod-import":
        print(mods.stage_download(a.path, _progress))
    elif a.cmd == "mod-install":
        g = entry(a.title)
        for m in mods.KNOWN_MODS:
            if mods.staged(m.id) and m.id not in mods.installed_stack(g.title_id):
                print(f"\n{m.name}: {mods.install(g.title_id, m.id, _progress)} files")
    elif a.cmd == "mod-uninstall":
        g = entry(a.title)
        while mods.installed_stack(g.title_id):
            print("removed", mods.uninstall_top(g.title_id))
    return 0


def main() -> int:
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-psn"):
        return cli(sys.argv[1:])
    from .ui import main as gui_main
    return gui_main()


if __name__ == "__main__":
    sys.exit(main())
