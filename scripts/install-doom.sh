#!/bin/bash
# Install Chocolate Doom on RG40XX H
# Requires: doom.wad (or doom1.wad / freedoom1.wad)

set -e
DDIR="$HOME/games/doom"
mkdir -p "$DDIR"

echo "=== Chocolate Doom Installer ==="
echo ""

# Check for WAD
WAD_FOUND=""
for wad in "$DDIR/doom.wad" "$DDIR/doom1.wad" "$DDIR/freedoom1.wad"; do
    if [ -f "$wad" ]; then
        WAD_FOUND="$wad"
        break
    fi
done

if [ -z "$WAD_FOUND" ]; then
    echo "[!] Missing WAD file!"
    echo "    Place one of these in: $DDIR/"
    echo "      - doom.wad (Ultimate Doom)"
    echo "      - doom1.wad (Shareware, 10MB)"
    echo "      - freedoom1.wad (Free alternative)"
    echo ""
    echo "    FreeDoom download:"
    echo "      https://freedoom.github.io/download.html"
    exit 1
fi

echo "[*] Found WAD: $WAD_FOUND"

# Install Chocolate Doom
if ! command -v chocolate-doom &>/dev/null; then
    echo "[*] Installing Chocolate Doom..."
    sudo apt-get update
    sudo apt-get install -y chocolate-doom
fi

echo ""
echo "=== Ready to play ==="
echo "Run: chocolate-doom -iwad $WAD_FOUND"
echo ""
echo "Controls:"
echo "  Arrow keys / Left stick = Move"
echo "  Ctrl / A button = Fire"
echo "  Space / B button = Use"
echo "  Enter / Start = Menu"
echo ""
echo "Performance on RG40XX H:"
echo "  - Software renderer, ~30-45 FPS at 640x480"
echo "  - Very playable"
