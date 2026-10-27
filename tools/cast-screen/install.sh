#!/bin/bash
# Install or update screen casting to a Chromecast on the RG40XX H over SSH (key-based root login).
#   tools/cast-screen/install.sh [DEVICE_IP] [CHROMECAST_NAME]
# Puts cast-screen into /userdata/system/bin and the Chromecast app into the Tools section.
# CHROMECAST_NAME (as shown by "cast-screen list") becomes the default device; the app changes it too.
set -euo pipefail
DEVICE_IP=${1:-${DEVICE_IP:-192.168.2.173}}
CHROMECAST=${2:-}
HERE=$(cd "$(dirname "$0")" && pwd)
TARGET=root@$DEVICE_IP

STATUS=0
COPYFILE_DISABLE=1 tar --no-xattrs -C "$HERE" -cf - cast-screen app | ssh "$TARGET" 'set -e
STAGE=$(mktemp -d)
tar -C "$STAGE" -xf -
# Stop a running cast with the version that started it.
/userdata/system/bin/cast-screen stop >/dev/null 2>&1 || true
install -m 755 "$STAGE/cast-screen" /userdata/system/bin/cast-screen
mkdir -p /userdata/roms/tools/chromecast /userdata/roms/tools/images
install -m 644 "$STAGE/app/cast_app.py" /userdata/roms/tools/chromecast/cast_app.py
install -m 755 "$STAGE/app/Chromecast.sh" /userdata/roms/tools/Chromecast.sh
rm -rf "$STAGE"
rm -f "/userdata/roms/tools/Cast start.sh" "/userdata/roms/tools/Cast stop.sh" /tmp/cast-screen.pid
python3 /userdata/roms/tools/chromecast/cast_app.py --icon /userdata/roms/tools/images/chromecast.png >/dev/null 2>&1 || true
# EmulationStation keeps gamelists in memory and writes them back when it reloads, so let it
# save first, edit the file, then reload again to show the new entry. Some game launchers pause
# EmulationStation; its copy would overwrite the edit later, so leave the gamelist alone then.
ES_PID=$(pidof emulationstation || true)
if [ -n "$ES_PID" ] && ps -o stat= -p "$ES_PID" | grep -q T; then
    /userdata/system/bin/cast-screen list
    exit 10
fi
reload_es() { curl -s -m 30 http://127.0.0.1:1234/reloadgames >/dev/null 2>&1 || true; }
reload_es
python3 - <<"PY"
import xml.etree.ElementTree as ET
from pathlib import Path
path = Path("/userdata/roms/tools/gamelist.xml")
tree = ET.parse(path) if path.exists() else ET.ElementTree(ET.Element("gameList"))
root = tree.getroot()
changed = False
for old in [g for g in root.findall("game") if g.findtext("path") in ("./Cast start.sh", "./Cast stop.sh")]:
    root.remove(old)
    changed = True
game = next((g for g in root.findall("game") if g.findtext("path") == "./Chromecast.sh"), None)
if game is None:
    game = ET.SubElement(root, "game")
fields = (("path", "./Chromecast.sh"), ("name", "Chromecast"),
          ("desc", "Casts the screen and sound to any Chromecast on the Wi-Fi network. Pick the TV in "
                   "the list; casting keeps running after the app is closed, so start a game and "
                   "play on the TV. Gamepad mode turns the handheld screen and speaker off while "
                   "casting. English or Russian, switched in the app."),
          ("image", "./images/chromecast.png"), ("developer", "rg40xx-demos"),
          ("genre", "System Tools"))
for tag, text in fields:
    node = game.find(tag)
    if node is None:
        node = ET.SubElement(game, tag)
    if node.text != text:
        node.text, changed = text, True
if changed:
    ET.indent(tree, "\t")
    tree.write(path, encoding="utf-8", xml_declaration=True)
    print("Updated Chromecast in the Tools gamelist")
PY
reload_es
/userdata/system/bin/cast-screen list' || STATUS=$?
[ "$STATUS" = 0 ] || [ "$STATUS" = 10 ] || exit "$STATUS"
if [ -n "$CHROMECAST" ]; then
    ssh "$TARGET" "/userdata/system/bin/cast-screen set device $(printf %q "$CHROMECAST")"
fi
if [ "$STATUS" = 10 ]; then
    echo "Installed, but EmulationStation is paused by a running game: run this again after the game to add Chromecast to Tools."
else
    echo "Installed. Chromecast is in Tools (EmulationStation gamelists were reloaded)."
fi
