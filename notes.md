# Work notes

Updated: 2026-11-09

## Current request

The user asked to collect all tickets from `https://github.com/Mabec-games/Gran-Turismo-6-PC/issues` and try to resolve them. The issue list is now readable through web browsing (six open issues). Continue investigating fixes, prioritizing Windows RPCS3 config path consistency.

## Work completed in this session

### Controller and wheel report

The user supplied this issue report:

> keeps defaulting to Keyboard and mouse as a gamepad. Tried ps4 controller, dualsense and 8bit do. Shit I even tried my fanatec wheel and it won't register during wheel set up

Repo history already contained Windows-related fixes:

* `8587f67` fixed the launcher becoming unresponsive when a background task completed.
* `4bcc4db` addressed a Windows RPCS3 startup failure involving `vcruntime140.dll`.
* `c53adcd` added Windows XInput discovery for Xbox pads and 8BitDo in X-input mode, and allowed SDL time to discover devices.

Those commits did not prove that PlayStation pads, Fanatec wheels, or other Windows hardware works. The Windows package had not been played on a Windows PC.

Changes made for the newly reported behavior:

* In `gt6launcher/gamepad.py`, Automatic mode no longer rewrites RPCS3 Player 1 to Keyboard when the launcher detects no gamepad. It leaves the existing RPCS3 input profile in place. Keyboard remains an explicit selectable mode.
* The UI text in `gt6launcher/ui.py` now describes that behavior.
* SDL joystick hints used by gamepad detection are shared with the wheel wizard. The wheel wizard sets the hints before SDL initialization and pumps SDL events before listing devices. Its initial scan waits briefly for asynchronous Windows device discovery; subsequent refreshes pump without the delay.

These changes prevent an empty scan from overwriting an existing controller selection and improve the wheel wizard's initial enumeration. They do **not** confirm that the listed hardware is detected or usable; that needs a Windows test with the reported devices.

### Portable Windows data

The user requested that the Windows package keep its data out of `%APPDATA%` / `%LOCALAPPDATA%`.

* `gt6launcher/paths.py`: a frozen Windows build now defaults to `<launcher directory>\\data\\`. Launcher settings, logs, downloads, mods, backups, RPCS3 config/cache, installed game data, and saves are rooted under this directory via the shared path helpers and `RPCS3_CONFIG_DIR`.
* `GT6L_HOME` remains an explicit override (also used by the CI smoke workflow).
* Running from source on Windows still defaults to `%LOCALAPPDATA%\\GT6Launcher`; the change is for the packaged/frozen Windows build.
* `packaging/build_windows.ps1` and `README.md` were updated to describe the portable data location.
* Existing data in `%LOCALAPPDATA%\\GT6Launcher` is not migrated or deleted. The portable package folder must be writable.

### Windows build attempt

The user asked to compile a Windows build for testing. No Windows package was produced.

* The host is Linux (`CachyOS`) with Wine 11.21 and a MinGW cross-compiler, but no Windows Python or PyInstaller installation.
* `gh auth status` reported that the saved `Mabec-games` CLI token is invalid.
* `gh auth login -h github.com` was attempted twice. Both attempts failed before browser authentication with `error connecting to github.com`.
* A direct `curl` connectivity check also failed DNS resolution for `www.python.org`.
* The repo's Windows GitHub Actions workflow exists, but it cannot build these local uncommitted changes until they are pushed to a branch; this session currently cannot reach GitHub.

The invalid `gh` status refers to the credential saved in this execution environment, not proof that the user's GitHub account is invalid. Do not request or store the user's password or token in project files.

## GitHub issue collection status

* The open issue list contains #1-#6. Pages #2-#6 were readable. The #1 body and GitHub user-attachment files (logs/DxDiag) were not retrievable by the web browser.
* Do not describe the issue attachments as reviewed; log retrieval is still needed to diagnose #5 and confirm #6.

## Files changed (uncommitted)

