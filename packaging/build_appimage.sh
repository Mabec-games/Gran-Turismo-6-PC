#!/usr/bin/env bash
# Build GT6-Launcher-x86_64.AppImage
#
#   packaging/build_appimage.sh [path/to/rpcs3.AppImage]
#
# RPCS3 to bundle (first found): argument, $GT6L_BUNDLE_RPCS3,
# ../build/out/rpcs3-gt6-x86_64.AppImage (GT6-patched build), ../rpcs3*.appimage (stock).
# Needs: python3 venv in launcher/.venv (PySide6-Essentials, pyinstaller, pyyaml), linuxdeploy
# with the appimage output plugin.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"          # launcher/
PROJ="$(dirname "$HERE")"
OUT="$HERE/dist"
WORK="$HERE/build-appimage"
PY="${PY:-$HERE/.venv/bin/python}"

RPCS3="${1:-${GT6L_BUNDLE_RPCS3:-}}"
if [[ -z "$RPCS3" ]]; then
  # the patched build is only used once build/ marked it boot-tested (<file>.ready)
  P="$PROJ/build/out/rpcs3-gt6-x86_64.AppImage"
  [[ -f "$P" && -f "$P.ready" ]] && RPCS3="$P"
  if [[ -z "$RPCS3" ]]; then
    for c in "$PROJ"/rpcs3*.AppImage "$PROJ"/rpcs3*.appimage; do
      [[ -f "$c" ]] && { RPCS3="$c"; break; }
    done
  fi
fi
[[ -f "$RPCS3" ]] || { echo "no RPCS3 AppImage to bundle"; exit 1; }
echo "bundling RPCS3: $RPCS3"

SDL3_SO="${GT6L_LIBSDL3:-}"
if [[ -z "$SDL3_SO" ]]; then
  for cand in /usr/lib/libSDL3.so.0 /usr/lib/x86_64-linux-gnu/libSDL3.so.0 /usr/lib64/libSDL3.so.0; do
    [[ -f "$cand" ]] && { SDL3_SO="$cand"; break; }
  done
fi

rm -rf "$WORK" && mkdir -p "$WORK" "$OUT"
cd "$WORK"
cat > entry.py <<'EOF'
import sys
from gt6launcher.__main__ import main
sys.exit(main())
EOF
"$PY" -m PyInstaller --noconfirm --clean --onedir --name gt6-launcher \
  --paths "$HERE" \
  --add-data "$HERE/gt6launcher/data:gt6launcher/data" \
  $( [[ -n "$SDL3_SO" && -f "$SDL3_SO" ]] && echo --add-binary "$SDL3_SO:." ) \
  --exclude-module tkinter --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.Qt3DCore \
  --distpath "$WORK/pyi" --workpath "$WORK/pyi-work" --specpath "$WORK" entry.py

# Never ship an older C++ runtime or low-level display/DRM client lib: on newer distros
# (Ubuntu 24.04/26.04, Fedora, Arch), host Mesa/Wayland/SDL2 libs loaded into the process
# require the host's newer GLIBCXX / Wayland symbols.
rm -f "$WORK/pyi/gt6-launcher/_internal"/libstdc++.so* \
      "$WORK/pyi/gt6-launcher/_internal"/libgcc_s.so* \
      "$WORK/pyi/gt6-launcher/_internal"/libwayland-client.so* \
      "$WORK/pyi/gt6-launcher/_internal"/libdrm.so* \
      "$WORK/pyi/gt6-launcher/_internal"/libGLX.so* \
      "$WORK/pyi/gt6-launcher/_internal"/libOpenGL.so* \
      "$WORK/pyi/gt6-launcher/_internal"/libEGL.so*

APPDIR="$WORK/AppDir"
mkdir -p "$APPDIR/usr/share/gt6-launcher/rpcs3" "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -a "$WORK/pyi/gt6-launcher" "$APPDIR/usr/share/gt6-launcher/app"
# keep the bundled emulator's file name: the launcher prefers names containing "gt6"
cp "$RPCS3" "$APPDIR/usr/share/gt6-launcher/rpcs3/$(basename "$RPCS3" | sed 's/\.appimage$/.AppImage/')"
chmod +x "$APPDIR"/usr/share/gt6-launcher/rpcs3/*.AppImage
cp "$HERE/gt6launcher/data/img/icon.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/gt6-launcher.png"
cat > "$APPDIR/usr/share/applications/gt6-launcher.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=GT6 Launcher
Comment=Gran Turismo 6 on RPCS3 - setup, updates, patches, mods and LAN
Exec=gt6-launcher
Icon=gt6-launcher
Categories=Game;Emulator;
Terminal=false
EOF
cat > "$WORK/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
export APPDIR="${APPDIR:-$HERE}"
exec "$HERE/usr/share/gt6-launcher/app/gt6-launcher" "$@"
EOF
chmod +x "$WORK/AppRun"

export ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1
export LDAI_OUTPUT="${LDAI_OUTPUT:-$OUT/GT6-Launcher-x86_64.AppImage}"
# No -e: the PyInstaller bundle already carries its libraries; linuxdeploy only packs.
linuxdeploy --appdir "$APPDIR" --custom-apprun "$WORK/AppRun" \
  -d "$APPDIR/usr/share/applications/gt6-launcher.desktop" \
  -i "$APPDIR/usr/share/icons/hicolor/256x256/apps/gt6-launcher.png" \
  --output appimage
ls -la "$OUT"
