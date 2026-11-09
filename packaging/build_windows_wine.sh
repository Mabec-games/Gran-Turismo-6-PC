#!/usr/bin/env bash
# Build the Windows launcher from CachyOS using Windows Python under Wine.
# This avoids Wine's stub PowerShell implementation; downloads and archives use
# native curl/7z while PyInstaller runs with the Windows interpreter.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
WINEPREFIX="${GT6_WINEPREFIX:-/tmp/gt6-winbuild-prefix}"
PYTHON_EXE='C:\Python312\python.exe'
WORK="$(mktemp -d "${TMPDIR:-/tmp}/gt6-build-win-${UID}.XXXXXX")"
DIST="$ROOT/dist"
ZIP="$DIST/GT6-Launcher-win64.zip"
SDL_VERSION="3.4.18"
RPCS3_URL="https://github.com/RPCS3/rpcs3-binaries-win/releases/download/build-eee3f0f7c285f2b8aa18fec278a2146c5cd874eb/rpcs3-v0.0.43-20565-eee3f0f7_win64_msvc.7z"
RPCS3_SHA256="FDEC321625C856DCF2D84EDA128F75F24A428230A233F1B2BF12C490882870E7"

die() { printf 'error: %s\n' "$*" >&2; exit 1; }
download() {
    local url="$1" out="$2"
    if command -v curl >/dev/null; then
        curl --fail --location --retry 3 --output "$out" "$url"
    elif command -v wget >/dev/null; then
        wget --tries=3 --output-document="$out" "$url"
    else
        die "Need curl or wget to download Windows build dependencies."
    fi
}

for tool in wine winepath 7z; do
    command -v "$tool" >/dev/null || die "Required host tool '$tool' is missing."
done
[[ -x "$WINEPREFIX/drive_c/Python312/python.exe" ]] || die "Windows Python missing in $WINEPREFIX; run install_windows_python_wine.sh first."

mkdir -p "$DIST"
WIN_ROOT="$(winepath -w "$ROOT")"
WIN_WORK="$(winepath -w "$WORK")"
if [[ -n "${GT6_WIN_VENV:-}" && -f "${GT6_WIN_VENV}/Scripts/python.exe" ]]; then
    printf 'Using cached Windows virtual environment: %s\n' "$GT6_WIN_VENV"
    WIN_VENV="$(winepath -w "$GT6_WIN_VENV")"
    WIN_PY="$WIN_VENV\\Scripts\\python.exe"
else
    WIN_VENV="$WIN_WORK\\venv"
    WIN_PY="$WIN_VENV\\Scripts\\python.exe"
    printf 'Creating Windows virtual environment under Wine...\n'
    WINEPREFIX="$WINEPREFIX" wine "$PYTHON_EXE" -m venv "$WIN_VENV"
    WINEPREFIX="$WINEPREFIX" wine "$WIN_PY" -m pip install --upgrade pip
    WINEPREFIX="$WINEPREFIX" wine "$WIN_PY" -m pip install PySide6-Essentials pyinstaller pyyaml pillow
fi
WIN_ENTRY="$WIN_WORK\\entry.py"
WIN_ICON="$WIN_WORK\\gt6-launcher.ico"

cat > "$WORK/entry.py" <<'PY'
import sys
from gt6launcher.__main__ import main
sys.exit(main())
PY

printf 'Creating Windows icon...\n'
WIN_ICON_PNG="$(winepath -w "$ROOT/gt6launcher/data/img/icon.png")"
WINEPREFIX="$WINEPREFIX" wine "$WIN_PY" -c \
    'from PIL import Image; import sys; Image.open(sys.argv[1]).save(sys.argv[2], sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])' \
    "$WIN_ICON_PNG" "$WIN_ICON"

if [[ -n "${GT6_SDL3_DLL:-}" && -f "${GT6_SDL3_DLL}" ]]; then
    printf 'Using cached SDL3.dll: %s\n' "$GT6_SDL3_DLL"
    SDL_DLL="$GT6_SDL3_DLL"
