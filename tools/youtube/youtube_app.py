#!/usr/bin/env python3
"""YouTube without ads for the Anbernic RG40XX H (Knulli), 640x480.

yt-dlp finds the videos and the stream, mpv plays it. The app drives mpv over its IPC socket
and reads the gamepad itself while a video plays (mpv on Knulli has no Lua and no gamepad
input), which also gives SponsorBlock skips and resume positions.

yt-dlp ships as a compressed zipapp that takes ~6 s just to start on this CPU, so the app
repacks the newest copy it finds into lib/yt_dlp-<version>.pyz with precompiled bytecode
(once per version) and imports it in-process.
"""

import json
import os
import queue
import re
import select
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

import pygame

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
CACHE_DIR = os.path.join(BASE_DIR, "cache")
LIB_DIR = os.path.join(BASE_DIR, "lib")
STATE_FILE = os.path.join(BASE_DIR, "state.json")
FONT_PATH = os.path.join(BASE_DIR, "font.ttf")
UPDATED_YTDLP = os.path.join(LIB_DIR, "yt-dlp.zipapp")
YTDLP_SOURCES = (UPDATED_YTDLP, "/userdata/system/bin/yt-dlp", "/usr/bin/yt-dlp")
YTDLP_LATEST_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
MPV = "/usr/bin/mpv"
MPV_SOCKET = "/tmp/rg-youtube-mpv.sock"
ES_INPUT = ("/userdata/system/configs/emulationstation/es_input.cfg",
            "/usr/share/emulationstation/es_input.cfg")

# Only the android client still gets a progressive stream (format 18: 360p H.264 + AAC)
# without a JavaScript runtime and PO tokens; android_vr and web clients get 403 or nothing.
PLAYER_CLIENT = "android"
STREAM_FORMAT = "18/b[height<=480]/b"
SPONSOR_CATEGORIES = ("sponsor", "selfpromo", "interaction")
SPONSOR_NAMES = {"sponsor": "спонсорская вставка", "selfpromo": "самореклама",
                 "interaction": "просьба подписаться"}

WIDTH, HEIGHT = 640, 480
HEADER_H = 46
FOOTER_H = 24
CARD_H, CARD_GAP = 84, 6
THUMB_W, THUMB_H = 120, 68

C_BG = (15, 15, 15)
C_HEADER = (24, 24, 24)
C_CARD = (30, 30, 32)
C_CARD_SEL = (48, 52, 64)
C_ACCENT = (255, 0, 51)
C_BLUE = (62, 166, 255)
C_TEXT = (245, 245, 245)
C_MUTED = (160, 160, 160)
C_BADGE_BG = (10, 10, 10)
C_GREEN = (43, 166, 64)
C_BORDER = (55, 55, 62)
C_KEY = (38, 38, 44)

# Home tab topics: a search for videos (no shorts) uploaded this week. The plain "this week"
# filter (EgIIAw==) often returns only 2-3 results for a query.
WEEK_FILTER = "EgQIAxAB"
TOPICS = (("Популярное", "популярное"), ("Музыка", "музыка"), ("Игры", "игры"),
          ("Ретро", "ретро игры"), ("Фильмы", "фильм"), ("Наука", "наука"),
          ("Юмор", "юмор"), ("Подкасты", "подкаст"))
DEFAULT_PRESETS = ("Ретро игры", "Музыка", "Обзоры", "Фильмы", "Подкасты")
PAGE = 20

# EmulationStation names -> (SDL button id, evdev code) on the RG40XX H, used when es_input.cfg
# has no entry for the controller.
DEFAULT_BUTTONS = {"a": (3, 304), "b": (4, 305), "y": (5, 306), "x": (6, 307),
                   "pageup": (7, 308), "pagedown": (8, 309), "select": (9, 310),
                   "start": (10, 311), "hotkey": (11, 312), "l2": (13, 314), "r2": (14, 315)}
ACTIONS = {"a": "A", "b": "B", "x": "X", "y": "Y", "pageup": "L1", "pagedown": "R1",
           "select": "SELECT", "start": "START", "hotkey": "MENU", "l2": "L2", "r2": "R2"}

yt_dlp = None
YTDLP_VERSION = ""
YTDLP_PYZ = ""


def log(*args):
    print(time.strftime("%H:%M:%S"), *args, file=sys.stderr, flush=True)


# ----------------- Text helpers ----------------- #

def clean_text(text):
    """Replaces emoji and symbols the bundled font draws as empty boxes with spaces."""
    out = []
    for ch in text or "":
        code = ord(ch)
        if code >= 0x2190 or 0x200B <= code <= 0x200F or 0x2060 <= code <= 0x206F:
            ch = " "
        out.append(ch)
    return re.sub(r"\s+", " ", "".join(out)).strip()


def format_duration(seconds):
    if not seconds:
        return ""
    s = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def format_size(num):
    if not num:
        return ""
    mb = num / (1024 * 1024)
    return f"{mb / 1024:.1f} ГБ" if mb >= 1024 else f"{mb:.0f} МБ"


def format_views(count):
    if not count:
        return ""
    n = int(count)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} млн просмотров"
    if n >= 1_000:
        return f"{n // 1_000} тыс. просмотров"
    return f"{n} просмотров"


def short_error(exc):
    msg = clean_text(str(exc))
    msg = re.sub(r"^ERROR:\s*", "", msg)
    msg = re.sub(r"^\[[^\]]+\]\s*[\w-]{11}:\s*", "", msg)
    return msg[:90]


# ----------------- State (history, search queries) ----------------- #

class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.data = {"history": [], "queries": []}
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                self.data.update(json.load(f))
        except (OSError, ValueError):
            pass

    def save(self):
        with self.lock:
            text = json.dumps(self.data, ensure_ascii=False)
        try:
            with open(STATE_FILE + ".tmp", "w", encoding="utf-8") as f:
                f.write(text)
            os.replace(STATE_FILE + ".tmp", STATE_FILE)
        except OSError as e:
            log("State save failed:", e)

    def history(self):
        with self.lock:
            return [dict(h) for h in self.data["history"]]

    def position(self, video_id):
        with self.lock:
            for h in self.data["history"]:
                if h["id"] == video_id:
                    return h.get("pos", 0), h.get("duration_s", 0)
        return 0, 0

    def record(self, item, pos, duration):
        entry = {k: item.get(k) for k in ("id", "title", "channel", "duration", "thumb_url")}
        entry["pos"] = pos
        entry["duration_s"] = duration
        entry["watched"] = time.time()
        with self.lock:
            hist = [h for h in self.data["history"] if h["id"] != item["id"]]
            self.data["history"] = [entry] + hist[:99]
        self.save()

    def remove(self, video_id):
        with self.lock:
            self.data["history"] = [h for h in self.data["history"] if h["id"] != video_id]
        self.save()

    def queries(self):
        with self.lock:
            return list(self.data["queries"])

    def add_query(self, query):
        with self.lock:
            rest = [q for q in self.data["queries"] if q.lower() != query.lower()]
            self.data["queries"] = [query] + rest[:7]
        self.save()


# ----------------- yt-dlp ----------------- #

def zipapp_version(path):
    try:
        with zipfile.ZipFile(path) as z:
            text = z.read("yt_dlp/version.py").decode()
        return re.search(r"__version__\s*=\s*'([^']+)'", text).group(1)
    except Exception:
        return None


