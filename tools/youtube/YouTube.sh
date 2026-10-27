#!/bin/bash
# YouTube app launcher for the Knulli Ports section.
# SDL's mali (fbdev) driver is the one that works here, for the app and for mpv --vo=sdl.
export SDL_VIDEODRIVER=mali
export XDG_RUNTIME_DIR=/var/run
export PYTHONUNBUFFERED=1
cd /userdata/roms/ports/YouTube || exit 1
exec python3 youtube_app.py >/tmp/youtube.log 2>&1