else
    printf 'Downloading SDL3...\n'
    SDL_ZIP="$WORK/sdl3.zip"
    download "https://github.com/libsdl-org/SDL/releases/download/release-${SDL_VERSION}/SDL3-${SDL_VERSION}-win32-x64.zip" "$SDL_ZIP"
    mkdir -p "$WORK/sdl3"
    7z x -y "-o$WORK/sdl3" "$SDL_ZIP" >/dev/null
    SDL_DLL="$(find "$WORK/sdl3" -type f -iname SDL3.dll -print -quit)"
fi
[[ -n "$SDL_DLL" ]] || die "SDL3.dll was not found."
WIN_SDL_DLL="$(winepath -w "$SDL_DLL")"

printf 'Downloading and unpacking RPCS3...\n'
RPCS3_DIR="$WORK/rpcs3"
PATCHED_RPCS3_DIR="${GT6L_BUNDLE_RPCS3_DIR:-}"
if [[ -n "$PATCHED_RPCS3_DIR" ]]; then
    [[ -f "$PATCHED_RPCS3_DIR/rpcs3.exe" ]] || die "GT6L_BUNDLE_RPCS3_DIR must contain rpcs3.exe at its root."
    mkdir -p "$RPCS3_DIR"
    cp -a "$PATCHED_RPCS3_DIR/." "$RPCS3_DIR/"
else
    RPCS3_ARCHIVE="$WORK/rpcs3.7z"
    download "$RPCS3_URL" "$RPCS3_ARCHIVE"
    if command -v sha256sum >/dev/null; then
        ACTUAL_RPCS3_SHA="$(sha256sum "$RPCS3_ARCHIVE" | cut -d ' ' -f 1)"
    else
        ACTUAL_RPCS3_SHA="$(7z h -scrcSHA256 "$RPCS3_ARCHIVE" | awk '/^SHA256 for data:/ {print tolower($4)}')"
    fi
    [[ "${ACTUAL_RPCS3_SHA,,}" == "${RPCS3_SHA256,,}" ]] || die "RPCS3 archive SHA-256 mismatch."
    mkdir -p "$RPCS3_DIR"
    7z x -y "-o$RPCS3_DIR" "$RPCS3_ARCHIVE" >/dev/null
fi
[[ -f "$RPCS3_DIR/rpcs3.exe" ]] || die "rpcs3.exe missing after extraction."

printf 'Running PyInstaller under Wine...\n'
WIN_DIST="$WIN_WORK\\pyi"
WIN_PYI_WORK="$WIN_WORK\\pyi-work"
WIN_SPEC="$WIN_WORK"
WIN_DATA="$WIN_ROOT\\gt6launcher\\data;gt6launcher\\data"
WIN_ENTRY="$(winepath -w "$WORK/entry.py")"
WIN_ICO="$(winepath -w "$WORK/gt6-launcher.ico")"
WIN_SDL_DLL="$(winepath -w "$SDL_DLL")"

WINEPREFIX="$WINEPREFIX" wine "$WIN_PY" -m PyInstaller \
    --noconfirm --clean --onedir --windowed --name GT6-Launcher \
    --icon "$WIN_ICO" --paths "$WIN_ROOT" \
    --add-data "$WIN_DATA" --exclude-module tkinter \
    --add-binary "$WIN_SDL_DLL;." \
    --distpath "$WIN_DIST" --workpath "$WIN_PYI_WORK" \
    --specpath "$WIN_SPEC" "$WIN_ENTRY"

APP="$WORK/pyi/GT6-Launcher"
[[ -f "$APP/GT6-Launcher.exe" ]] || die "PyInstaller did not produce GT6-Launcher.exe."
cp -a "$RPCS3_DIR" "$APP/rpcs3"
if [[ -n "$PATCHED_RPCS3_DIR" && ! -f "$APP/rpcs3/GT6-PATCHED.txt" ]]; then
    printf 'GT6-patched RPCS3 build %s from emulator/gt6-patches\n' '0.0.43-20565 (eee3f0f7)' \
        > "$APP/rpcs3/GT6-PATCHED.txt"
fi

rm -f "$ZIP"
(cd "$WORK/pyi" && 7z a -tzip "$ZIP" GT6-Launcher >/dev/null)
printf '\nWindows build saved locally: %s\n' "$ZIP"