def version_key(version):
    return tuple(int(x) for x in re.findall(r"\d+", version))


def build_pyz(src, dst):
    """Repacks a yt-dlp zipapp as an uncompressed zip of precompiled modules."""
    import importlib.util
    import marshal
    header = importlib.util.MAGIC_NUMBER + bytes(12)
    tmp = dst + ".tmp"
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED) as zout:
        for info in zin.infolist():
            name = info.filename
            if not name.startswith("yt_dlp/") or name.endswith("/"):
                continue
            data = zin.read(info)
            if name.endswith(".py"):
                code = compile(data, name, "exec", dont_inherit=True)
                zout.writestr(name[:-3] + ".pyc", header + marshal.dumps(code))
            else:
                zout.writestr(name, data)
    os.replace(tmp, dst)


def prepare_ytdlp(progress=lambda msg: None):
    """Builds (once per version) and imports the newest yt-dlp found on the device."""
    global yt_dlp, YTDLP_VERSION, YTDLP_PYZ
    found = [(zipapp_version(p), p) for p in YTDLP_SOURCES if os.path.isfile(p)]
    found = [f for f in found if f[0]]
    if not found:
        raise RuntimeError("yt-dlp не найден на приставке")
    version, src = max(found, key=lambda f: version_key(f[0]))
    os.makedirs(LIB_DIR, exist_ok=True)
    pyz = os.path.join(LIB_DIR, f"yt_dlp-{version}.pyz")
    if not os.path.exists(pyz):
        progress(f"Подготовка yt-dlp {version} (один раз, ~15 с)...")
        log("Building", pyz, "from", src)
        build_pyz(src, pyz)
        for name in os.listdir(LIB_DIR):
            if name.startswith("yt_dlp-") and name.endswith(".pyz") and name != os.path.basename(pyz):
                os.remove(os.path.join(LIB_DIR, name))
    sys.path.insert(0, pyz)
    import yt_dlp as module
    yt_dlp, YTDLP_VERSION, YTDLP_PYZ = module, version, pyz
    log("yt-dlp", version, "from", src)


def ydl_opts(**extra):
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True,
            "socket_timeout": 15}
    opts.update(extra)
    return opts


def entry_to_item(e):
    vid = e.get("id")
    if not vid or len(vid) != 11 or "/shorts/" in (e.get("url") or ""):
        return None
    live = e.get("live_status") in ("is_live", "is_upcoming")
    return {"id": vid,
            "title": clean_text(e.get("title")) or "Без названия",
            "channel": clean_text(e.get("channel") or e.get("uploader")) or "YouTube",
            "duration": "LIVE" if live else format_duration(e.get("duration")),
            "views": format_views(e.get("view_count")),
            "thumb_url": f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg",
            "live": live}


def search(source, count):
    """source is a search URL or a plain query."""
    url = source if source.startswith("https://") else f"ytsearch{count}:{source}"
    with yt_dlp.YoutubeDL(ydl_opts(extract_flat="in_playlist", playlistend=count)) as ydl:
        info = ydl.extract_info(url, download=False)
    items, seen = [], set()
    for e in info.get("entries") or []:
        item = entry_to_item(e)
        if item and item["id"] not in seen:
            seen.add(item["id"])
            items.append(item)
    return items


def extract_stream(video_id):
    opts = ydl_opts(format=STREAM_FORMAT,
                    extractor_args={"youtube": {"player_client": [PLAYER_CLIENT]}})
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
    if not info.get("url"):
        raise RuntimeError("YouTube не отдал поток для этого видео")
    return info


def sponsor_segments(video_id):
    """SponsorBlock segments as (start, end, category); empty on any error."""
    cats = urllib.parse.quote(json.dumps(list(SPONSOR_CATEGORIES)))
    url = f"https://sponsor.ajay.app/api/skipSegments?videoID={video_id}&categories={cats}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "rg-youtube"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return sorted((float(s["segment"][0]), float(s["segment"][1]), s.get("category", ""))
                      for s in data if len(s.get("segment", ())) == 2)
    except Exception:
        return []


def update_ytdlp(progress):
    """Downloads the latest yt-dlp release; returns its version or raises."""
    tmp = UPDATED_YTDLP + ".part"
    progress("Скачивание свежего yt-dlp...")
    req = urllib.request.Request(YTDLP_LATEST_URL, headers={"User-Agent": "rg-youtube"})
    with urllib.request.urlopen(req, timeout=30) as resp, open(tmp, "wb") as f:
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            f.write(chunk)
    version = zipapp_version(tmp)
    if not version:
        os.remove(tmp)
        raise RuntimeError("скачанный файл не похож на yt-dlp")
    os.replace(tmp, UPDATED_YTDLP)
    return version


# ----------------- Gamepad ----------------- #

def load_buttons(device_name):
    """{es name: (sdl id, evdev code)} from EmulationStation's controller config."""
    for path in ES_INPUT:
        try:
            root = ET.parse(path).getroot()
        except (OSError, ET.ParseError):
            continue
        for config in root.iter("inputConfig"):
            if config.get("deviceName") != device_name:
                continue
            buttons = dict(DEFAULT_BUTTONS)
            for node in config.iter("input"):
                name, sdl_id, code = node.get("name"), node.get("id"), node.get("code")
                if node.get("type") == "button" and name in buttons and (sdl_id or "").isdigit():
                    buttons[name] = (int(sdl_id), int(code) if (code or "").isdigit() else buttons[name][1])
            return buttons
    return dict(DEFAULT_BUTTONS)


def open_gamepad(name):
    try:
        import evdev
    except ImportError:
        return None
    for path in evdev.list_devices():
        try:
            dev = evdev.InputDevice(path)
        except OSError:
            continue
        if dev.name == name or (not name and "Controller" in dev.name):
            return dev
        dev.close()
    return None


# ----------------- mpv ----------------- #

class Mpv:
    """mpv process plus its JSON IPC socket."""

    def __init__(self, src, title, start=0):
        try:
            os.remove(MPV_SOCKET)
        except OSError:
            pass
        cmd = [MPV, "--fs", "--vo=sdl", "--no-terminal", "--idle=no",
               f"--input-ipc-server={MPV_SOCKET}", f"--force-media-title={title}",
               "--cache=yes", "--demuxer-max-bytes=48MiB", "--demuxer-readahead-secs=60",
               "--stream-lavf-o=reconnect=1,reconnect_streamed=1,reconnect_delay_max=5",
               "--osd-font-size=30", "--osd-duration=2000", "--sub-auto=no"]
        if start:
            cmd.append(f"--start={start:.0f}")
        cmd.append(src)
        self.log = open("/tmp/youtube-mpv.log", "w")
        self.proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=self.log,
                                     stderr=subprocess.STDOUT)
        self.sock = None
        self.buf = b""
        deadline = time.time() + 8
        while time.time() < deadline and self.proc.poll() is None:
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(MPV_SOCKET)
                self.sock = s
                break
            except OSError:
                s.close()
                time.sleep(0.05)

    def alive(self):
        return self.proc.poll() is None

    def command(self, *args):
        if not self.sock:
            return
        try:
            self.sock.sendall(json.dumps({"command": list(args)}).encode() + b"\n")
        except OSError:
            pass

    def osd(self, text, ms=2500):
        self.command("show-text", text, ms)

    def read_events(self):
        if not self.sock:
            return []
        try:
            data = self.sock.recv(65536)
        except OSError:
            return []
        if not data:
            self.sock.close()
            self.sock = None
            return []
        self.buf += data
        *lines, self.buf = self.buf.split(b"\n")
        events = []
        for line in lines:
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
        return events

    def stop(self):
        self.command("quit")
        try:
            self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        if self.sock:
            self.sock.close()
        self.log.close()


