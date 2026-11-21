#!/bin/bash
# build-dmg.sh — build the Feuerwerk Passphrase .app and a .dmg on macOS.
#
# Run this ON A MAC. It uses PyInstaller to make a standalone .app bundle, then
# wraps it in a disk image so it can be dragged into Applications.
#
# It needs a Python with PyInstaller:
#     pip3 install pyinstaller cryptography
#
# The result is a .dmg containing "Feuerwerk Passphrase.app". The vault is NOT
# inside it — the vault lives at ~/.config/feuerwerk-passphrase, so it is never
# copied around by accident.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="Feuerwerk Passphrase"
VERSION="1.0"

echo "=== 1. checking the tools ==="
command -v python3 >/dev/null || { echo "python3 is needed"; exit 1; }
python3 -c "import cryptography" 2>/dev/null || {
  echo "The 'cryptography' package is needed:"; echo "    pip3 install cryptography"; exit 1; }
python3 -m PyInstaller --version >/dev/null 2>&1 || {
  echo "PyInstaller is needed:"; echo "    pip3 install pyinstaller"; exit 1; }
echo "    python3:  $(python3 --version 2>&1)"
echo "    pyinstaller: $(python3 -m PyInstaller --version 2>&1)"

echo
echo "=== 2. building the .app ==="
cd "$HERE"
rm -rf build dist "$APP_NAME.spec"

# --windowed makes a proper .app with no terminal window.
# The words.txt must travel with it: the app reads it from the bundle.
python3 -m PyInstaller \
  --noconfirm --clean --windowed \
  --name "$APP_NAME" \
  --add-data "words.txt:." \
  --osx-bundle-identifier "org.bgmcd.feuerwerkpassphrase" \
  feuerwerk-passphrase.py

echo
echo "=== 3. making the disk image ==="
DMG="$HERE/$APP_NAME-$VERSION.dmg"
rm -f "$DMG"

# A tiny Automator-free approach: a folder with the app and a symlink to
# /Applications, which is what makes the drag-to-Applications window.
STAGE="$HERE/dmg-stage"
rm -rf "$STAGE" && mkdir -p "$STAGE"
cp -R "$HERE/dist/$APP_NAME.app" "$STAGE/"
ln -s /Applications "$STAGE/Applications"

hdiutil create \
  -volname "$APP_NAME" \
  -srcfolder "$STAGE" \
  -ov -format UDZO \
  "$DMG"

rm -rf "$STAGE"

echo
echo "=== done ==="
ls -la "$DMG"
echo
echo "The app is unsigned, so macOS will refuse to open it the first time."
echo "To allow it: right-click the app, Choose Open, then Open again."
echo "Or in Terminal:  xattr -dr com.apple.quarantine \"$DMG\""
