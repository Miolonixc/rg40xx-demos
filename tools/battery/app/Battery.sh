#!/bin/bash
# Battery app launcher for the Knulli Tools section (same setup as the Ports Manager tool).
ES_PID=$(pidof emulationstation)
[ -n "$ES_PID" ] && kill -STOP "$ES_PID"

if [ -f /userdata/system/bin/port-exit-watcher.py ]; then
    python3 /userdata/system/bin/port-exit-watcher.py "$$" >/dev/null 2>&1 &
    WATCHER_PID=$!
fi

cleanup() {
    [ -n "$WATCHER_PID" ] && kill "$WATCHER_PID" 2>/dev/null
    ES_PID=$(pidof emulationstation)
    [ -n "$ES_PID" ] && kill -CONT "$ES_PID" 2>/dev/null
    printf "\033c" >/dev/tty0 2>/dev/null
}
trap cleanup EXIT INT TERM

export XDG_RUNTIME_DIR=/var/run
export SDL_VIDEODRIVER=mali
export SDL_AUDIODRIVER=dummy
export PYTHONUNBUFFERED=1
python3 /userdata/roms/tools/battery/battery_app.py >/tmp/battery_app.log 2>&1
