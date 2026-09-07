#!/bin/bash
# Install build dependencies on RG40XX H
# Run this first before building demos

set -e

echo "=== Installing RG40XX H Demo Dependencies ==="
echo ""

# Update package list
sudo apt-get update

# Essential build tools
echo "[*] Installing build tools..."
sudo apt-get install -y \
    build-essential \
    gcc \
    g++ \
    make \
    pkg-config \
    git

# SDL2
echo "[*] Installing SDL2..."
sudo apt-get install -y \
    libsdl2-dev \
    libsdl2-gfx-dev

# Raylib
echo "[*] Installing Raylib..."
sudo apt-get install -y \
    libraylib-dev \
    libgl1-mesa-dev \
    libx11-dev \
    libxrandr-dev \
    libxi-dev \
    libxcursor-dev \
    libxinerama-dev

# For Quake/Doom ports
echo "[*] Installing game port dependencies..."
sudo apt-get install -y \
    libsdl2-mixer-dev \
    libsdl2-net-dev

echo ""
echo "=== Dependencies Installed ==="
echo "Now run: ./scripts/build-all.sh"