PLAYER_HELP = ("A пауза · ←/→ 10 с · L1/R1 1 мин · ↑/↓ громкость\n"
               "X время · Y скорость · Select сначала · B выход")
SPEEDS = (1.0, 1.25, 1.5, 2.0, 0.75)


def run_player(src, title, start, segments, gamepad, codes):
    """Plays src until the user leaves or it ends. Returns (last position, duration, ended)."""
    mpv = Mpv(src, title, start)
    _current["mpv"] = mpv
    mpv.command("observe_property", 1, "time-pos")
    mpv.command("observe_property", 2, "duration")
    hint = PLAYER_HELP
    if start:
        hint = f"Продолжение с {format_duration(start)} (Select - сначала)\n" + hint
    mpv.osd(hint, 5000)

    action_by_code = {code: ACTIONS[name] for name, (_, code) in codes.items()}
    pos, duration, ended, playing = start, 0.0, False, False
    speed_idx = 0
    hat = {"x": 0, "y": 0}
    hat_repeat = 0.0
    skipped_at = {}

    def press(action):
        nonlocal speed_idx
        if action in ("A", "START"):
            mpv.command("cycle", "pause")
        elif action in ("B", "MENU"):
            mpv.command("quit")
        elif action == "L1":
            mpv.command("seek", -60)
        elif action == "R1":
            mpv.command("seek", 60)
        elif action == "X":
            mpv.command("show-progress")
        elif action == "Y":
            speed_idx = (speed_idx + 1) % len(SPEEDS)
            mpv.command("set_property", "speed", SPEEDS[speed_idx])
            mpv.osd(f"Скорость {SPEEDS[speed_idx]:g}x")
        elif action == "SELECT":
            mpv.command("seek", 0, "absolute")
        elif action == "L2":
            mpv.command("seek", -5)
        elif action == "R2":
            mpv.command("seek", 5)

    def hat_action():
        if hat["x"]:
            mpv.command("seek", 10 * hat["x"])
        elif hat["y"]:
            mpv.command("add", "volume", -5 * hat["y"])
            mpv.osd("Громкость ${volume}%", 1200)

    while mpv.alive():
        fds = [mpv.sock] if mpv.sock else []
        if gamepad:
            fds.append(gamepad.fd)
        timeout = 0.1 if (hat["x"] or hat["y"]) else 0.5
        ready = []
        try:
            if fds:
                ready = select.select(fds, [], [], timeout)[0]
            else:
                time.sleep(timeout)
        except (OSError, ValueError):
            time.sleep(0.2)
        if gamepad and gamepad.fd in ready:
            try:
                for ev in gamepad.read():
                    if ev.type == 1 and ev.value == 1 and ev.code in action_by_code:
                        press(action_by_code[ev.code])
                    elif ev.type == 3 and ev.code in (16, 17):
                        axis = "x" if ev.code == 16 else "y"
                        hat[axis] = ev.value
                        if ev.value:
                            hat_action()
                            hat_repeat = time.time() + 0.45
            except OSError:
                gamepad = None
        if (hat["x"] or hat["y"]) and time.time() >= hat_repeat:
            hat_action()
            hat_repeat = time.time() + 0.2
        if mpv.sock and mpv.sock in ready:
            for ev in mpv.read_events():
                if ev.get("event") == "property-change" and ev.get("data") is not None:
                    if ev.get("id") == 1:
                        pos, playing = float(ev["data"]), True
                        for seg_start, seg_end, cat in segments:
                            # Skip once per pass; seeking back into a segment skips it again.
                            if seg_start <= pos < seg_end - 0.5 and time.time() - skipped_at.get(seg_start, 0) > 3:
                                skipped_at[seg_start] = time.time()
                                mpv.command("seek", seg_end, "absolute")
                                mpv.osd(f"Пропущено: {SPONSOR_NAMES.get(cat, cat)}")
                                break
                    elif ev.get("id") == 2:
                        duration = float(ev["data"])
                elif ev.get("event") == "end-file" and ev.get("reason") == "eof":
                    ended = True
    rc = mpv.proc.returncode
    mpv.stop()
    _current["mpv"] = None
    if rc and not playing:
        raise RuntimeError(f"mpv завершился с ошибкой {rc}, см. /tmp/youtube-mpv.log")
    return pos, duration, ended


_current = {"mpv": None}


def _terminate(signum, frame):
    if _current["mpv"]:
        _current["mpv"].proc.kill()
    sys.exit(0)


# ----------------- Downloads ----------------- #

class DownloadManager:
    def __init__(self):
        self.queue = queue.Queue()
        self.current = None
        self.pending = 0
        self.last_result = None
        self.lock = threading.Lock()
        threading.Thread(target=self._worker, daemon=True).start()

    def add(self, item, kind):
        with self.lock:
            self.pending += 1
        self.queue.put((dict(item), kind))

    def status(self):
        with self.lock:
            return (dict(self.current) if self.current else None), self.pending

    def take_result(self):
        with self.lock:
            result, self.last_result = self.last_result, None
            return result

    def _worker(self):
        while True:
            item, kind = self.queue.get()
            with self.lock:
                self.pending -= 1
                self.current = {"title": item["title"], "progress": 0.0, "speed": ""}
            safe = re.sub(r'[\\/*?:"<>|]', "", item["title"]).strip()[:60] or item["id"]
            out = os.path.join(DOWNLOADS_DIR, f"{safe} [{item['id']}].%(ext)s")
            # The zipapp has no yt_dlp/__main__.py, so "python3 -m yt_dlp" does not work.
            cmd = [sys.executable, "-c", "import yt_dlp; yt_dlp.main()",
                   "--no-warnings", "--newline", "--no-playlist",
                   "--no-mtime", "--extractor-args", f"youtube:player_client={PLAYER_CLIENT}",
                   "-f", STREAM_FORMAT,
                   "--sponsorblock-remove", ",".join(SPONSOR_CATEGORIES), "-o", out]
            if kind == "audio":
                cmd += ["-x", "--audio-format", "m4a"]
            else:
                cmd += ["--merge-output-format", "mp4"]
            cmd.append(f"https://www.youtube.com/watch?v={item['id']}")
            env = dict(os.environ, PYTHONPATH=YTDLP_PYZ)
            error = last = ""
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, bufsize=1, env=env)
                for line in proc.stdout:
                    m = re.search(r"\[download\]\s+([\d.]+)%.*?at\s+(\S+)", line)
                    if m:
                        with self.lock:
                            self.current["progress"] = float(m.group(1))
                            self.current["speed"] = m.group(2)
                    elif line.startswith("ERROR"):
                        error = short_error(line)
                    elif line.strip():
                        last = line.strip()
                proc.wait()
                if proc.returncode and not error:
                    error = short_error(last) or f"yt-dlp завершился с кодом {proc.returncode}"
            except OSError as e:
                error = str(e)
            if error:
                log("Download failed:", item["id"], error)
            with self.lock:
                self.current = None
                self.last_result = (item["title"], error)


# ----------------- Thumbnails ----------------- #