* `README.md` — documents portable Windows data under `data\\`.
* `gt6launcher/paths.py` — frozen Windows build uses `data\\` beside the executable; RPCS3 config path follows an adjacent `portable/` folder if RPCS3 gives it precedence; adds `rpcs3_settings_dir()` (`<cfg_dir>/config` on Windows) and uses it for `custom_config_file()`.
* `gt6launcher/patches.py` — `write_patch_config()` writes `patch_config.yml` inside `rpcs3_settings_dir()`.
* `gt6launcher/gamepad.py` — uses `rpcs3_settings_dir()` for `Default.yml` and `LogitechG27.yml`; loads `gamecontrollerdb.txt` in `_sdl_gamepads()`; shared SDL hints and event pumping; Automatic keeps existing pad config on an empty scan.
* `gt6launcher/lan.py` — uses `rpcs3_settings_dir()` for `config.yml` and `rpcn.yml`.
* `gt6launcher/core.py` — resolves RPCS3 early on Windows; `PROFILE_REV = 4` cleans up stale top-level Windows config files; calls `seed_gui_settings()` and `write_patch_config(paths.rpcs3_settings_dir(cfg_dir), ...)` in `prepare()`.
* `gt6launcher/rpcs3.py` — registers each RPCS3 executable with `paths.set_rpcs3_binary()`; `seed_gui_settings()` ensures `log/` exists and copies `config_database.dat`, `compat_database.dat`, and `gamecontrollerdb.txt` into `data\\rpcs3\\` on Windows.
* `gt6launcher/ui.py` — explains Automatic controller fallback and throttles empty wheel-wizard rescans to once per second.
* `packaging/build_windows.ps1` — updates the packaging comment for the data location.
* `packaging/install_windows_python_wine.sh` — downloads/checksums Python 3.12.10 and installs it in an isolated Wine prefix.
* `packaging/build_windows_wine.sh` — local Bash build path that runs Windows PyInstaller under Wine and supports `GT6L_BUNDLE_RPCS3_DIR`, `GT6_WIN_VENV`, and `GT6_SDL3_DLL`.
* `notes.md` — this record.

The repository was on `main` at `5e239f2` (`v1.1.2`) before these local edits. No commit or push has been made.

## Checks and remaining work

* `git diff --check` completed without whitespace errors.
* The user installed Windows Python 3.12.10 successfully in `/tmp/gt6-winbuild-prefix`.
* Running the existing PowerShell build script through Wine did not start it: Wine's bundled `powershell.exe` reports `fixme:powershell:wmain stub` and only prints the supplied arguments.
* `packaging/build_windows_wine.sh` builds through host `curl`/`7z` and Windows Python under Wine. Wine's bundled PowerShell is a stub, so the `.ps1` build script cannot run under Wine. Wine execution itself is blocked in this sandbox, but the user can run the Bash script in their terminal.
* The user's first ZIP was stock RPCS3; the user correctly flagged that GT6 requires the patched build. A local patched Windows RPCS3 artifact was available under `/tmp`, its sidecar SHA-256 matched, and its executable hash is `3a8bdd40d4c8903028e42b325760737ea04c235006ac16827b4848d220ff9a18` (contains `GT6_WINDOW_ICON`). It was extracted to `/tmp/gt6-patched-rpcs3-20565`.
* Replaced the ZIP's stock emulator with that patched RPCS3 0.0.43-20565 (`eee3f0f7`), added `GT6-PATCHED.txt`, and re-created `dist/GT6-Launcher-win64.zip`. `7z t` passed; the ZIP hash is `53963473f5471fdb68c194d0d429fe5cb72be0e9150a6c73acac87306471987c`. The launcher modules still contain the config-path and controller fixes. It has not been launched on Windows.
* Enumerate the complete GitHub issue list after GitHub access becomes available.
* Run `bash packaging/build_windows_wine.sh` from the repo root or `bash build_windows_wine.sh` from `packaging`; it saves the local ZIP to `dist/GT6-Launcher-win64.zip` and publishes nothing.
* After building, launch from a writable extracted folder and verify no application-owned data is written under AppData.
* Test automatic detection with a DualShock 4, DualSense, and 8BitDo in its reported mode; verify RPCS3 Player 1 configuration before and after a failed/empty scan.
* Test wheel wizard discovery and mapping with the Fanatec wheel/pedals. Confirm wheel input and force feedback in GT6/RPCS3.
* Decide whether existing `%LOCALAPPDATA%\\GT6Launcher` data should be offered for migration. Current code leaves it untouched.

