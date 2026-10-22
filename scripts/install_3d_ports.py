#!/usr/bin/env python3
"""3D ports for Anbernic RG40XX H (device code: rg40xx-h).

Catalog and release zips come from the official PortMaster repos, so only the
port packages are downloaded. Games marked "needs files" still require assets
from a copy you own.

Usage:
    python scripts/install_3d_ports.py --list
    python scripts/install_3d_ports.py --download downloads/3d_ports
    python scripts/install_3d_ports.py --download downloads/3d_ports --all
    python scripts/install_3d_ports.py --install
    python scripts/install_3d_ports.py --install --all
"""

import argparse
import json
import os
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PORTS_URL = "https://raw.githubusercontent.com/PortsMaster/PortMaster-Info/main/ports.json"
DEVICE = "rg40xx-h"
HOST = "192.168.2.173"
USER = "root"
PASSWORD = "linux"

PORTMASTER_DIRS = [
    "/userdata/system/.local/share/PortMaster",  # Knulli / ROCKNIX
    "/mnt/mmc/MUOS/PortMaster",                  # muOS
    "/roms/ports/PortMaster",
]

# Ready to Run: assets are included, nothing to buy.
FREE = [
    "quake.zip",
    "descent.zip",
    "descent2.zip",
    "alephone-marathon.zip",
    "alephone-marathon2.zip",
    "alephone-marathoninfinity.zip",
    "cromagrally.zip",
    "srb2.zip",
    "srb2kart.zip",
    "supertuxkart.zip",
    "neverball.zip",
    "triggerrally.zip",
    "warzone2100.zip",
    "minetest.zip",
]

# Needs files from a game/ROM you own.
OWNED = [
    "gta3.zip",
    "gtavc.zip",
    "half-life.zip",
    "maxpayne.zip",
    "quake.2.zip",
    "quake3.zip",
    "quakespasm.zip",
    "ut99.zip",
    "openmw.zip",
    "rvgl.zip",
    "nfs2se.zip",
    "carmageddon.zip",
    "wipeout.zip",
    "tomb.raider.1.zip",
    "descent3.zip",
    "jedioutcast.zip",
    "jediacademy.zip",
    "openjkdf2.zip",
    "theforceengine.zip",
    "iortcw.zip",
    "avp.zip",
    "doom3.zip",
    "serioussam-tfe.zip",
    "serioussam-tse.zip",
    "openmohaa.zip",
    "render96ex.zip",
    "sm64coopdx.zip",
    "spaghettikart.zip",
    "soh.zip",
    "soh2.zip",
    "perfectdark.zip",
]


