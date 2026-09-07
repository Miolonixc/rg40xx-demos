#!/bin/bash
# Master build script for RG40XX H demos
# Run this ON the RG40XX H or with cross-compiler set up

set -e

DEMOS_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="${HOME}/rg40xx-demos"

echo "=== RG40XX H Demos Builder ==="
echo "Target: ${INSTALL_DIR}"
echo ""

# Detect platform
if [ "$(uname -m)" = "aarch64" ] || [ "$(uname -m)" = "armv7l" ]; then
    echo "[*] Building natively on ARM"
    CC="${CC:-gcc}"
    CXX="${CXX:-g++}"
else
    echo "[!] Cross-compilation not configured, attempting native build"
    CC="${CC:-gcc}"
    CXX="${CXX:-g++}"
fi

# Check for SDL2
if pkg-config --exists sdl2 2>/dev/null; then
    echo "[+] SDL2 found"
    SDL2_FLAGS="$(pkg-config --cflags --libs sdl2)"
else
    echo "[-] SDL2 not found via pkg-config, using defaults"
    SDL2_FLAGS="-lSDL2"
fi

# Check for raylib
if pkg-config --exists raylib 2>/dev/null; then
    echo "[+] Raylib found"
    RAYLIB_FLAGS="$(pkg-config --cflags --libs raylib)"
else
    echo "[-] Raylib not found via pkg-config, using defaults"
    RAYLIB_FLAGS="-lraylib -lGL -lm -lpthread -ldl -lrt -lX11"
fi

mkdir -p "${INSTALL_DIR}/bin"

# Build SDL2 demos
echo ""
echo "=== Building SDL2 Demos ==="
for src in "${DEMOS_DIR}"/sdl-demos/*.c; do
    name="$(basename "$src" .c)"
    echo "  Building ${name}..."
    $CC "$src" -o "${INSTALL_DIR}/bin/${name}" $SDL2_FLAGS -lm 2>/dev/null || \
    $CC "$src" -o "${INSTALL_DIR}/bin/${name}" -lSDL2 -lm
done

# Build raylib demos
echo ""
echo "=== Building Raylib Demos ==="
for src in "${DEMOS_DIR}"/raylib-demos/*.c; do
    name="$(basename "$src" .c)"
    echo "  Building ${name}..."
    $CC "$src" -o "${INSTALL_DIR}/bin/${name}" $RAYLIB_FLAGS -lm 2>/dev/null || \
    $CC "$src" -o "${INSTALL_DIR}/bin/${name}" -lraylib -lGL -lm -lpthread -ldl -lrt -lX11
done

# Make launcher script
cat > "${INSTALL_DIR}/launch.sh" << 'LAUNCHER'
#!/bin/bash
# RG40XX H Demos Launcher
DEMOS_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN_DIR="${DEMOS_DIR}/bin"

select_demo() {
    echo "=== RG40XX H Demos ==="
    echo ""
    i=1
    for f in "${BIN_DIR}"/*; do
        [ -x "$f" ] && echo "  $i) $(basename "$f")" && demos[$i]="$f" && ((i++))
    done
    echo "  0) Exit"
    echo ""
    read -p "Select: " choice
    if [ "$choice" = "0" ]; then exit 0; fi
    if [ -n "${demos[$choice]}" ]; then
        echo "Launching ${demos[$choice]}..."
        "${demos[$choice]}"
    fi
}

while true; do
    select_demo
done
LAUNCHER
chmod +x "${INSTALL_DIR}/launch.sh"

echo ""
echo "=== Build Complete ==="
echo "Binaries in: ${INSTALL_DIR}/bin/"
echo "Launch with: ${INSTALL_DIR}/launch.sh"
