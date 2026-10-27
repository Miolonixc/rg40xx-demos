#!/bin/bash
# Install or update the YouTube app on the RG40XX H over SSH (key-based root login).
#   tools/youtube/install.sh [DEVICE_IP]
# Keeps downloads, history, thumbnails and font.ttf; prepares yt-dlp so the first start is fast.
set -euo pipefail
DEVICE_IP=${1:-${DEVICE_IP:-192.168.2.173}}
HERE=$(cd "$(dirname "$0")" && pwd)
TARGET=root@$DEVICE_IP

COPYFILE_DISABLE=1 tar --no-xattrs -C "$HERE" -cf - youtube_app.py YouTube.sh | ssh "$TARGET" 'set -e
APP=/userdata/roms/ports/YouTube
STAGE=$(mktemp -d)
tar -C "$STAGE" -xf -
mkdir -p "$APP"
install -m 755 "$STAGE/youtube_app.py" "$APP/youtube_app.py"
install -m 755 "$STAGE/YouTube.sh" /userdata/roms/ports/YouTube.sh
rm -rf "$STAGE" "$APP/__pycache__" "$APP/mpv_input.conf"
[ -f "$APP/font.ttf" ] || cp /usr/share/fonts/dejavu/DejaVuSans.ttf "$APP/font.ttf"
cd "$APP" && python3 youtube_app.py --prepare
# EmulationStation keeps gamelists in memory and writes them back when it reloads, so let it
# save first, edit the file, then reload again. Skipped while a game runs.
if curl -s -m 5 http://127.0.0.1:1234/runningGame | grep -q "NO GAME RUNNING"; then
    reload_es() { curl -s -m 30 http://127.0.0.1:1234/reloadgames >/dev/null 2>&1 || true; }
    reload_es
    python3 - <<"PY"
import re
from pathlib import Path
path = Path("/userdata/roms/ports/gamelist.xml")
desc = ("YouTube без рекламы: подборки по темам, поиск с экранной клавиатурой, история с "
        "продолжением просмотра, пропуск спонсорских вставок (SponsorBlock), скачивание "
        "видео (360p) и звука для просмотра без сети. Start - меню, обновление yt-dlp.")
old = text = path.read_text(encoding="utf-8")
# An earlier installer left <name>/<image>/<desc> outside any <game>; drop that fragment.
text = re.sub(r"(</game>)\s*<name>YouTube \(No Ads\)</name>\s*<image>[^<]*</image>\s*"
              r"<desc>[^<]*</desc>", r"\1", text)
game = re.search(r"<game>(?:(?!</game>).)*?<path>\./YouTube\.sh</path>.*?</game>", text, re.S)
if game:
    block = game.group(0)
    if "<desc>" in block:
        new = re.sub(r"<desc>.*?</desc>", lambda m: f"<desc>{desc}</desc>", block, flags=re.S)
    else:
        new = re.sub(r"(\s*)(<name>.*?</name>)", lambda m: f"{m.group(1)}{m.group(2)}{m.group(1)}<desc>{desc}</desc>",
                     block, count=1, flags=re.S)
    text = text.replace(block, new)
if text != old:
    path.write_text(text, encoding="utf-8")
    print("Updated the YouTube entry in the Ports gamelist")
PY
    reload_es
else
    echo "A game is running: gamelist left as is"
fi'
echo "Installed. YouTube is in Ports."
