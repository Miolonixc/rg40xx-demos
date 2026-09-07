#!/bin/bash
# Install TyrQuake (Quake 1 engine) on RG40XX H
# Requires: pak0.pak + pak1.pak from original Quake (or re-release)

set -e
QDIR="$HOME/games/quake"
mkdir -p "$QDIR/id1"

echo "=== TyrQuake Installer ==="
echo ""

# Check for pak files
if [ ! -f "$QDIR/id1/pak0.pak" ]; then
    echo "[!] Missing pak0.pak!"
    echo "    Place Quake PAK files in: $QDIR/id1/"
    echo "    You can extract them from:"
    echo "      - Steam/GOG Quake installation"
    echo "      - Quake 1.08 patch (linux quake-1.08.zip)"
    echo ""
    echo "    Expected files:"
    echo "      id1/pak0.pak (16MB)"
    echo "      id1/pak1.pak (23MB)"
    exit 1
fi

echo "[*] Found pak files"
ls -lh "$QDIR/id1/"

# Install TyrQuake
if ! command -v tyr-quake &>/dev/null; then
    echo "[*] Installing TyrQuake..."
    sudo apt-get update
    sudo apt-get install -y tyr-quake
fi

echo ""
echo "=== Ready to play ==="
echo "Run: tyr-quake -basedir $QDIR"
echo ""
echo "Controls (default):"
echo "  Arrow keys / Left stick = Move"
echo "  Z / A button = Fire"
echo "  Space / B button = Jump"
echo "  C / Y button = Use"
echo "  Esc / Start = Menu"
echo ""
echo "Performance on RG40XX H:"
echo "  - Software renderer works best (no Mali 3D acceleration in TyrQuake)"
echo "  - Expect ~20-30 FPS at 640x480"
