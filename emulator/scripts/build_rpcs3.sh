#!/usr/bin/env bash
# Build the GT6-optimised RPCS3 AppImage.
#   upstream RPCS3 @ RPCS3_COMMIT + build/gt6-patches/*.diff
# Output: build/out/rpcs3-gt6-x86_64.AppImage
set -euo pipefail
B="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$B/rpcs3-src"
OBJ="$B/rpcs3-obj"
APPDIR="$B/rpcs3-appdir"
OUT="$B/out"
RPCS3_COMMIT="${RPCS3_COMMIT:-eee3f0f7c}"
JOBS="${JOBS:-$(nproc)}"

cd "$SRC"
if [ "${SKIP_PATCH:-0}" != 1 ]; then
  # start from a pristine tree at the pinned commit, then apply our patches
  git checkout -q -- rpcs3 Utilities
  git checkout -q "$RPCS3_COMMIT"
  for p in "$B"/gt6-patches/*.diff; do
    echo ">> applying $(basename "$p")"
    git apply "$p"
  done
fi
SHORT=$(git rev-parse --short=8 HEAD)

cmake -S "$SRC" -B "$OBJ" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
  -DCMAKE_INSTALL_PREFIX=/usr \
  -DUSE_NATIVE_INSTRUCTIONS=OFF \
  -DUSE_LTO=OFF \
  -DUSE_SYSTEM_CURL=ON -DUSE_SYSTEM_SDL=ON -DUSE_SYSTEM_ZLIB=ON \
  -DUSE_DISCORD_RPC=OFF \
  -DVulkan_INCLUDE_DIR="$B/vulkan-headers/include" \
  -DVulkan_LIBRARY=/usr/lib/libvulkan.so
cmake --build "$OBJ" -j "$JOBS"

rm -rf "$APPDIR"
DESTDIR="$APPDIR" cmake --install "$OBJ"

mkdir -p "$OUT"
cd "$B"
export QMAKE="$B/tools/qmake-filtered"
export EXTRA_QT_PLUGINS="svg;"
export EXTRA_PLATFORM_PLUGINS="libqwayland.so;"
export NO_STRIP=1
export LDAI_OUTPUT="$OUT/rpcs3-gt6-x86_64.AppImage"
DESKTOP=$(find "$APPDIR/usr/share/applications" -name '*.desktop' | head -1)
ICON=$(find "$APPDIR/usr/share/icons" -name 'rpcs3.svg' -o -name 'rpcs3.png' | head -1)
APPIMAGE_EXTRACT_AND_RUN=1 "$B/tools/linuxdeploy-x86_64.AppImage" --appdir "$APPDIR" \
  --executable "$APPDIR/usr/bin/rpcs3" -d "$DESKTOP" -i "$ICON" --plugin qt

# Qt's FFmpeg multimedia backend + the system libav* it drags in segfault RPCS3's
# main thread when the Qt music handler starts (RPCS3 links its own FFmpeg).
# GT6 doesn't need the music handler, so ship without that backend.
rm -f "$APPDIR"/usr/plugins/multimedia/libffmpegmediaplugin.so
for l in libavcodec libavformat libavutil libswresample libswscale libdav1d librav1e libSvtAv1Enc libdvdnav libdvdread; do
  rm -f "$APPDIR"/usr/lib/$l.so*
done
# make sure nothing left still needs them
if ldd "$APPDIR"/usr/bin/rpcs3 "$APPDIR"/usr/plugins/*/*.so 2>/dev/null | grep -q "not found"; then
  ldd "$APPDIR"/usr/bin/rpcs3 "$APPDIR"/usr/plugins/*/*.so | grep -B5 "not found" | head -20
  echo "!! unresolved libraries after pruning"; exit 1
fi
# linuxdeploy leaves AppRun as a bare symlink to the binary, so the Qt plugin
# hook never runs and Qt intermittently fails to load its platform plugin
# (qFatal in QGuiApplicationPrivate::createPlatformIntegration). Use a wrapper.
rm -f "$APPDIR/AppRun"
cat > "$APPDIR/AppRun" <<'EOS'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
export APPDIR="${APPDIR:-$HERE}"
export QT_PLUGIN_PATH="$HERE/usr/plugins"
export QT_QPA_PLATFORM_PLUGIN_PATH="$HERE/usr/plugins/platforms"
exec "$HERE/usr/bin/rpcs3" "$@"
EOS
chmod 755 "$APPDIR/AppRun"
rm -f "$LDAI_OUTPUT"
APPIMAGE_EXTRACT_AND_RUN=1 ARCH=x86_64 "$B/tools/appimagetool-x86_64.AppImage" -n "$APPDIR" "$LDAI_OUTPUT"
echo "gt6-$SHORT" > "$OUT/rpcs3-gt6.version"
echo ">> built $LDAI_OUTPUT (gt6-$SHORT)"