def fetch_catalog():
    req = urllib.request.Request(PORTS_URL, headers={"User-Agent": "rg40xx-3d-ports/1.0"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.load(resp)["ports"]


def compatible(info):
    avail = info["attr"].get("avail") or []
    return not avail or any(item.startswith(DEVICE + ":") for item in avail)


def select(catalog, include_owned):
    names = FREE + (OWNED if include_owned else [])
    entries = []
    missing = []
    for name in names:
        info = catalog.get(name)
        if info is None:
            missing.append(name)
            continue
        if not compatible(info):
            missing.append(name)
            continue
        entries.append(info)
    return entries, missing


def fmt_size(size):
    return f"{size / (1024 * 1024):.0f} MB"


def print_list(entries):
    entries = sorted(entries, key=lambda e: (not e["attr"]["rtr"], e["attr"]["title"].lower()))
    free = [e for e in entries if e["attr"]["rtr"]]
    owned = [e for e in entries if not e["attr"]["rtr"]]

    print(f"\n=== Ready to Run ({len(free)}) ===")
    for e in free:
        print(f"  {e['attr']['title']:<38} {fmt_size(e['source']['size']):>8}  {e['name']}")
    if owned:
        print(f"\n=== Needs your game files ({len(owned)}) ===")
        for e in owned:
            print(f"  {e['attr']['title']:<38} {fmt_size(e['source']['size']):>8}  {e['name']}")
    print()


def download(entries, dest):
    os.makedirs(dest, exist_ok=True)
    ok = 0
    for e in entries:
        url = e["source"]["url"]
        expected = int(e["source"]["size"])
        path = os.path.join(dest, e["name"])
        if os.path.exists(path) and os.path.getsize(path) == expected:
            print(f"[skip] {e['name']} (already downloaded)")
            ok += 1
            continue
        print(f"[get ] {e['name']} ({fmt_size(expected)})")
        tmp = path + ".part"
        req = urllib.request.Request(url, headers={"User-Agent": "rg40xx-3d-ports/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as out:
                total = int(resp.headers.get("Content-Length") or expected)
                done = 0
                started = time.time()
                last = started
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    now = time.time()
                    if now - last > 3:
                        last = now
                        speed = done / (1024 * 1024) / max(now - started, 0.001)
                        print(f"       {done / (1024 * 1024):.0f}/{total / (1024 * 1024):.0f} MB @ {speed:.1f} MB/s")
            os.replace(tmp, path)
            ok += 1
        except Exception as exc:
            if os.path.exists(tmp):
                os.remove(tmp)
            print(f"[fail] {e['name']}: {exc}")
    print(f"\nDownloaded {ok}/{len(entries)} to {os.path.abspath(dest)}")


def connect():
    import paramiko

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=15)
    return client


def find_portmaster(client):
    for path in PORTMASTER_DIRS:
        _, out, _ = client.exec_command(f"test -d {path} && echo {path}")
        found = out.read().decode("utf-8", errors="replace").strip()
        if found:
            return found
    return None


def install(entries):
    client = connect()
    pm_dir = find_portmaster(client)
    if pm_dir is None:
        client.close()
        sys.exit("PortMaster not found on device. Install it first (portmaster.games).")
    print(f"PortMaster: {pm_dir}")

    ok = 0
    failed = []
    for e in entries:
        name = e["name"]
        print(f"[inst] {name}")
        cmd = f"cd {pm_dir} && ./harbourmaster --quiet install {name}"
        _, stdout, stderr = client.exec_command(cmd, timeout=900)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        status = stdout.channel.recv_exit_status()
        tail = (out.strip().splitlines() or [""])[-1]
        if tail:
            print(f"       {tail}")
        if err.strip():
            print(f"       ERR: {err.strip()[-300:]}")
        if status == 0:
            ok += 1
        else:
            failed.append(name)

    ports_dir = find_ports_dir(client)
    if ports_dir:
        client.exec_command(f"chmod -R +x {ports_dir}/*.sh {ports_dir}/*/ 2>/dev/null")
    client.exec_command("curl -s http://127.0.0.1:1234/reloadgames >/dev/null 2>&1")
    client.close()
    print(f"\nInstalled {ok}/{len(entries)}.")
    if failed:
        print(f"Failed: {', '.join(failed)}")


def find_ports_dir(client):
    for path in ("/userdata/roms/ports", "/mnt/mmc/ROMS/Ports", "/roms/ports"):
        _, out, _ = client.exec_command(f"test -d {path} && echo {path}")
        found = out.read().decode("utf-8", errors="replace").strip()
        if found:
            return found
    return None


def main():
    parser = argparse.ArgumentParser(description="3D ports for RG40XX H")
    parser.add_argument("--list", action="store_true", help="show the curated list (default)")
    parser.add_argument("--download", metavar="DIR", help="download release zips into DIR")
    parser.add_argument("--install", action="store_true", help=f"install over SSH to {HOST}")
    parser.add_argument("--all", action="store_true", help="also include ports that need your own game files")
    args = parser.parse_args()

    catalog = fetch_catalog()
    entries, missing = select(catalog, args.all)
    if missing:
        print(f"[warn] not found / not compatible: {', '.join(missing)}", file=sys.stderr)

    if args.download:
        download(entries, args.download)
    elif args.install:
        install(entries)
    else:
        print_list(entries)
        print("Run with --download DIR to fetch the zips, or --install to push them to the device.")
        print("Add --all to include ports that need files from a game you own.")


if __name__ == "__main__":
    main()