class ThumbnailManager:
    def __init__(self):
        self.cache = {}
        self.requested = set()
        self.queue = queue.Queue()
        self.lock = threading.Lock()
        threading.Thread(target=self._worker, daemon=True).start()
        threading.Thread(target=self._prune, daemon=True).start()

    def get(self, video_id, url):
        with self.lock:
            if video_id in self.cache:
                return self.cache[video_id]
            if video_id in self.requested:
                return None
            self.requested.add(video_id)
        self.queue.put((video_id, url))
        return None

    def _worker(self):
        while True:
            video_id, url = self.queue.get()
            path = os.path.join(CACHE_DIR, f"{video_id}.jpg")
            try:
                if not os.path.exists(path) and url:
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=6) as resp:
                        data = resp.read()
                    with open(path, "wb") as f:
                        f.write(data)
                surf = pygame.transform.smoothscale(pygame.image.load(path), (THUMB_W, THUMB_H))
                with self.lock:
                    self.cache[video_id] = surf
            except Exception:
                with self.lock:
                    self.requested.discard(video_id)

    @staticmethod
    def _prune(keep=400):
        try:
            files = [os.path.join(CACHE_DIR, f) for f in os.listdir(CACHE_DIR)]
            files.sort(key=os.path.getmtime, reverse=True)
            for path in files[keep:]:
                os.remove(path)
        except OSError:
            pass


# ----------------- UI ----------------- #

_TEXT_CACHE = {}


def get_text(font, text, color):
    key = (id(font), text, color)
    surf = _TEXT_CACHE.get(key)
    if surf is None:
        if len(_TEXT_CACHE) > 800:
            _TEXT_CACHE.clear()
        surf = _TEXT_CACHE[key] = font.render(text or " ", True, color)
    return surf


def fit_text(font, text, max_w):
    if font.size(text)[0] <= max_w:
        return text
    while text and font.size(text + "...")[0] > max_w:
        text = text[:-1]
    return text.rstrip() + "..."


def wrap_text(font, text, max_w, lines=2):
    words, out, cur = text.split(" "), [], ""
    for i, word in enumerate(words):
        trial = f"{cur} {word}".strip()
        if font.size(trial)[0] <= max_w:
            cur = trial
            continue
        if cur:
            out.append(cur)
        cur = word
        if len(out) == lines - 1:
            out.append(fit_text(font, " ".join([cur] + words[i + 1:]), max_w))
            return out
    if cur:
        out.append(fit_text(font, cur, max_w))
    return out[:lines]


def draw_play_icon(surface, cx, cy, size, color):
    pygame.draw.polygon(surface, color, [(cx - size * 0.4, cy - size * 0.5),
                                         (cx - size * 0.4, cy + size * 0.5),
                                         (cx + size * 0.5, cy)])


