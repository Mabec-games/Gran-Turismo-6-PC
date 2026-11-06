#!/usr/bin/env bash
# Create a "gt6" branch of RPCS3 = upstream commit + build/gt6-patches, ready to
# push to YOUR fork. RPCS3's own .github/workflows/rpcs3.yml then builds a
# portable Linux AppImage (Ubuntu 22.04 container) and a Windows .7z when you
# run it manually (Actions tab > "Build RPCS3" > Run workflow > branch gt6).
#
#   ./make_gt6_branch.sh                      # prepare branch locally
#   git -C ../rpcs3-ci push <your-fork-remote> gt6
#   gh workflow run rpcs3.yml --repo <you>/rpcs3 --ref gt6
#   gh run download --repo <you>/rpcs3 -n "RPCS3 for Windows (MSVC)"
set -euo pipefail
B="$(cd "$(dirname "$0")/.." && pwd)"
COMMIT="${RPCS3_COMMIT:-eee3f0f7c}"
DST="$B/rpcs3-ci"
[ -d "$DST/.git" ] || git clone -q "$B/rpcs3-src" "$DST"
cd "$DST"
git fetch -q "$B/rpcs3-src" "$COMMIT"
git checkout -q -B gt6 "$COMMIT"
for p in "$B"/gt6-patches/*.diff; do git apply --index "$p"; done
git -c user.name="GT6 Launcher" -c user.email="gt6-launcher@localhost" commit -q -m "GT6 build: rt-reload race, blit reprotect, vdec skip crash, savestate fixes, USER_COMMAND legacy mode

Patches: $(cd "$B/gt6-patches" && ls *.diff | tr '\n' ' ')"
git log --oneline -2
echo "Branch 'gt6' ready in $DST"
