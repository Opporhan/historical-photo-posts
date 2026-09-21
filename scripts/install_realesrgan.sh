#!/usr/bin/env bash
# Downloads the Real-ESRGAN ncnn-vulkan binary (BSD-3-Clause) with its models into tools/realesrgan/.
# Supports macOS, Linux and (via Git Bash) Windows release archives from xinntao/Real-ESRGAN.
set -euo pipefail

VERSION="v0.2.5.0"
STAMP="20220424"
case "$(uname -s)" in
  Darwin) OS="macos" ;;
  Linux)  OS="ubuntu" ;;
  MINGW*|MSYS*|CYGWIN*) OS="windows" ;;
  *) echo "Unsupported OS: $(uname -s)" >&2; exit 1 ;;
esac

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/tools/realesrgan"
BIN="$DEST/realesrgan-ncnn-vulkan"
[ "$OS" = "windows" ] && BIN="$BIN.exe"

if [ -x "$BIN" ] && [ -f "$DEST/models/realesrgan-x4plus.bin" ]; then
  echo "Real-ESRGAN already installed at $DEST"
  exit 0
fi

URL="https://github.com/xinntao/Real-ESRGAN/releases/download/${VERSION}/realesrgan-ncnn-vulkan-${STAMP}-${OS}.zip"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
echo "Downloading $URL"
curl -fL --retry 3 -o "$TMP/r.zip" "$URL"
mkdir -p "$DEST"
unzip -q -o "$TMP/r.zip" -d "$DEST"
chmod +x "$BIN"
[ "$OS" = "macos" ] && xattr -dr com.apple.quarantine "$DEST" 2>/dev/null || true
echo "Installed to $DEST"