class VirtualKeyboard:
    RU_KEYS = [list("1234567890"), list("ЙЦУКЕНГШЩЗХ"), list("ФЫВАПРОЛДЖЭ"), list("ЯЧСМИТЬБЮЪ"),
               ["RU/EN", "Пробел", "Стереть", "Найти"]]
    EN_KEYS = [list("1234567890"), list("QWERTYUIOP"), list("ASDFGHJKL'"), list("ZXCVBNM-.?"),
               ["RU/EN", "Пробел", "Стереть", "Найти"]]

    def __init__(self, fonts):
        self.font_main, self.font_tiny = fonts
        self.lang = "RU"
        self.text = ""
        self.row, self.col = 1, 0
        self.presets = list(DEFAULT_PRESETS)
        self.preset_idx = 0
        self.section = "keys"

    def open(self, recent):
        self.presets = (recent + [p for p in DEFAULT_PRESETS if p not in recent])[:6]
        self.preset_idx = 0
        self.section = "keys"

    def layout(self):
        return self.RU_KEYS if self.lang == "RU" else self.EN_KEYS

    def switch_lang(self):
        self.lang = "EN" if self.lang == "RU" else "RU"
        self.col = min(self.col, len(self.layout()[self.row]) - 1)

    def handle(self, action):
        """Returns 'SEARCH', 'EXIT' or None."""
        if action in ("B", "MENU"):
            return "EXIT"
        if action == "START":
            return "SEARCH" if self.text.strip() else None
        if action in ("X", "L1"):
            self.text = self.text[:-1]
            return None
        if action in ("Y", "SELECT"):
            self.switch_lang()
            return None
        if action == "R1":
            self.text += " "
            return None
        layout = self.layout()
        if self.section == "presets":
            if action == "LEFT":
                self.preset_idx = max(0, self.preset_idx - 1)
            elif action == "RIGHT":
                self.preset_idx = min(len(self.presets) - 1, self.preset_idx + 1)
            elif action == "DOWN":
                self.section = "keys"
                self.row = 0
                self.col = min(self.col, len(layout[0]) - 1)
            elif action == "A":
                self.text = self.presets[self.preset_idx]
                return "SEARCH"
            return None
        if action == "UP":
            if self.row == 0:
                self.section = "presets"
            else:
                self.row -= 1
                self.col = min(self.col, len(layout[self.row]) - 1)
        elif action == "DOWN" and self.row < len(layout) - 1:
            # Keep roughly the same horizontal spot when moving onto the short bottom row.
            frac = (self.col + 0.5) / len(layout[self.row])
            self.row += 1
            self.col = min(int(frac * len(layout[self.row])), len(layout[self.row]) - 1)
        elif action == "LEFT":
            self.col = (self.col - 1) % len(layout[self.row])
        elif action == "RIGHT":
            self.col = (self.col + 1) % len(layout[self.row])
        elif action == "A":
            key = layout[self.row][self.col]
            if key == "RU/EN":
                self.switch_lang()
            elif key == "Пробел":
                self.text += " "
            elif key == "Стереть":
                self.text = self.text[:-1]
            elif key == "Найти":
                return "SEARCH" if self.text.strip() else None
            elif len(self.text) < 60:
                self.text += key.lower()
        return None

    def draw(self, surface, overlay):
        surface.blit(overlay, (0, 0))
        bw, bh = 610, 400
        bx, by = (WIDTH - bw) // 2, 40
        pygame.draw.rect(surface, C_HEADER, (bx, by, bw, bh), border_radius=10)
        pygame.draw.rect(surface, C_BORDER, (bx, by, bw, bh), 2, border_radius=10)

        field = (bx + 15, by + 12, bw - 30, 38)
        pygame.draw.rect(surface, (36, 36, 40), field, border_radius=6)
        pygame.draw.rect(surface, C_ACCENT if self.section == "keys" else C_BORDER, field, 2,
                         border_radius=6)
        shown = self.text + ("_" if int(time.time() * 2) % 2 else " ")
        txt = get_text(self.font_main, fit_text(self.font_main, shown, bw - 60) if self.text
                       else "Введите запрос...", C_TEXT if self.text else C_MUTED)
        surface.blit(txt, (bx + 25, by + 22))
        lang = get_text(self.font_tiny, self.lang, C_MUTED)
        surface.blit(lang, (bx + bw - 25 - lang.get_width(), by + 25))

        px, py = bx + 15, by + 58
        for i, preset in enumerate(self.presets):
            sel = self.section == "presets" and self.preset_idx == i
            label = get_text(self.font_tiny, fit_text(self.font_tiny, preset, 110), C_TEXT)
            pw = label.get_width() + 16
            if px + pw > bx + bw - 15:
                break
            pygame.draw.rect(surface, C_ACCENT if sel else (45, 45, 50), (px, py, pw, 24),
                             border_radius=12)
            surface.blit(label, (px + 8, py + 12 - label.get_height() // 2))
            px += pw + 8

        total_w = bw - 30
        for r, row in enumerate(self.layout()):
            ky = by + 92 + r * 48
            key_w = total_w // len(row)
            for c, key in enumerate(row):
                kx = bx + 15 + c * key_w
                sel = self.section == "keys" and self.row == r and self.col == c
                pygame.draw.rect(surface, C_ACCENT if sel else C_KEY, (kx + 2, ky, key_w - 4, 40),
                                 border_radius=5)
                k = get_text(self.font_main, key, C_TEXT)
                surface.blit(k, (kx + (key_w - k.get_width()) // 2, ky + (40 - k.get_height()) // 2))

        hint = "A ввод · X стереть · R1 пробел · Y язык · Start найти · B закрыть"
        h = get_text(self.font_tiny, hint, C_MUTED)
        surface.blit(h, ((WIDTH - h.get_width()) // 2, by + bh - 24))


class YouTubeApp:
    TABS = ("Главная", "Поиск", "История", "Загрузки")
    HOME, SEARCH, HISTORY, DOWNLOADS = range(4)

    def __init__(self):
        os.environ.setdefault("SDL_VIDEODRIVER", "mali")
        pygame.init()
        self.joysticks = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
        for j in self.joysticks:
            j.init()
        self.pad_name = self.joysticks[0].get_name() if self.joysticks else ""
        self.buttons = load_buttons(self.pad_name)
        self.action_by_id = {sdl_id: ACTIONS[name] for name, (sdl_id, _) in self.buttons.items()}
        log("Gamepad", repr(self.pad_name), self.buttons)
        self.open_display()

        def font(size):
            try:
                return pygame.font.Font(FONT_PATH, size)
            except Exception:
                return pygame.font.Font(None, size + 5)
        self.font_title, self.font_main = font(17), font(13)
        self.font_small, self.font_tiny = font(11), font(10)
        self.overlay = pygame.Surface((WIDTH, HEIGHT))
        self.overlay.set_alpha(200)
        self.overlay.fill((0, 0, 0))
        self.clock = pygame.time.Clock()

        self.state = State()
        self.downloads = DownloadManager()
        self.thumbs = ThumbnailManager()
        self.keyboard = VirtualKeyboard((self.font_main, self.font_tiny))

        self.tab = self.HOME
        self.topic = 0
        self.topic_cache = {}
        self.topic_changed_at = 0.0
        self.lists = {self.HOME: [], self.SEARCH: [], self.HISTORY: [], self.DOWNLOADS: []}
        self.sel = {t: 0 for t in self.lists}
        self.scroll = {t: 0 for t in self.lists}
        self.more = {self.HOME: True, self.SEARCH: True}
        self.query = ""

        self.in_keyboard = False
        self.modal = None   # (title, [(label, callback)]), selection index in modal_sel
        self.modal_sel = 0
        self.results = queue.Queue()
        self.busy = ""      # full-screen loading message
        self.busy_token = None
        self.busy_cancel = False
        self.loading_more = False
        self.status_msg, self.status_until, self.status_error = "", 0.0, False
        self.held = None
        self.held_next = 0.0
        self.last_axis = 0.0
        self.pending_play = None
        self.jobs = 0

        self.refresh_downloads()
        self.refresh_history()
        self.run_task("Запуск...", self._boot, self._booted)

    # ---- display ----

    def open_display(self):
        try:
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.DOUBLEBUF)
        except pygame.error:
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("YouTube")
        pygame.mouse.set_visible(False)

    def set_status(self, msg, seconds=3.0, error=False):
        self.status_msg, self.status_until, self.status_error = msg, time.time() + seconds, error

    # ---- background tasks ----

    def run_task(self, busy_msg, work, done, cancellable=False):
        """Runs work() in a thread behind a full-screen message; done(result, error) is
        called on the UI thread unless the user cancelled with B."""
        token = object()
        self.busy, self.busy_token, self.busy_cancel = busy_msg, token, cancellable
        self._spawn(token, work, done)

    def run_quiet(self, work, done):
        """Like run_task but keeps the list usable (loading more results)."""
        self._spawn(None, work, done)

    def _spawn(self, token, work, done):
        def runner():
            try:
                res, err = work(), None
            except Exception as e:  # yt-dlp raises many kinds of errors
                log("Task failed:", repr(e))
                res, err = None, e
            self.results.put((token, done, res, err))
        threading.Thread(target=runner, daemon=True).start()

    def poll_tasks(self):
        while not self.results.empty():
            token, done, res, err = self.results.get()
            if token is not None:
                if token is not self.busy_token:
                    continue    # cancelled
                self.busy = ""
            done(res, err)

    def _boot(self):
        prepare_ytdlp(lambda msg: setattr(self, "busy", msg))
        self.busy = "Загрузка подборки..."
        return self._fetch_topic(self.topic, PAGE)

    def _booted(self, items, err):
        if err:
            self.set_status(f"Ошибка: {short_error(err)}", 10, True)
            return
        self.lists[self.HOME] = items
        self.topic_cache[self.topic] = items

    def _fetch_topic(self, topic, count):
        query = urllib.parse.quote(TOPICS[topic][1])
        return search(f"https://www.youtube.com/results?search_query={query}&sp={WEEK_FILTER}",
                      count)

    def load_topic(self, topic):
        if topic in self.topic_cache:
            self.lists[self.HOME] = self.topic_cache[topic]
            self.sel[self.HOME] = self.scroll[self.HOME] = 0
            return

        def done(items, err):
            if err:
                self.set_status(f"Ошибка: {short_error(err)}", 6, True)
                return
            self.topic_cache[topic] = items
            if self.topic == topic:
                self.lists[self.HOME] = items
                self.sel[self.HOME] = self.scroll[self.HOME] = 0
                self.more[self.HOME] = True
        self.run_task(f"Загрузка: {TOPICS[topic][0]}...", lambda: self._fetch_topic(topic, PAGE), done)

    def execute_search(self, query):
        query = query.strip()
        if not query or not yt_dlp:
            return
        self.query = query
        self.state.add_query(query)
        self.tab = self.SEARCH

        def done(items, err):
            if err:
                self.set_status(f"Ошибка поиска: {short_error(err)}", 6, True)
                return
            self.lists[self.SEARCH] = items
            self.sel[self.SEARCH] = self.scroll[self.SEARCH] = 0
            self.more[self.SEARCH] = True
            if not items:
                self.set_status("Ничего не найдено", 4)
        self.run_task(f"Поиск: {query}...", lambda: search(query, PAGE), done)

    def load_more(self):
        tab = self.tab
        if self.loading_more or not self.more.get(tab) or not yt_dlp:
            return
        items = self.lists[tab]
        count = len(items) + PAGE
        if tab == self.HOME:
            topic = self.topic
            work = lambda: self._fetch_topic(topic, count)
        else:
            query = self.query
            work = lambda: search(query, count)
        self.loading_more = True

        def done(new_items, err):
            self.loading_more = False
            if err or new_items is None:
                return
            if tab == self.HOME and self.topic != topic:
                return
            if len(new_items) <= len(self.lists[tab]):
                self.more[tab] = False
            self.lists[tab] = new_items
            if tab == self.HOME:
                self.topic_cache[topic] = new_items
        self.run_quiet(work, done)

    def refresh_downloads(self):
        items = []
        try:
            names = sorted(os.listdir(DOWNLOADS_DIR),
                           key=lambda n: os.path.getmtime(os.path.join(DOWNLOADS_DIR, n)),
                           reverse=True)
        except OSError:
            names = []
        for name in names:
            if not name.endswith((".mp4", ".mkv", ".webm", ".m4a", ".mp3")):
                continue
            path = os.path.join(DOWNLOADS_DIR, name)
            m = re.search(r"\[([\w-]{11})\]", name)
            vid = m.group(1) if m else ""
            items.append({"id": vid or name,
                          "title": clean_text(re.sub(r"\s*\[[\w-]{11}\]", "", name).rsplit(".", 1)[0]),
                          "channel": "Аудио" if name.endswith((".m4a", ".mp3")) else "Видео",
                          "duration": "", "size": format_size(os.path.getsize(path)),
                          "filepath": path, "offline": True,
                          "thumb_url": f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg" if vid else ""})
        self.lists[self.DOWNLOADS] = items
        self.downloaded_ids = {i["id"] for i in items}
        self.clamp(self.DOWNLOADS)

    def refresh_history(self):
        self.lists[self.HISTORY] = self.state.history()
        self.clamp(self.HISTORY)

    def clamp(self, tab):
        n = len(self.lists[tab])
        self.sel[tab] = max(0, min(self.sel[tab], n - 1))
        self.scroll[tab] = max(0, min(self.scroll[tab], self.sel[tab]))

    # ---- playback ----

    def play(self, item):
        if item.get("offline"):
            self.pending_play = (item, item["filepath"], [])
            return
        if not yt_dlp:
            return

        def work():
            segments = []
            seg_thread = threading.Thread(target=lambda: segments.extend(sponsor_segments(item["id"])))
            seg_thread.start()
            info = extract_stream(item["id"])
            seg_thread.join(timeout=4)
            return info, list(segments)

        def done(res, err):
            if err:
                self.set_status(f"Не удалось открыть: {short_error(err)}", 8, True)
                return
            info, segments = res
            log("Stream", item["id"], info.get("format_id"), "segments", len(segments))
            self.pending_play = (dict(item, duration_s=info.get("duration") or 0), info["url"], segments)
        self.run_task("Получение видео без рекламы...  B - отмена", work, done, cancellable=True)

    def start_pending_play(self):
        item, src, segments = self.pending_play
        self.pending_play = None
        start, _ = self.state.position(item["id"])
        if item.get("offline") or start < 15:
            start = 0
        self.busy = "Запуск плеера..."
        self.draw()
        gamepad = open_gamepad(self.pad_name)
        pygame.display.quit()
        error = None
        try:
            pos, duration, ended = run_player(src, item["title"], start, segments, gamepad,
                                              self.buttons)
        except Exception as e:
            log("Player failed:", repr(e))
            error, pos, duration, ended = e, start, 0, False
        finally:
            if gamepad:
                gamepad.close()
        pygame.display.init()
        self.open_display()
        pygame.event.clear()
        self.busy = ""
        if error:
            self.set_status(f"Ошибка плеера: {short_error(error)}", 8, True)
            return
        duration = duration or item.get("duration_s") or 0
        if not item.get("offline"):
            # Near the end counts as watched: start from the beginning next time.
            if ended or item.get("live") or (duration and pos > duration - 20):
                pos = 0
            self.state.record(item, round(pos, 1), duration)
            self.refresh_history()

    # ---- actions ----

    def item_menu(self, item):
        if item.get("offline"):
            options = [("Смотреть", lambda: self.play(item)),
                       ("Удалить файл", lambda: self.confirm(
                           "Удалить файл с приставки?", lambda: self.delete_download(item)))]
        else:
            pos, _ = self.state.position(item["id"])
            watch = f"Продолжить с {format_duration(pos)}" if pos >= 15 else "Смотреть"
            options = [(watch, lambda: self.play(item))]
            if pos >= 15:
                options.append(("Смотреть сначала", lambda: self.play_from_start(item)))
            options += [("Скачать видео (360p)", lambda: self.download(item, "video")),
                        ("Скачать только звук", lambda: self.download(item, "audio"))]
            if self.tab == self.HISTORY:
                options.append(("Убрать из истории", lambda: self.forget(item)))
        options.append(("Отмена", None))
        self.open_modal(fit_text(self.font_main, item["title"], 380), options)

    def play_from_start(self, item):
        self.state.record(item, 0, self.state.position(item["id"])[1])
        self.play(item)

    def forget(self, item):
        self.state.remove(item["id"])
        self.refresh_history()

    def download(self, item, kind):
        if not yt_dlp:
            return
        self.downloads.add(item, kind)
        self.set_status("Добавлено в загрузки (без рекламных вставок)")

    def delete_download(self, item):
        try:
            os.remove(item["filepath"])
            self.set_status("Файл удалён", 2)
        except OSError as e:
            self.set_status(f"Ошибка удаления: {e}", 4, True)
        self.refresh_downloads()

    def app_menu(self):
        options = [(f"Обновить yt-dlp (сейчас {YTDLP_VERSION or '-'})", self.update_ytdlp),
                   ("Очистить историю", lambda: self.confirm("Очистить всю историю просмотров?",
                                                             self.clear_history)),
                   ("Выйти из YouTube", self.quit),
                   ("Отмена", None)]
        self.open_modal("Меню", options)

    def clear_history(self):
        self.state.data["history"] = []
        self.state.save()
        self.refresh_history()

    def update_ytdlp(self):
        def work():
            return update_ytdlp(lambda msg: setattr(self, "busy", msg))

        def done(version, err):
            if err:
                self.set_status(f"Не удалось обновить: {short_error(err)}", 8, True)
            elif version_key(version) <= version_key(YTDLP_VERSION):
                self.set_status(f"Уже последняя версия ({YTDLP_VERSION})", 5)
            else:
                # The new module can only be imported in a fresh process.
                self.busy = f"yt-dlp {version} скачан, перезапуск..."
                self.draw()
                pygame.quit()
                os.execv(sys.executable, [sys.executable] + sys.argv)
        self.run_task("Обновление yt-dlp...", work, done)

    def confirm(self, title, callback):
        self.open_modal(title, [("Да", callback), ("Нет", None)])

    def open_modal(self, title, options):
        self.modal = (title, options)
        self.modal_sel = 0

    def quit(self):
        self.running = False

    def switch_tab(self, delta):
        self.tab = (self.tab + delta) % len(self.TABS)
        if self.tab == self.DOWNLOADS:
            self.refresh_downloads()
        elif self.tab == self.HISTORY:
            self.refresh_history()

    def move(self, delta):
        items = self.lists[self.tab]
        if not items:
            return
        tab = self.tab
        self.sel[tab] = max(0, min(len(items) - 1, self.sel[tab] + delta))
        rows = self.visible_rows()
        if self.sel[tab] < self.scroll[tab]:
            self.scroll[tab] = self.sel[tab]
        elif self.sel[tab] >= self.scroll[tab] + rows:
            self.scroll[tab] = self.sel[tab] - rows + 1
        if tab in (self.HOME, self.SEARCH) and self.sel[tab] >= len(items) - 3:
            self.load_more()

    def handle(self, action):
        if self.busy:
            if action == "B" and self.busy_cancel:
                self.busy_token = None
                self.busy = ""
                self.set_status("Отменено", 2)
            return
        if self.in_keyboard:
            res = self.keyboard.handle(action)
            if res == "SEARCH":
                self.in_keyboard = False
                self.execute_search(self.keyboard.text)
            elif res == "EXIT":
                self.in_keyboard = False
            return
        if self.modal:
            _, options = self.modal
            if action == "UP":
                self.modal_sel = (self.modal_sel - 1) % len(options)
            elif action == "DOWN":
                self.modal_sel = (self.modal_sel + 1) % len(options)
            elif action == "A":
                callback = options[self.modal_sel][1]
                self.modal = None
                if callback:
                    callback()
            elif action in ("B", "MENU"):
                self.modal = None
            return

        items = self.lists[self.tab]
        item = items[self.sel[self.tab]] if items else None
        if action == "L1":
            self.switch_tab(-1)
        elif action == "R1":
            self.switch_tab(1)
        elif action == "UP":
            self.move(-1)
        elif action == "DOWN":
            self.move(1)
        elif action == "L2":
            self.move(-self.visible_rows())
        elif action == "R2":
            self.move(self.visible_rows())
        elif action in ("LEFT", "RIGHT") and self.tab == self.HOME:
            self.topic = (self.topic + (1 if action == "RIGHT" else -1)) % len(TOPICS)
            self.topic_changed_at = time.time()
        elif action == "A":
            if self.tab == self.SEARCH and not items:
                self.open_keyboard()
            elif item:
                self.item_menu(item)
        elif action == "X":
            if self.tab == self.SEARCH:
                self.open_keyboard()
            elif item and not item.get("offline"):
                self.download(item, "video")
        elif action == "Y":
            if item and item.get("offline"):
                self.confirm("Удалить файл с приставки?", lambda: self.delete_download(item))
            elif self.tab == self.HOME:
                self.topic_cache.pop(self.topic, None)
                self.load_topic(self.topic)
            elif self.tab == self.HISTORY and item:
                self.forget(item)
        elif action == "SELECT":
            self.open_keyboard()
        elif action == "START":
            self.app_menu()
        elif action == "B":
            self.confirm("Выйти из YouTube?", self.quit)
        elif action == "MENU":
            self.quit()

    def open_keyboard(self):
        self.tab = self.SEARCH
        self.keyboard.open(self.state.queries())
        self.in_keyboard = True

    def process_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.JOYBUTTONDOWN:
                action = self.action_by_id.get(event.button)
                if action:
                    self.handle(action)
            elif event.type == pygame.JOYHATMOTION:
                hx, hy = event.value
                direction = ("UP" if hy == 1 else "DOWN" if hy == -1 else
                             "LEFT" if hx == -1 else "RIGHT" if hx == 1 else None)
                self.held = direction
                if direction:
                    self.handle(direction)
                    self.held_next = time.time() + 0.4
            elif event.type == pygame.JOYAXISMOTION and event.axis in (0, 1):
                now = time.time()
                if abs(event.value) > 0.65 and now - self.last_axis > 0.18:
                    self.last_axis = now
                    if event.axis == 1:
                        self.handle("UP" if event.value < 0 else "DOWN")
                    else:
                        self.handle("LEFT" if event.value < 0 else "RIGHT")
            elif event.type == pygame.KEYDOWN:
                keys = {pygame.K_UP: "UP", pygame.K_DOWN: "DOWN", pygame.K_LEFT: "LEFT",
                        pygame.K_RIGHT: "RIGHT", pygame.K_RETURN: "A", pygame.K_SPACE: "A",
                        pygame.K_ESCAPE: "B", pygame.K_BACKSPACE: "X", pygame.K_y: "Y",
                        pygame.K_q: "L1", pygame.K_e: "R1", pygame.K_s: "SELECT",
                        pygame.K_TAB: "START"}
                if event.key in keys:
                    self.handle(keys[event.key])
        # Held d-pad repeats, for scrolling long lists and the keyboard.
        if self.held and time.time() >= self.held_next:
            self.handle(self.held)
            self.held_next = time.time() + 0.12

    # ---- drawing ----

    def list_top(self):
        return HEADER_H + (36 if self.tab == self.HOME else 8)

    def visible_rows(self):
        return (HEIGHT - FOOTER_H - self.list_top()) // (CARD_H + CARD_GAP)

    def draw(self):
        s = self.screen
        s.fill(C_BG)
        pygame.draw.rect(s, C_HEADER, (0, 0, WIDTH, HEADER_H))
        pygame.draw.line(s, C_BORDER, (0, HEADER_H), (WIDTH, HEADER_H))
        pygame.draw.rect(s, C_ACCENT, (14, 13, 28, 20), border_radius=6)
        draw_play_icon(s, 28, 23, 10, C_TEXT)
        s.blit(get_text(self.font_title, "YouTube", C_TEXT), (48, 12))

        x = 150
        for i, name in enumerate(self.TABS):
            col = C_ACCENT if i == self.tab else C_MUTED
            t = get_text(self.font_main, name, col)
            s.blit(t, (x, 15))
            if i == self.tab:
                pygame.draw.line(s, C_ACCENT, (x, HEADER_H - 3), (x + t.get_width(), HEADER_H - 3), 3)
            x += t.get_width() + 18

        current, pending = self.downloads.status()
        if current:
            txt = f"{current['progress']:.0f}%" + (f" +{pending}" if pending else "")
            t = get_text(self.font_tiny, txt, C_BLUE)
            s.blit(t, (WIDTH - t.get_width() - 12, 17))
            bar_x = WIDTH - t.get_width() - 12 - 58
            pygame.draw.rect(s, (40, 40, 45), (bar_x, 19, 50, 8), border_radius=4)
            pygame.draw.rect(s, C_BLUE, (bar_x, 19, int(50 * current["progress"] / 100), 8),
                             border_radius=4)

        if self.tab == self.HOME:
            self.draw_topics()
        if self.busy:
            self.draw_center(self.busy, C_TEXT)
        else:
            self.draw_list()
        self.draw_footer()
        if self.modal:
            self.draw_modal()
        if self.in_keyboard:
            self.keyboard.draw(s, self.overlay)
        pygame.display.flip()

    def draw_topics(self):
        x, y = 12, HEADER_H + 7
        # Scroll the chip row so the selected topic stays on screen.
        widths = [get_text(self.font_small, name, C_TEXT).get_width() + 18 for name, _ in TOPICS]
        offset = 0
        while sum(widths[offset:self.topic + 1]) + 6 * (self.topic - offset) > WIDTH - 24:
            offset += 1
        for i in range(offset, len(TOPICS)):
            w = widths[i]
            if x + w > WIDTH - 12:
                break
            sel = i == self.topic
            pygame.draw.rect(self.screen, C_TEXT if sel else (45, 45, 50), (x, y, w, 22),
                             border_radius=11)
            t = get_text(self.font_small, TOPICS[i][0], C_BG if sel else C_TEXT)
            self.screen.blit(t, (x + 9, y + 11 - t.get_height() // 2))
            x += w + 6

    def draw_center(self, text, color):
        t = get_text(self.font_main, text, color)
        self.screen.blit(t, ((WIDTH - t.get_width()) // 2, 230))

    def draw_list(self):
        s = self.screen
        items = self.lists[self.tab]
        if not items:
            empty = {self.HOME: "Нет видео. Y - обновить, влево/вправо - другая тема",
                     self.SEARCH: "A или X - открыть поиск",
                     self.HISTORY: "Здесь появятся просмотренные видео",
                     self.DOWNLOADS: "Нет скачанных видео. X на видео - скачать"}[self.tab]
            self.draw_center(empty, C_MUTED)
            return
        top = self.list_top()
        rows = self.visible_rows()
        first = self.scroll[self.tab]
        info_x = 20 + THUMB_W + 12
        info_w = WIDTH - 24 - info_x
        for r in range(rows):
            idx = first + r
            if idx >= len(items):
                break
            item = items[idx]
            sel = idx == self.sel[self.tab]
            y = top + r * (CARD_H + CARD_GAP)
            pygame.draw.rect(s, C_CARD_SEL if sel else C_CARD, (12, y, WIDTH - 24, CARD_H),
                             border_radius=8)
            if sel:
                pygame.draw.rect(s, C_ACCENT, (12, y, WIDTH - 24, CARD_H), 2, border_radius=8)

            tx, ty = 20, y + (CARD_H - THUMB_H) // 2
            pygame.draw.rect(s, (20, 20, 25), (tx, ty, THUMB_W, THUMB_H), border_radius=4)
            thumb = self.thumbs.get(item["id"], item.get("thumb_url")) if item.get("thumb_url") else None
            if thumb:
                s.blit(thumb, (tx, ty))
            else:
                draw_play_icon(s, tx + THUMB_W // 2, ty + THUMB_H // 2, 18, C_MUTED)
            if item.get("duration"):
                live = item["duration"] == "LIVE"
                d = get_text(self.font_tiny, item["duration"], C_TEXT)
                bw = d.get_width() + 8
                pygame.draw.rect(s, C_ACCENT if live else C_BADGE_BG,
                                 (tx + THUMB_W - bw - 3, ty + THUMB_H - 17, bw, 14), border_radius=3)
                s.blit(d, (tx + THUMB_W - bw + 1, ty + THUMB_H - 16))
            pos, dur = self.state.position(item["id"]) if not item.get("offline") else (0, 0)
            if pos and dur:
                pygame.draw.rect(s, (90, 90, 90), (tx, ty + THUMB_H - 3, THUMB_W, 3))
                pygame.draw.rect(s, C_ACCENT, (tx, ty + THUMB_H - 3, int(THUMB_W * min(1, pos / dur)), 3))

            lines = wrap_text(self.font_main, item["title"], info_w)
            for i, line in enumerate(lines):
                s.blit(get_text(self.font_main, line, C_TEXT), (info_x, y + 8 + i * 18))
            sub = item.get("channel", "")
            if item.get("views"):
                sub += "  ·  " + item["views"]
            if item.get("size"):
                sub += "  ·  " + item["size"]
            s.blit(get_text(self.font_small, fit_text(self.font_small, sub, info_w), C_MUTED),
                   (info_x, y + 48))
            badges = []
            if item.get("offline"):
                badges.append(("НА ПРИСТАВКЕ", C_GREEN, (20, 45, 25)))
            elif item["id"] in self.downloaded_ids:
                badges.append(("СКАЧАНО", C_GREEN, (20, 45, 25)))
            if pos and dur:
                badges.append((f"ОСТАНОВЛЕНО НА {format_duration(pos)}", C_BLUE, (15, 35, 55)))
            bx = info_x
            for text, fg, bg in badges:
                b = get_text(self.font_tiny, text, fg)
                pygame.draw.rect(s, bg, (bx, y + 64, b.get_width() + 10, 15), border_radius=4)
                s.blit(b, (bx + 5, y + 65))
                bx += b.get_width() + 16

        if len(items) > rows:
            track_top, track_h = top, rows * (CARD_H + CARD_GAP) - CARD_GAP
            thumb_h = max(20, track_h * rows // len(items))
            thumb_y = track_top + (track_h - thumb_h) * first // max(1, len(items) - rows)
            pygame.draw.rect(s, (60, 60, 66), (WIDTH - 7, thumb_y, 3, thumb_h), border_radius=2)

    def draw_footer(self):
        s = self.screen
        fy = HEIGHT - FOOTER_H
        pygame.draw.rect(s, (18, 18, 20), (0, fy, WIDTH, FOOTER_H))
        pygame.draw.line(s, C_BORDER, (0, fy), (WIDTH, fy))
        result = self.downloads.take_result()
        if result:
            title, error = result
            if error:
                self.set_status(f"Загрузка не удалась: {error}", 8, True)
            else:
                self.set_status(f"Скачано: {title}", 4)
                self.refresh_downloads()
        if time.time() < self.status_until:
            text, col = self.status_msg, (C_ACCENT if self.status_error else C_TEXT)
        elif self.loading_more:
            text, col = "Загрузка ещё...", C_MUTED
        else:
            text = {self.HOME: "A меню · X скачать · ←/→ тема · Y обновить · L1/R1 вкладки · Start меню",
                    self.SEARCH: "A меню · X новый поиск · L1/R1 вкладки · Start меню · B выход",
                    self.HISTORY: "A продолжить · Y убрать · L1/R1 вкладки · Start меню · B выход",
                    self.DOWNLOADS: "A смотреть · Y удалить · L1/R1 вкладки · Start меню · B выход"}[self.tab]
            col = C_MUTED
        s.blit(get_text(self.font_tiny, fit_text(self.font_tiny, text, WIDTH - 24), col), (12, fy + 6))

    def draw_modal(self):
        s = self.screen
        title, options = self.modal
        s.blit(self.overlay, (0, 0))
        mw = 420
        mh = 50 + len(options) * 42 + 8
        mx, my = (WIDTH - mw) // 2, (HEIGHT - mh) // 2
        pygame.draw.rect(s, C_HEADER, (mx, my, mw, mh), border_radius=10)
        pygame.draw.rect(s, C_BORDER, (mx, my, mw, mh), 2, border_radius=10)
        s.blit(get_text(self.font_main, title, C_TEXT), (mx + 20, my + 15))
        for i, (label, _) in enumerate(options):
            oy = my + 46 + i * 42
            sel = i == self.modal_sel
            pygame.draw.rect(s, C_ACCENT if sel else C_KEY, (mx + 15, oy, mw - 30, 36), border_radius=6)
            t = get_text(self.font_main, label, C_TEXT)
            s.blit(t, (mx + 27, oy + 18 - t.get_height() // 2))

    # ---- main loop ----

    def run(self):
        self.running = True
        while self.running:
            self.process_events()
            self.poll_tasks()
            if self.pending_play:
                self.start_pending_play()
            if (self.tab == self.HOME and self.topic_changed_at
                    and time.time() - self.topic_changed_at > 0.35 and yt_dlp):
                self.topic_changed_at = 0
                self.load_topic(self.topic)
            self.draw()
            self.clock.tick(30)
        pygame.quit()


def main():
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)
    if "--prepare" in sys.argv:
        prepare_ytdlp(print)
        print("yt-dlp", YTDLP_VERSION, "ready:", YTDLP_PYZ)
        return
    signal.signal(signal.SIGTERM, _terminate)
    signal.signal(signal.SIGHUP, _terminate)
    YouTubeApp().run()


if __name__ == "__main__":
    main()
