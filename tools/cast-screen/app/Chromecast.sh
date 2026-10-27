#!/bin/bash
# Chromecast app launcher for the Knulli Tools section (same setup as the Battery app).
ES_PID=$(pidof emulationstation)
[ -n "$ES_PID" ] && kill -STOP "$ES_PID"

cleanup() {
    [ -n "$WATCHER_PID" ] && kill "$WATCHER_PID" 2>/dev/null
    [ -n "$APP_PID" ] && kill "$APP_PID" 2>/dev/null
    ES_PID=$(pidof emulationstation)
    [ -n "$ES_PID" ] && kill -CONT "$ES_PID" 2>/dev/null
    printf "\033c" >/dev/tty0 2>/dev/null
}
trap cleanup EXIT INT TERM

export XDG_RUNTIME_DIR=/var/run
export SDL_VIDEODRIVER=mali
export SDL_AUDIODRIVER=dummy
export PYTHONUNBUFFERED=1
python3 /userdata/roms/tools/chromecast/cast_app.py >/tmp/cast_app.log 2>&1 &
APP_PID=$!
# The app quits on B, Start and Menu itself; the watcher is a fallback that kills the app
# (not this script, which would leave the app on screen) on Menu or Select+Start.
if [ -f /userdata/system/bin/port-exit-watcher.py ]; then
    python3 /userdata/system/bin/port-exit-watcher.py "$APP_PID" >/dev/null 2>&1 &
    WATCHER_PID=$!
fi
wait "$APP_PID"
APP_PID=
