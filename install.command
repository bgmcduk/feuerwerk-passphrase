#!/bin/bash
# Feuerwerk Passphrase — one-click installer for macOS.
#
# DOUBLE-CLICK this file in the Finder (or run it from Terminal). It will:
#   1. check that Python is present
#   2. install the two packages it needs, into a private folder
#   3. build a standalone Feuerwerk Passphrase.app
#   4. put the app in your Applications folder
#
# Nothing is installed system-wide, and your vault is never touched: it lives
# at ~/.config/feuerwerk-passphrase, exactly as on the other machines.

set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="Feuerwerk Passphrase"
VENV="$HOME/.feuerwerk-venv"
LOG="$HERE/install.log"

say() { printf '%s\n' "$*" | tee -a "$LOG"; }

: > "$LOG"
say "=== Feuerwerk Passphrase — installing for macOS ==="
say "    $(date)"

# ── 1. Python ────────────────────────────────────────────────────
PY=""
for c in python3 /usr/bin/python3 /usr/local/bin/python3 /opt/homebrew/bin/python3; do
  if command -v "$c" >/dev/null 2>&1; then
    if "$c" -c 'import tkinter' >/dev/null 2>&1; then PY="$c"; break; fi
    [ -z "$PY" ] && PY="$c"
  fi
done

if [ -z "$PY" ]; then
  say ""
  say "  Python 3 was not found."
  say ""
  say "  macOS ships Python 3 with the Command Line Tools. Install them with:"
  say "      xcode-select --install"
  say "  then run this file again."
  say ""
  read -r -p "  Press Return to close." _
  exit 1
fi
say "    python: $PY ($("$PY" --version 2>&1))"

if ! "$PY" -c 'import tkinter' >/dev/null 2>&1; then
  say ""
  say "  This Python has no tkinter, which the app needs for its window."
  say "  The Python that comes with the Command Line Tools includes it; a"
  say "  Homebrew python does not. Install the Command Line Tools with:"
  say "      xcode-select --install"
  say ""
  read -r -p "  Press Return to close." _
  exit 1
fi

# ── 2. A private place for the packages ──────────────────────────
say ""
say "=== 2. the packages it needs ==="
if [ ! -d "$VENV" ]; then
  say "    making $VENV"
  "$PY" -m venv "$VENV" >>"$LOG" 2>&1 || say "    (could not make the venv)"
fi
VPY="$VENV/bin/python"
if [ ! -x "$VPY" ]; then VPY="$PY"; fi

# cryptography is PINNED. The current release ships arm64-only wheels for
# macOS, so on an Intel Mac pip falls back to building it from Rust — and
# that needs a Rust toolchain and a reachable crates.io mirror, which is
# where the first version of this installer failed. 48.0.1 has a
# universal2 wheel, so it installs cleanly on either chip.
CRYPTO_VERSION="48.0.1"

"$VPY" -m pip install --quiet --upgrade pip >>"$LOG" 2>&1
say "    installing cryptography $CRYPTO_VERSION"
"$VPY" -m pip install --quiet "cryptography==$CRYPTO_VERSION" >>"$LOG" 2>&1

if ! "$VPY" -c 'import cryptography' >/dev/null 2>&1; then
  say ""
  say "  cryptography would not install. This is what happened the first time:"
  say "  the current release has no Intel wheel, so pip tried to build it"
  say "  from Rust and could not reach the crates.io mirror."
  say ""
  say "  The working app is already built and waiting for you at:"
  say "      https://downloads.beagmcd.net/FeuerwerkPassphrase-1.0.dmg"
  say ""
  say "  Or, if you have a working internet connection, try:"
  say "      $VPY -m pip install \"cryptography==$CRYPTO_VERSION\""
  say ""
  read -r -p "  Press Return to close." _
  exit 1
fi

if ! "$VPY" -c 'import PyInstaller' >/dev/null 2>&1; then
  say "    installing pyinstaller"
  "$VPY" -m pip install --quiet pyinstaller >>"$LOG" 2>&1
fi

"$VPY" -c 'import cryptography; print("    cryptography", cryptography.__version__)' 2>&1 | tee -a "$LOG"
if ! "$VPY" -c 'import PyInstaller' >/dev/null 2>&1; then
  say ""
  say "  PyInstaller would not install. The app still works if you run it with:"
  say "      $VPY \"$HERE/feuerwerk-passphrase.py\""
  say ""
  read -r -p "  Press Return to close." _
  exit 1
fi

# ── 3. Build the .app ───────────────────────────────────────────
say ""
say "=== 3. building $APP_NAME.app ==="
cd "$HERE" || exit 1
rm -rf build dist "$APP_NAME.spec"
"$VPY" -m PyInstaller --noconfirm --clean --windowed \
  --name "$APP_NAME" \
  --add-data "words.txt:." \
  --osx-bundle-identifier "org.bgmcd.feuerwerkpassphrase" \
  feuerwerk-passphrase.py >>"$LOG" 2>&1

if [ ! -d "dist/$APP_NAME.app" ]; then
  say ""
  say "  The build did not finish. The full log is at:"
  say "      $LOG"
  say ""
  read -r -p "  Press Return to close." _
  exit 1
fi
say "    built: dist/$APP_NAME.app"

# ── 4. Into Applications ─────────────────────────────────────────
say ""
say "=== 4. putting it in Applications ==="
if [ -d "/Applications" ] && [ -w "/Applications" ]; then
  rm -rf "/Applications/$APP_NAME.app"
  cp -R "dist/$APP_NAME.app" "/Applications/" && say "    copied to /Applications"
else
  say "    /Applications is not writable, so it is here instead:"
  say "        $HERE/dist/$APP_NAME.app"
fi

# ── 5. Unblock it ───────────────────────────────────────────────
# An app that was not signed is quarantined, and macOS then refuses to
# open it. Clearing the quarantine on our own build is safe.
xattr -dr com.apple.quarantine "dist/$APP_NAME.app" 2>/dev/null
[ -d "/Applications/$APP_NAME.app" ] && xattr -dr com.apple.quarantine "/Applications/$APP_NAME.app" 2>/dev/null

say ""
say "=== done ==="
say "    Open it from your Applications folder."
say ""
say "    Your vault lives at:"
say "        ~/.config/feuerwerk-passphrase"
say "    which is the same place as on the other machines, so a vault can"
say "    be carried between them with the Export and Import buttons."
say ""
say "    The web version, if you would rather use that:"
say "        https://feuerpass.beagmcd.net"
say ""
read -r -p "  Press Return to close." _
