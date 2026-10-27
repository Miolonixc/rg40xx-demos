#!/bin/bash
# Install or update the battery tools on the RG40XX H over SSH (key-based root login).
#   tools/battery/install.sh [DEVICE_IP]
# Keeps an existing settings file; services are restarted to pick up new versions.
set -euo pipefail
DEVICE_IP=${1:-${DEVICE_IP:-192.168.2.173}}
HERE=$(cd "$(dirname "$0")" && pwd)
TARGET=root@$DEVICE_IP

COPYFILE_DISABLE=1 tar --no-xattrs -C "$HERE" -cf - battery-tools services app | ssh "$TARGET" 'set -e
STAGE=$(mktemp -d)
tar -C "$STAGE" -xf -
install -m 755 "$STAGE/battery-tools" /userdata/system/bin/battery-tools
for service in chargelimit lowbattery chargevibe; do
    install -m 755 "$STAGE/services/$service" /userdata/system/services/$service
done
mkdir -p /userdata/roms/tools/battery
install -m 644 "$STAGE/app/battery_app.py" /userdata/roms/tools/battery/battery_app.py
install -m 755 "$STAGE/app/Battery.sh" /userdata/roms/tools/Battery.sh
rm -rf "$STAGE"
[ -f /userdata/system/configs/battery-tools.conf ] || /userdata/system/bin/battery-tools range 40 60 >/dev/null
for service in chargelimit lowbattery chargevibe; do
    knulli-services enable $service >/dev/null 2>&1 || true
    /userdata/system/services/$service stop >/dev/null 2>&1 || true
    /userdata/system/services/$service start
done
mkdir -p /userdata/roms/tools/images
python3 /userdata/roms/tools/battery/battery_app.py --icon /userdata/roms/tools/images/battery.png >/dev/null 2>&1 || true
# EmulationStation keeps gamelists in memory and writes them back when it reloads, so let it
# save first, edit the file, then reload again to show the new entry.
reload_es() { curl -s -m 30 http://127.0.0.1:1234/reloadgames >/dev/null 2>&1 || true; }
reload_es
python3 - <<"PY"
import xml.etree.ElementTree as ET
from pathlib import Path
path = Path("/userdata/roms/tools/gamelist.xml")
tree = ET.parse(path) if path.exists() else ET.ElementTree(ET.Element("gameList"))
root = tree.getroot()
game = next((g for g in root.findall("game") if g.findtext("path") == "./Battery.sh"), None)
if game is None:
    game = ET.SubElement(root, "game")
fields = (("path", "./Battery.sh"), ("name", "Battery"),
          ("desc", "Charge limit while plugged in (40-60%, 50-80% or 20-80%), a one-time full "
                   "charge on request, low-battery shutdown, a buzz on plugging in the charger "
                   "and battery status. English or Russian, switched in the app."),
          ("image", "./images/battery.png"), ("developer", "rg40xx-demos"),
          ("genre", "System Tools"))
changed = False
for tag, text in fields:
    node = game.find(tag)
    if node is None:
        node = ET.SubElement(game, tag)
    if node.text != text:
        node.text, changed = text, True
if changed:
    ET.indent(tree, "\t")
    tree.write(path, encoding="utf-8", xml_declaration=True)
    print("Updated Battery in the Tools gamelist")
PY
reload_es
/userdata/system/bin/battery-tools status'
echo "Installed. Battery is in Tools (EmulationStation gamelists were reloaded)."
