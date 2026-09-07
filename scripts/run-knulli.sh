#!/bin/bash
# Run demos on Knulli OS via SSH
# Usage: ssh root@<rg40xx-ip> 'bash -s' < scripts/run-knulli.sh

# Setup environment for Knulli OS
export SDL_VIDEODRIVER=KMSDRM
export SDL_RENDER_DRIVER=opengles2
export SDL_MOUSEDEV=/dev/input/event0
export SDL_JOYSTICKDEV=/dev/input/event1

# Create demo directory
DEMO_DIR="/tmp/rg40xx-demos"
mkdir -p "$DEMO_DIR"

# Download pre-compiled SDL2 demos (if not present)
if [ ! -f "$DEMO_DIR/bouncing-balls" ]; then
    echo "Downloading demos..."
    cd "$DEMO_DIR"
    wget -q "https://github.com/Miolonixc/rg40xx-demos/releases/latest/download/rg40xx-sdl-demos.tar.gz"
    tar xzf rg40xx-sdl-demos.tar.gz
    chmod +x bouncing-balls particles starfield
fi

# Menu
while true; do
    echo ""
    echo "=== RG40XX H Demos (Knulli OS) ==="
    echo "1) Bouncing Balls"
    echo "2) Particles"
    echo "3) Starfield"
    echo "0) Exit"
    read -p "Select: " choice
    
    case $choice in
        1) "$DEMO_DIR/bouncing-balls" ;;
        2) "$DEMO_DIR/particles" ;;
        3) "$DEMO_DIR/starfield" ;;
        0) break ;;
    esac
done
