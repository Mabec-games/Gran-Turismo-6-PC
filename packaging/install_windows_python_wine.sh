#!/usr/bin/env bash
# Install the Windows CPython runtime needed by build_windows.ps1 into an isolated
# Wine prefix. PyInstaller and the Python package dependencies are installed later
# by build_windows.ps1 into its own build virtual environment.
set -euo pipefail

PYTHON_VERSION="3.12.10"
PYTHON_EXE="python-${PYTHON_VERSION}-amd64.exe"
PYTHON_URL="https://www.python.org/ftp/python/${PYTHON_VERSION}/${PYTHON_EXE}"
PYTHON_SHA256="67b5635e80ea51072b87941312d00ec8927c4db9ba18938f7ad2d27b328b95fb"
INSTALL_DIR="${TMPDIR:-/tmp}/gt6-python-wine"
WINEPREFIX="${GT6_WINEPREFIX:-${TMPDIR:-/tmp}/gt6-winbuild-prefix}"
INSTALLER="${INSTALL_DIR}/${PYTHON_EXE}"

die() { printf 'error: %s\n' "$*" >&2; exit 1; }

command -v wine >/dev/null || die "Wine was not found on PATH."
command -v wineboot >/dev/null || die "wineboot was not found on PATH."
mkdir -p "$INSTALL_DIR" "$WINEPREFIX"

if [[ ! -f "$INSTALLER" ]]; then
    if command -v curl >/dev/null; then
        curl --fail --location --retry 3 --output "$INSTALLER.part" "$PYTHON_URL"
    elif command -v wget >/dev/null; then
        wget --tries=3 --output-document="$INSTALLER.part" "$PYTHON_URL"
    elif command -v python3 >/dev/null; then
        python3 -c 'import sys, urllib.request; urllib.request.urlretrieve(sys.argv[1], sys.argv[2])' \
            "$PYTHON_URL" "$INSTALLER.part"
    else
        die "Need curl, wget, or python3 to download the official Python installer."
    fi
    mv "$INSTALLER.part" "$INSTALLER"
fi

if command -v sha256sum >/dev/null; then
    ACTUAL_SHA256="$(sha256sum "$INSTALLER" | cut -d ' ' -f 1)"
elif command -v sha256 >/dev/null; then
    ACTUAL_SHA256="$(sha256 -q "$INSTALLER")"
else
    ACTUAL_SHA256="$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$INSTALLER")"
fi
[[ "${ACTUAL_SHA256,,}" == "$PYTHON_SHA256" ]] || die "Python installer SHA-256 mismatch."

if [[ ! -f "$WINEPREFIX/system.reg" ]]; then
    WINEPREFIX="$WINEPREFIX" WINEARCH=win64 wineboot --init
else
    WINEPREFIX="$WINEPREFIX" wineboot --init
fi

WINEPREFIX="$WINEPREFIX" wine "$INSTALLER" /quiet InstallAllUsers=0 \
    'TargetDir=C:\Python312' PrependPath=1 Include_pip=1 Include_test=0

WINEPREFIX="$WINEPREFIX" wine cmd /c 'C:\Python312\python.exe --version'
WINEPREFIX="$WINEPREFIX" wine cmd /c 'C:\Python312\python.exe -m pip --version'
if ! WINEPREFIX="$WINEPREFIX" wine cmd /c 'python --version'; then
    printf 'Python installed, but the Wine command PATH did not refresh. Use C:\\Python312\\python.exe or reopen the Wine shell.\n' >&2
fi

printf '\nWindows Python is installed in Wine prefix:\n  %s\n' "$WINEPREFIX"
printf 'Wine prefix for subsequent build commands: WINEPREFIX=%q\n' "$WINEPREFIX"
printf 'PyInstaller will be installed automatically by packaging/build_windows.ps1.\n'
