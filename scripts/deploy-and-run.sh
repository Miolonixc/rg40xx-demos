#!/bin/bash
# Deploy and run demos on RG40XX H (Knulli OS)
#
# Usage:
#   scripts/deploy-and-run.sh [binary-path|directory]
#
# Environment variables:
#   DEVICE_IP - RG40XX H IP (default: 192.168.2.173)
#   DEVICE_PASS - SSH password (default: linux)
#
# Examples:
#   scripts/deploy-and-run.sh build/knulli/bouncing-balls
#   scripts/deploy-and-run.sh build/knulli/*

set -e

DEVICE_IP="${DEVICE_IP:-192.168.2.173}"
DEVICE_PASS="${DEVICE_PASS:-linux}"

if [ -z "$1" ]; then
    echo "Usage: $0 [binary-path|directory]"
    echo ""
    echo "Environment:"
    echo "  DEVICE_IP - RG40XX H IP (default: 192.168.2.173)"
    echo "  DEVICE_PASS - SSH password (default: linux)"
    exit 1
fi

# Find binaries
BINARIES=()
if [ -d "$1" ]; then
    for f in "$1"/*; do
        [ -f "$f" ] && [ -x "$f" ] && BINARIES+=("$f")
    done
else
    BINARIES+=("$1")
fi

if [ ${#BINARIES[@]} -eq 0 ]; then
    echo "No binaries found in $1"
    exit 1
fi

echo "=== Deploying to $DEVICE_IP ==="

# Deploy all binaries
for bin in "${BINARIES[@]}"; do
    name="$(basename "$bin")"
    echo "[*] Deploying $name..."
    sshpass -p "$DEVICE_PASS" scp -o StrictHostKeyChecking=no "$bin" "root@$DEVICE_IP:/tmp/$name"
done

echo ""
echo "=== Running demos ==="
echo "Press Ctrl+C to stop and restart EmulationStation"
echo ""

# Stop EmulationStation
sshpass -p "$DEVICE_PASS" ssh -o StrictHostKeyChecking=no "root@$DEVICE_IP" 'killall -9 emulationstation 2>/dev/null; sleep 1'

# Run each demo for 10 seconds
for bin in "${BINARIES[@]}"; do
    name="$(basename "$bin")"
    echo "--- Running $name (10s) ---"
    sshpass -p "$DEVICE_PASS" ssh -o StrictHostKeyChecking=no "root@$DEVICE_IP" \
        "export SDL_VIDEODRIVER=FBCON; timeout 10 /tmp/$name; true" 2>&1 || true
    echo ""
done

# Restart EmulationStation
echo "=== Restarting EmulationStation ==="
sshpass -p "$DEVICE_PASS" ssh -o StrictHostKeyChecking=no "root@$DEVICE_IP" \
    '/etc/init.d/S31emulationstation start 2>&1' || true

echo "=== Done ==="