## GitHub issue review and research (2026-11-09)

The issues page is readable through the web browser now. There are six open issues (#1-#6). The descriptions for #1 and the attached diagnostic/log files were not retrievable, but the other relevant issue bodies and comments were visible.

### Findings

* #4 (21 GB under AppData): the portable-data change above directly addresses this request for new frozen Windows builds. Existing data is not migrated.
* #6 says launcher graphics, patches, overlays and inputs have no effect, and #2 reports flicker across several Nvidia and AMD systems. These may share a config-path or config-application problem, but the attached DxDiag could not be fetched.
* #3 shows the launcher detecting and selecting `SDL / XInput Controller #1 1`; another commenter says input also fails when configured in RPCS3 directly. This proves launcher-side enumeration, not that the game is reading that same input config.
* RPCS3 Windows source checks for `<RPCS3 executable folder>/portable/` before consulting `RPCS3_CONFIG_DIR`. The config-path fix now shares that precedence: the selected emulator path is registered centrally, and launcher paths use that `portable/` directory when it exists. The launcher logs the effective config directory. Source: https://github.com/RPCS3/rpcs3/blob/master/Utilities/File.cpp
* RPCS3's GT6 graphics reports describe flicker as configuration-sensitive: Write Color Buffers can trigger it for some versions/scenes, with Force CPU Blit documented as an alternate workaround in applicable versions. Other GT6 versions need color buffers, so this cannot be applied as a universal switch. See RPCS3 issue #12567: https://github.com/RPCS3/rpcs3/issues/12567.
* #5 is not confirmed AMD-specific: a second reporter says the same shader-stage exit on an RTX 5060. Its `game exited (code 0)` line alone does not identify a crash. The attached `log.txt` and `RPCS3.log` links returned Cache miss, so the actual error and RPCS3 build are still needed before choosing a fix. An upstream shader-interpreter crash regression around builds 20028-20031 was fixed; compare the reporter's build against that range before considering it relevant: https://github.com/RPCS3/rpcs3/issues/19548.

### Next verification

Build and run on Windows with the bundled RPCS3, then select an external RPCS3 install that has a `portable/` folder. Confirm the About screen, launcher writes, RPCS3 log path, `RPCS3_CONFIG_DIR`, and RPCS3's `Applying custom config` log all use that same directory. Retest issue #6 and controller input. Do not change GT6 render defaults based only on generic flicker reports. For #5, obtain an accessible `RPCS3.log` before changing emulator or shader settings.

### Issue #8 flickering follow-up

* The secret Gist upload succeeded. The uploaded ZIP is the 0.0.43-20565 GT6-patched RPCS3 build and launcher changes available at build time; two issue #8 reporters downloaded it and reported the same flicker. One tested 1.05 and 1.22; another says 1.00 and 1.22 both flicker. Replacing the emulator executable alone did not fix this.
* The user recalled the Linux flicker fix as an add-on in Patches. The local Linux `patch_config.yml` has `Bloom/Glare Resolution Scale Fix` enabled, along with the other resolution-scale companion fixes. `profile.desired_patches()` also selects these companion fixes automatically; their source notes say the bloom/glare patch corrects green/blocky bloom at non-native scales. This is the leading hypothesis for the recalled add-on.
* The launcher is supposed to write this selection into `patch_config.yml` for the active title/version. If the Windows build misses it because RPCS3 reads a different config directory, flicker may persist. Confirm the patch is checked and RPCS3 logs it as enabled before changing the PPU/render settings.

## Root Cause Analysis & Fix Verification (2026-11-09)

1. **`fs::get_config_dir(true)` on Windows appends `"config/"` (`Utilities/File.cpp:2702-2708`)**:
   * On Linux, `fs::get_config_dir(false)` and `fs::get_config_dir(true)` return the same directory.
   * On Windows (`#ifdef _WIN32`), `fs::get_config_dir(false)` returns `<RPCS3_CONFIG_DIR>/`, whereas `fs::get_config_dir(true)` returns `<RPCS3_CONFIG_DIR>/config/`.
   * Up to v1.1.2 (and in the secret Gist test build `4e2888a8...` built from `Gran-Turismo-6-PC` before `launcher/gt6launcher`'s `rpcs3_settings_dir()` changes were synced over), the launcher only used `"config"` for `LogitechG27.yml` and `rpcn.yml`, while writing the 4 critical configuration files directly into `<RPCS3_CONFIG_DIR>/` instead of `<RPCS3_CONFIG_DIR>/config/`:
     * `custom_configs/config_<TITLE>.yml` (`rpcs3/Emu/system_utils.cpp:587` uses `fs::get_config_dir(true) + "custom_configs/"`): RPCS3 on Windows **never loaded the per-game custom config**, so `Force CPU Blit: true` (for 1.00–1.05), `Write Color Buffers: true` + `Read Color Buffers: true` + `Handle RSX Memory Tiling: true` + `Disable ZCull Occlusion Queries: true` + `Accurate RSX reservation access: true` (for 1.06–1.22), `Resolution Scale`, and `Frame limit` were never applied.
     * `patch_config.yml` (`Utilities/bin_patch.cpp:130` uses `fs::get_config_dir(true) + "patch_config.yml"`): **Zero patches were ever enabled on Windows**, including `Bloom/Glare Resolution Scale Fix`, `Auto Exposure Resolution Scale Fix`, `Smoke and Dust Resolution Scale Fix`, `Movie Playback Fix`, `Use Sharper MLAA`, `Sharper Shadows`, and `Unlock FPS`.
     * `input_configs/global/Default.yml` (`rpcs3/Emu/system_utils.cpp:602` uses `fs::get_config_dir(true) + "input_configs/"`): RPCS3 never saw the launcher's `Default.yml` and fell back to Keyboard (`mouse and keyboard are not used as a pad`, Issues #1, #3, #6, #7).
     * `config.yml` (`rpcs3/Emu/System.cpp:503` uses `fs::get_config_dir(true) + "config.yml"`).
   * Fixed by introducing `paths.rpcs3_settings_dir()` across `paths.py`, `patches.py`, `gamepad.py`, `lan.py`, and `core.py` (with `PROFILE_REV = 4` cleanup of stale top-level files).
2. **Bundled Windows RPCS3 build in the Gist ZIP was missing Patch 08 (`08-startup-dialog-steps.diff` / `GT6_LAUNCHER`)**:
   * The Gist build at `/home/martin/Desktop/testt/4e2888a8.../` bundled `/tmp/gt6-patched-rpcs3-20565/rpcs3.exe` from Nov 6 (patches 01–07 only), which lacked `GT6_LAUNCHER` (Patch 08) and could trigger the modal `"Experimental Build Warning"` dialog (`game exited (code 0)` when dismissed, Issue #5).
   * Extracted the Nov 8 v1.1.2 `rpcs3.exe` (CI run `42531024891`, verified to contain both `GT6_WINDOW_ICON` and `GT6_LAUNCHER`) into `/tmp/gt6-patched-rpcs3-v112` and bundled it into the new Windows build.
3. **`log/`, `GuiConfigs/config_database.dat`, and `config/input_configs/gamecontrollerdb.txt` in portable `data\rpcs3\`**:
   * Because `RPCS3_CONFIG_DIR` points to `data\rpcs3\` while `rpcs3.exe` lives in `rpcs3\`, `seed_gui_settings()` now ensures `data\rpcs3\log` exists before RPCS3 starts, copies `GuiConfigs/config_database.dat` and `compat_database.dat` from `rpcs3\GuiConfigs\`, and copies `gamecontrollerdb.txt` into `data\rpcs3\config\input_configs\gamecontrollerdb.txt` (which `_sdl_gamepads()` also loads via `SDL_AddGamepadMappingsFromFile`).
4. **Wine Verification & Rebuilt Windows Package (`2026-11-09`)**:
   * All changes in `Gran-Turismo-6-PC/gt6launcher/` (`paths.py`, `patches.py`, `gamepad.py`, `lan.py`, `rpcs3.py`, `core.py`, `ui.py`) were synced with `launcher/gt6launcher/`.
   * Rebuilt `GT6-Launcher-win64.zip` (`SHA-256: 886be94f1ed9e62d35b0489a797aecd9fac51f955385131fb586afe311a36362`, 98,079,924 bytes) using `packaging/build_windows_wine.sh` with the Patch-08 Windows RPCS3 build (`/tmp/gt6-patched-rpcs3-v112`).
   * Verified under Wine (`GT6-Launcher.exe add-game` + `GT6-Launcher.exe prepare` + `rpcs3.exe --no-gui` on `BCES01893` `01.22`); `data/rpcs3/log/RPCS3.log` confirmed:
     * `GUI: Finished reading config database from file: .../data/rpcs3//GuiConfigs/config_database.dat`
     * `SYS: Applying custom config: .../data/rpcs3/config/custom_configs/config_BCES01893.yml` (`Write Color Buffers: true`, `Read Color Buffers: true`, `Handle RSX Memory Tiling: true`)
     * `PAT: Loading patch config file .../data/rpcs3/config/patch_config.yml` (with the 7 default patches enabled: `Use Sharper MLAA`, `Unlock FPS`, `Sharper Shadows`, `Bloom/Glare Resolution Scale Fix`, `Auto Exposure Resolution Scale Fix`, `Smoke and Dust Resolution Scale Fix`, `Movie Playback Fix`).
   * Note on the **Patches** tab UI (`ui.py:_fill_patch_list`): the tab only populates after a GT6 disc image (`.iso`) is added in Setup **and** game updates (`01.22` or `01.05`) are installed, because `patch.yml` and `imported_patch.yml` are keyed by disc serial and have 0 patches for unpatched `01.00`.
   * Saved the rebuilt ZIP to:
     * `/home/martin/Downloads/gran turismo 6/Gran-Turismo-6-PC/dist/GT6-Launcher-win64.zip`
     * `/home/martin/Desktop/testt/4e2888a8ba00ca497fbba25057424158-d03f6ec4bfaae1018320199ce89882ea8f10fb6b/GT6-Launcher-win64.zip`
     * `/home/martin/GT6-Launcher-win64.zip`
   * Uploaded to Gist `https://gist.github.com/Mabec-games/4e2888a8ba00ca497fbba25057424158` at revision `ceefb9c36e72ce2551f722ed8eb8888650bb16d2` (`2026-11-09T14:38:39Z`).
5. **v1.1.3 Release (`2026-11-09`)**:
   * Confirmed on Issue #8 (`Fantomas3228`): *"Flickering is gone in this one! And controller is also working! Great job! And also it is not going to disk C now, so every issue is fixed here."*
   * Bumped version to `1.1.3` in `gt6launcher/__init__.py` and `README.md`.
   * Built both `dist/GT6-Launcher-win64.zip` and `dist/GT6-Launcher-x86_64.AppImage` for `v1.1.3`.
