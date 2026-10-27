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
for service in chargelimit lowbattery; do
    install -m 755 "$STAGE/services/$service" /userdata/system/services/$service
done
mkdir -p /userdata/roms/tools/battery
install -m 644 "$STAGE/app/battery_app.py" /userdata/roms/tools/battery/battery_app.py
install -m 755 "$STAGE/app/Battery.sh" /userdata/roms/tools/Battery.sh
rm -rf "$STAGE"
[ -f /userdata/system/configs/battery-tools.conf ] || /userdata/system/bin/battery-tools range 40 60 >/dev/null
for service in chargelimit lowbattery; do
    knulli-services enable $service >/dev/null 2>&1 || true
    /userdata/system/services/$service stop >/dev/null 2>&1 || true
    /userdata/system/services/$service start
done
mkdir -p /userdata/roms/tools/images
python3 /userdata/roms/tools/battery/battery_app.py --icon /userdata/roms/tools/images/battery.png >/dev/null 2>&1 || true
python3 - <<"PY"
import xml.etree.ElementTree as ET
from pathlib import Path
path = Path("/userdata/roms/tools/gamelist.xml")
tree = ET.parse(path) if path.exists() else ET.ElementTree(ET.Element("gameList"))
root = tree.getroot()
game = next((g for g in root.findall("game") if g.findtext("path") == "./Battery.sh"), None)
if game is None:
    game = ET.SubElement(root, "game")
fields = (("path", "./Battery.sh"), ("name", "Батарея"),
          ("desc", "Ограничение заряда на зарядке (40–60%, 50–80% или 20–80%), полный заряд "
                   "один раз по запросу, выключение при низком заряде и состояние батареи."),
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
/userdata/system/bin/battery-tools status'
echo "Installed. Reload games in EmulationStation (Start > Game settings > Update gamelists) to see Battery in Tools."
