#!/bin/bash
# Install NXEngine (Cave Story) on RG40XX H
# Requires: Cave Story data files (Doukutsu.exe or extracted)

set -e
CDIR="$HOME/games/cavestory"
mkdir -p "$CDIR"

echo "=== Cave Story (NXEngine) Installer ==="
echo ""

# Check for data files
if [ ! -f "$CDIR/Doukutsu.exe" ] && [ ! -d "$CDIR/data" ]; then
    echo "[!] Missing Cave Story data files!"
    echo "    Place Doukutsu.exe in: $CDIR/"
    echo "    Or extract Cave Story data to: $CDIR/data/"
    echo ""
    echo "    You can get Cave Story for free from:"
    echo "      https://www.cavestory.org/download/cave-story.php"
    echo ""
    echo "    Extract the .exe with unzip/7z, or use the freeware installer."
    exit 1
fi

echo "[*] Found Cave Story data"

# Install NXEngine
if ! command -v nxengine &>/dev/null; then
    echo "[*] Installing NXEngine..."
    sudo apt-get update
    sudo apt-get install -y nxengine
fi

echo ""
echo "=== Ready to play ==="
echo "Run: nxengine $CDIR"
echo ""
echo "Controls:"
echo "  Arrow keys / Left stick = Move"
echo "  Z / A button = Jump"
echo "  X / X button = Shoot"
echo "  C / Y button = Switch weapon"
echo "  Q / L1 = Previous weapon"
echo "  E / R1 = Next weapon"
echo "  Enter / Start = Menu"
echo ""
echo "Performance on RG40XX H:"
echo "  - 2D game, runs at 60 FPS easily"
echo "  - Perfect for this hardware"
