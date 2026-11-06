# GT6-patched RPCS3

Gran Turismo 6 PC ships RPCS3 built from upstream commit **`eee3f0f7c`** (0.0.43-20565) plus the
patches in [`gt6-patches/`](gt6-patches), applied in order:

| Patch | Fixes |
|---|---|
| `01-rt-reload-race` | Stale horizontal bands in races: GT6's SPUs write a frame in strips while the RSX reads it back. Memory is now tagged before it is read, so strips written during the load are reloaded. |
| `02-blit-reprotect` | Texture-cache consistency when a blit lands in an already protected section |
| `03-vdec-intro-skip-crash` | Crash when skipping the intro movie (video decoder handed out a picture it had announced as gone) |
| `04-savestate-keeps-config` | Save states keep the per-game config (otherwise the world renders black after loading one) |
| `05-savestate-pending-sysutil` | Saving a state during the opening movie no longer aborts |
| `06-usercmd-no-drain-stall` | **The ~1 s freezes in races** (RPCS3 #19549): pre-#19549 USER_COMMAND behaviour. `RPCS3_USERCMD_MODE=upstream` restores upstream behaviour for A/B tests. |
| `07-gt6-theme-and-memlock` | Launcher colours for the in-game home menu, window icon from `GT6_WINDOW_ICON`, and memory locking stops after the first failure (no syscall + log spam when the system limit is low) |

Patches 01–05 started from abowen's GT6 RPCS3 research and were rebased onto the current upstream.

## Build (Linux)

```sh
git clone https://github.com/RPCS3/rpcs3.git emulator/rpcs3-src
git -C emulator/rpcs3-src checkout eee3f0f7c && git -C emulator/rpcs3-src submodule update --init --recursive
emulator/scripts/build_rpcs3.sh       # -> emulator/out/rpcs3-gt6-x86_64.AppImage
```

The script expects clang, Ninja, Qt 6, LLVM and Vulkan headers, plus `linuxdeploy` / `appimagetool`
in `emulator/tools/`. It applies the patches to a clean tree at the pinned commit.

`ci/make_gt6_branch.sh` creates a `gt6` branch (upstream + patches) that RPCS3's own CI can build
for Windows and Linux on a fork.

`scripts/gt6ctl.py` and `scripts/bench_config.py` drive benchmark runs: an XWayland window, FPS from
the window title, and counts of RSX stalls from the log.

RPCS3 is licensed under GPL-2.0; these patches are under the same license.
