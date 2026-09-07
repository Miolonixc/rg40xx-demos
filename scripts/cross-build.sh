#!/bin/bash
# Cross-build script for RG40XX H (Knulli OS)
# 
# Usage:
#   scripts/cross-build.sh [demo-name|all]
#
# Environment variables:
#   ZIG_BIN - path to zig binary (default: autodetect)
#   DEVICE_IP - RG40XX H IP (for auto-deploy)
#
# Examples:
#   scripts/cross-build.sh all
#   scripts/cross-build.sh bouncing-balls
#   scripts/cross-build.sh particles

set -e

# Detect zig
if [ -z "$ZIG_BIN" ]; then
    ZIG_BIN="/data/data/com.termux/files/usr/bin/zig"
    if [ ! -f "$ZIG_BIN" ]; then
        ZIG_BIN="$(which zig 2>/dev/null || true)"
    fi
fi

if [ ! -f "$ZIG_BIN" ]; then
    echo "ERROR: zig not found. Install with: pkg install zig"
    exit 1
fi

echo "=== Using zig: $ZIG_BIN ==="
$ZIG_BIN version

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="${REPO_DIR}/build/knulli"
SYSROOT="${REPO_DIR}/sysroot"

# Initialize sysroot (SDL2 headers + libs from device)
init_sysroot() {
    if [ -d "$SYSROOT/include/SDL2" ] && [ -f "$SYSROOT/lib/libSDL2.so" ]; then
        echo "=== Sysroot already initialized ==="
        return
    fi
    
    echo "=== Initializing sysroot ==="
    mkdir -p "$SYSROOT/include" "$SYSROOT/lib"
    
    # Download SDL2 headers
    if [ ! -f "$SYSROOT/include/SDL2/SDL.h" ]; then
        echo "[*] Downloading SDL2 headers..."
        cd /tmp
        curl -sL -o sdl2.tar.gz "https://github.com/libsdl-org/SDL/releases/download/release-2.32.8/SDL2-2.32.8.tar.gz"
        tar xzf sdl2.tar.gz
        mkdir -p "$SYSROOT/include/SDL2"
        cp SDL2-2.32.8/include/* "$SYSROOT/include/SDL2/"
        rm -rf SDL2-2.32.8 sdl2.tar.gz
    fi
    
    # Get SDL2_gfx header
    if [ ! -f "$SYSROOT/include/SDL2/SDL2_gfxPrimitives.h" ]; then
        echo "[*] Downloading SDL2_gfx header..."
        curl -sL "https://raw.githubusercontent.com/svn2github/SDL2_gfx/master/SDL2_gfxPrimitives.h" \
            -o "$SYSROOT/include/SDL2/SDL2_gfxPrimitives.h"
    fi
    
    # Get SDL2 libs from device
    if [ -n "$DEVICE_IP" ]; then
        echo "[*] Copying SDL2 libs from device $DEVICE_IP..."
        sshpass -p "linux" scp -o StrictHostKeyChecking=no \
            root@$DEVICE_IP:/usr/lib/libSDL2-2.0.so.0.3200.8 "$SYSROOT/lib/libSDL2.so"
        sshpass -p "linux" scp -o StrictHostKeyChecking=no \
            root@$DEVICE_IP:/usr/lib/libSDL2_gfx-1.0.so.0.0.2 "$SYSROOT/lib/libSDL2_gfx.so"
    else
        echo "[!] WARNING: DEVICE_IP not set. Place SDL2 libs manually in $SYSROOT/lib/"
        echo "    Then re-run."
        exit 1
    fi
    
    echo "=== Sysroot ready ==="
}

# Build a single demo
build_demo() {
    local src="$1"
    local name="$(basename "$src" .c)"
    local out="$BUILD_DIR/$name"
    
    echo "=== Building $name ==="
    mkdir -p "$BUILD_DIR"
    
    $ZIG_BIN cc -target aarch64-linux-gnu \
        -I"$SYSROOT/include" \
        -L"$SYSROOT/lib" \
        -lSDL2 -lSDL2_gfx -lm \
        -Wl,--allow-shlib-undefined \
        -O2 \
        -o "$out" "$src"
    
    echo "  -> $out"
}

# Main
cd "$REPO_DIR"

DEMO="${1:-all}"

if [ "$DEMO" = "all" ]; then
    init_sysroot
    echo ""
    echo "=== Building all SDL2 demos ==="
    for src in sdl-demos/*.c; do
        build_demo "$src"
    done
    echo ""
    echo "=== Build complete ==="
    echo "Binaries: $BUILD_DIR/"
    echo ""
    echo "To deploy, run:"
    echo "  scripts/deploy-and-run.sh $BUILD_DIR/*"
else
    init_sysroot
    if [ -f "sdl-demos/${DEMO}.c" ]; then
        build_demo "sdl-demos/${DEMO}.c"
    else
        echo "ERROR: sdl-demos/${DEMO}.c not found"
        exit 1
    fi
fi
