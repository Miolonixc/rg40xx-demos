#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chromecast app for the RG40XX H on Knulli (Tools section).

Finds the Chromecast devices (anything Cast with a screen) on the local network, starts and stops
casting the handheld screen and sound to one of them through cast-screen, and holds its settings:
the handheld's own screen and speaker while casting (off turns it into just a gamepad), how the
4:3 picture fits a 16:9 TV, quality, latency and frame rate. Casting keeps running in the
background after the app is closed. Same look and controls as the Battery app; the layout is 480
units high and follows the display width. English with a switch to Russian, kept in cast-app.conf.

Test mode: --keys down,a --screenshot out.png renders those inputs and saves a frame.
"""
import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET

os.environ.setdefault("XDG_RUNTIME_DIR", "/var/run")
os.environ.setdefault("SDL_VIDEODRIVER", "mali")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame  # noqa: E402

TOOL = os.environ.get("CAST_SCREEN", "/userdata/system/bin/cast-screen")
STATE = "/tmp/cast-screen.state"
CAST_CONF = "/userdata/system/cast-screen.conf"
CAST_LOG = "/tmp/cast-screen.log"
FONT_BOLD = "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"
FONT_NORMAL = "/usr/share/fonts/dejavu/DejaVuSans.ttf"
SETTINGS = os.environ.get("CAST_APP_CONF", "/userdata/system/configs/cast-app.conf")
# EmulationStation's controller config gives the SDL button numbers of A, B, X, Start and Menu.
ES_INPUT = ("/userdata/system/configs/emulationstation/es_input.cfg",
            "/usr/share/emulationstation/es_input.cfg")
DEFAULT_BUTTONS = {"a": 3, "b": 4, "x": 6, "start": 10, "hotkey": 11}  # RG40XX H on Knulli.

BG = (14, 19, 26)
PANEL = (24, 32, 43)
SELECTED = (36, 58, 82)
WHITE = (236, 242, 246)
MUTED = (134, 152, 170)
GREEN = (72, 214, 140)
YELLOW = (255, 204, 92)
RED = (240, 96, 82)
CYAN = (70, 200, 240)

LANGUAGES = ["en", "ru"]
# cast-screen settings: values in the order ◀ ▶ walks through them, and the default. Screen and sound
# apply to a running cast at once; the others make cast-screen restart it.
CAST_SETTINGS = {"screen": ["on", "off"], "sound": ["on", "off"], "aspect": ["4:3", "stretch", "zoom"],
            "bitrate": ["2000", "3000", "5000"], "delay": ["150", "250", "400"], "fps": ["30", "25", "20"]}
DEFAULTS = {"screen": "on", "sound": "on", "aspect": "4:3", "bitrate": "3000", "delay": "250", "fps": "30"}
ROWS = 8  # rows visible in the panel

TEXT = {
    "en": {
        "title": "CHROMECAST", "subtitle": "Cast the screen and sound to a TV over Wi-Fi",
        "devices": "DEVICES & SETTINGS", "on": "ON", "off": "OFF", "language_name": "English",
        "searching": "Searching the network…", "none": "No Chromecast found",
        "stop": "Stop casting", "rescan": "Search again",
        "screen": "Handheld screen", "sound": "Handheld sound", "aspect": "Picture on TV",
        "bitrate": "Quality", "delay": "Latency", "fps": "Frame rate",
        "keep": "ON", "off_casting": "OFF while casting",
        "aspect_values": {"4:3": "4:3 as is", "stretch": "Stretch to 16:9", "zoom": "Zoom to 16:9"},
        "bitrate_value": "{mbit} Mbit/s", "fps_value": "{fps} fps",
        "delay_values": {"150": "150 ms · low", "250": "250 ms · normal", "400": "400 ms · smoothest"},
        "language": "Language / Язык", "exit": "Exit",
        "casting_here": "● CASTING", "default": "last used",
        "casting": "Casting", "idle": "Not casting", "connecting": "Connecting…",
        "for": "for {time}", "handheld_off": "Handheld: {what} off",
        "screen_word": "screen", "sound_word": "sound", "and": " and ",
        "minutes": "{m} min", "hours": "{h} h {m:02d} min", "seconds": "{s} s",
        "connecting_to": "Connecting to {name}…", "now_casting": "Casting to {name}",
        "failed": "Could not connect: {reason}", "stopped": "Casting stopped",
        "restarting": "Casting restarts with the new setting…",
        "saved": "Saved, used on the next cast",
        "footer": "D-pad — select    A — cast / change    X — search    B — exit",
    },
    "ru": {
        "title": "CHROMECAST", "subtitle": "Экран и звук на телевизор по Wi-Fi",
        "devices": "УСТРОЙСТВА И НАСТРОЙКИ", "on": "ВКЛ", "off": "ВЫКЛ", "language_name": "Русский",
        "searching": "Поиск в сети…", "none": "Chromecast не найден",
        "stop": "Остановить трансляцию", "rescan": "Искать снова",
        "screen": "Экран приставки", "sound": "Звук приставки", "aspect": "Картинка на ТВ",
        "bitrate": "Качество", "delay": "Задержка", "fps": "Частота кадров",
        "keep": "ВКЛ", "off_casting": "ВЫКЛ при трансляции",
        "aspect_values": {"4:3": "4:3 как есть", "stretch": "Растянуть на 16:9",
                          "zoom": "Приблизить до 16:9"},
        "bitrate_value": "{mbit} Мбит/с", "fps_value": "{fps} к/с",
        "delay_values": {"150": "150 мс · низкая", "250": "250 мс · обычная", "400": "400 мс · плавнее"},
        "language": "Language / Язык", "exit": "Выход",
        "casting_here": "● ТРАНСЛЯЦИЯ", "default": "последний",
        "casting": "Трансляция", "idle": "Трансляции нет", "connecting": "Подключение…",
        "for": "уже {time}", "handheld_off": "На приставке выключен {what}",
        "screen_word": "экран", "sound_word": "звук", "and": " и ",
        "minutes": "{m} мин", "hours": "{h} ч {m:02d} мин", "seconds": "{s} с",
        "connecting_to": "Подключение к {name}…", "now_casting": "Трансляция на {name}",
        "failed": "Не удалось подключиться: {reason}", "stopped": "Трансляция остановлена",
        "restarting": "Трансляция перезапускается с новой настройкой…",
        "saved": "Сохранено, применится при следующей трансляции",
        "footer": "Крестовина — выбор    A — транслировать / изменить    X — поиск    B — выход",
    },
}


def load_language():
    try:
        with open(SETTINGS, encoding="utf-8") as settings:
            for line in settings:
                key, _, value = line.strip().partition("=")
                if key == "LANGUAGE" and value in LANGUAGES:
                    return value
    except OSError:
        pass
    return "en"


def save_language(language):
    try:
        os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
        with open(SETTINGS + ".tmp", "w", encoding="utf-8") as settings:
            settings.write(f"LANGUAGE={language}\n")
        os.replace(SETTINGS + ".tmp", SETTINGS)
    except OSError:
        pass


def button_map(device_name):
    """SDL button numbers for A, B, X, Start and Menu from EmulationStation's controller config."""
    for path in ES_INPUT:
        try:
            root = ET.parse(path).getroot()
        except (OSError, ET.ParseError):
            continue
        for config in root.iter("inputConfig"):
            if config.get("deviceName") != device_name:
                continue
            ids = {node.get("name"): int(node.get("id")) for node in config.iter("input")
                   if node.get("type") == "button" and (node.get("id") or "").isdigit()}
            if "a" in ids and "b" in ids:
                return {name: ids.get(name, number) for name, number in DEFAULT_BUTTONS.items()}
    return dict(DEFAULT_BUTTONS)


def cast_state():
    """The running cast from cast-screen's state file, or None (also while it is still connecting)."""
    try:
        with open(STATE) as f:
            state = json.load(f)
        os.kill(state["pid"], 0)
        return None if state.get("connecting") else state
    except (OSError, ValueError, KeyError, TypeError):
        return None


def cast_conf():
    conf = {}
    try:
        with open(CAST_CONF) as f:
            for line in f:
                key, sep, value = line.strip().partition("=")
                if sep:
                    conf[key] = value
    except OSError:
        pass
    return conf


def cast_settings(conf):
    if conf.get("gamepad") == "on":  # older single switch for both
        conf = dict(conf, screen=conf.get("screen", "off"), sound=conf.get("sound", "off"))
    return {key: conf.get(key) if conf.get(key) in values else DEFAULTS[key]
            for key, values in CAST_SETTINGS.items()}


JOBS = queue.Queue()


def run_background(*args):
    """cast-screen calls that may take seconds (starting, restarting a cast) without freezing the UI,
    one after another so two restarts never overlap."""
    JOBS.put(args)


def _worker():
    while True:
        args = JOBS.get()
        run_tool(*args)


threading.Thread(target=_worker, daemon=True).start()


def last_error():
    """The reason from the end of the cast log, for a failed connection."""
    try:
        with open(CAST_LOG, errors="replace") as f:
            lines = [l.strip() for l in f.read().replace("\0", "").splitlines() if l.strip()]
    except OSError:
        return "?"
    for line in reversed(lines):
        if "Error" in line or "not found" in line or "refused" in line or "rejected" in line:
            return line.split(": ", 1)[-1][:60]
    return lines[-1][:60] if lines else "?"


def run_tool(*args):
    try:
        return subprocess.run([TOOL, *args], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def duration(text, seconds):
    seconds = max(0, int(seconds))
    if seconds < 60:
        return text["seconds"].format(s=seconds)
    hours, minutes = seconds // 3600, seconds % 3600 // 60
    return text["hours"].format(h=hours, m=minutes) if hours else text["minutes"].format(m=minutes)


class CastApp:
    def __init__(self, screenshot=None):
        pygame.init()
        pygame.joystick.init()
        self.joysticks = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
        self.buttons = button_map(self.joysticks[0].get_name() if self.joysticks else "")
        self.language = load_language()
        self.offscreen = bool(screenshot)
        if self.offscreen:  # Knulli's SDL has no dummy/offscreen video driver; draw in memory.
            self.screen = pygame.Surface((640, 480))
        else:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            pygame.mouse.set_visible(False)
        width, height = self.screen.get_size()
        self.scale = height / 480
        self.width = width / self.scale  # Layout width in 480-high units.
        self.fonts = {}
        self.devices, self.scanning = [], False
        self.state, self.conf = cast_state(), cast_conf()
        self.refreshed = time.time()
        self.pending = None  # (device name, deadline, start time of the cast it replaces) while connecting
        self.selected, self.top = 0, 0
        self.message, self.message_until = "", 0
        self.running = True
        self.last_axis = 0

    # Layout helpers in 480-high units.
    def px(self, value):
        return int(round(value * self.scale))

    def font(self, size, bold=False):
        key = (size, bold)
        if key not in self.fonts:
            self.fonts[key] = pygame.font.Font(FONT_BOLD if bold else FONT_NORMAL, self.px(size))
        return self.fonts[key]

    def text(self, x, y, value, color=WHITE, size=16, bold=False, align="left", width=None):
        font = self.font(size, bold)
        if width is not None:  # cut long device names to fit
            while value and font.size(value)[0] > self.px(width):
                value = value[:-2] + "…"
        surface = font.render(value, True, color)
        left = self.px(x)
        if align == "right":
            left -= surface.get_width()
        elif align == "center":
            left -= surface.get_width() // 2
        self.screen.blit(surface, (left, self.px(y)))

    def rect(self, x, y, w, h, color, radius=0, border=0):
        pygame.draw.rect(self.screen, color, (self.px(x), self.px(y), self.px(w), self.px(h)),
                         border, border_radius=self.px(radius))

    @property
    def t(self):
        return TEXT[self.language]

    # State.
    def scan(self, wait=False):
        def work():
            out = run_tool("list", "--raw")
            self.devices = [tuple(line.split("\t")) for line in out.splitlines() if line.count("\t") == 2]
            self.scanning = False
        if not self.scanning:
            self.scanning = True
            if wait:
                work()
            else:
                threading.Thread(target=work, daemon=True).start()

    def refresh(self):
        self.state, self.conf = cast_state(), cast_conf()
        self.refreshed = time.time()
        if self.pending:
            name, deadline, replaced = self.pending
            if self.state and self.state.get("device") == name and self.state.get("since") != replaced:
                self.pending = None
                self.notify(self.t["now_casting"].format(name=name))
            elif time.time() > deadline:
                self.pending = None
                self.notify(self.t["failed"].format(reason=last_error()), 6)

    # Menu.
    def items(self):
        t, state = self.t, self.state
        casting_to = state.get("device") if state else None
        rows = []
        for name, model, ip in self.devices:
            if name == casting_to:
                value, color = t["casting_here"], GREEN
            elif self.pending and self.pending[0] == name:
                value, color = t["connecting"], YELLOW
            elif name == self.conf.get("device"):
                value, color = t["default"], CYAN
            else:
                value, color = model, MUTED
            rows.append(("device", name, value, color, name))
        if self.scanning:
            rows.append(("info", t["searching"], "", MUTED, None))
        elif not self.devices:
            rows.append(("info", t["none"], "", MUTED, None))
        if state:
            rows.append(("stop", t["stop"], "", RED, None))
        conf = cast_settings(self.conf)
        for key in ("screen", "sound"):
            off = conf[key] == "off"
            rows.append((key, t[key], t["off_casting"] if off else t["keep"], YELLOW if off else GREEN, None))
        rows.append(("aspect", t["aspect"], "◀ %s ▶" % t["aspect_values"][conf["aspect"]], CYAN, None))
        rows.append(("bitrate", t["bitrate"],
                     "◀ %s ▶" % t["bitrate_value"].format(mbit=int(conf["bitrate"]) // 1000), CYAN, None))
        rows.append(("delay", t["delay"], "◀ %s ▶" % t["delay_values"][conf["delay"]], CYAN, None))
        rows.append(("fps", t["fps"], "◀ %s ▶" % t["fps_value"].format(fps=conf["fps"]), CYAN, None))
        rows.append(("rescan", t["rescan"], "X", MUTED, None))
        rows.append(("language", t["language"], f"◀ {t['language_name']} ▶", CYAN, None))
        rows.append(("exit", t["exit"], "", WHITE, None))
        return rows

    def notify(self, message, seconds=3):
        self.message, self.message_until = message, time.time() + seconds

    def activate(self, direction=0):
        items = self.items()
        self.selected = min(self.selected, len(items) - 1)
        key, _, _, _, name = items[self.selected]
        t = self.t
        if key == "device" and not direction:
            run_tool("set", "device", name)
            run_background("background", name)  # stops a running cast first
            self.pending = (name, time.time() + 25, self.state and self.state.get("since"))
            self.notify(t["connecting_to"].format(name=name), 25)
        elif key == "stop" and not direction:
            run_background("stop")
            self.pending = None
            self.notify(t["stopped"])
        elif key in CAST_SETTINGS:
            values = CAST_SETTINGS[key]
            value = values[(values.index(cast_settings(self.conf)[key]) + (direction or 1)) % len(values)]
            self.conf = dict(self.conf, **{key: value})  # shown at once; cast-screen saves it
            run_background("set", key, value)
            if key not in ("screen", "sound"):
                if self.state:
                    self.pending = (self.state["device"], time.time() + 25, self.state.get("since"))
                self.notify(t["restarting"] if self.state else t["saved"], 4)
            return
        elif key == "rescan" and not direction:
            self.scan()
        elif key == "language":
            index = LANGUAGES.index(self.language)
            self.language = LANGUAGES[(index + (direction or 1)) % len(LANGUAGES)]
            save_language(self.language)
        elif key == "exit" and not direction:
            self.running = False
        self.refresh()

    def handle(self, action):
        count = len(self.items())
        if action == "up":
            self.selected = (self.selected - 1) % count
        elif action == "down":
            self.selected = (self.selected + 1) % count
        elif action == "left":
            self.activate(-1)
        elif action == "right":
            self.activate(1)
        elif action == "a":
            self.activate()
        elif action == "x":
            self.scan()
        elif action == "b":
            self.running = False

    def poll(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                keys = {pygame.K_UP: "up", pygame.K_DOWN: "down", pygame.K_LEFT: "left",
                        pygame.K_RIGHT: "right", pygame.K_RETURN: "a", pygame.K_SPACE: "a",
                        pygame.K_x: "x", pygame.K_ESCAPE: "b", pygame.K_BACKSPACE: "b"}
                if event.key in keys:
                    self.handle(keys[event.key])
            elif event.type == pygame.JOYBUTTONDOWN:
                buttons = self.buttons
                if event.button == buttons["a"]:
                    self.handle("a")
                elif event.button == buttons["x"]:
                    self.handle("x")
                elif event.button in (buttons["b"], buttons["start"], buttons["hotkey"]):
                    self.handle("b")
            elif event.type == pygame.JOYHATMOTION:
                x, y = event.value
                if y > 0:
                    self.handle("up")
                elif y < 0:
                    self.handle("down")
                elif x < 0:
                    self.handle("left")
                elif x > 0:
                    self.handle("right")
        if self.joysticks:
            axis = self.joysticks[0].get_axis(1)
            now = time.time()
            if abs(axis) > .6 and now - self.last_axis > .2:
                self.handle("up" if axis < 0 else "down")
                self.last_axis = now

    # Drawing.
    def draw_tv(self, x, y, casting):
        color = GREEN if casting else MUTED
        self.rect(x, y, 170, 108, color, 10, 4)
        self.rect(x + 60, y + 108, 50, 8, color)
        self.rect(x + 40, y + 116, 90, 6, color, 3)
        # cast symbol in the corner of the screen: three arcs and a dot
        cx, cy = self.px(x + 26), self.px(y + 86)
        for r in (14, 26, 38) if casting else (14,):
            pygame.draw.arc(self.screen, color, (cx - self.px(r), cy - self.px(r), self.px(2 * r), self.px(2 * r)),
                            0, 1.5708, self.px(4))
        pygame.draw.circle(self.screen, color, (cx, cy), self.px(5))

    def draw(self):
        t, state = self.t, self.state
        self.screen.fill(BG)
        w = self.width
        self.rect(0, 0, w, 4, CYAN)
        self.text(24, 22, t["title"], WHITE, 30, True)
        self.text(26, 62, t["subtitle"], CYAN, 13)
        panel_w = 356
        panel_x = w - panel_w - 20
        left = max(20, (panel_x - 200) / 2)
        self.draw_tv(left + 15, 120, bool(state))
        if state:
            self.text(left + 100, 262, t["casting"], GREEN, 22, True, "center")
            self.text(left + 100, 294, state.get("device", "?"), WHITE, 15, True, "center", 200)
            self.text(left + 100, 318, t["for"].format(time=duration(t, time.time() - state.get("since", 0))),
                      MUTED, 13, False, "center")
            off = [t[key + "_word"] for key in ("screen", "sound") if state.get(key) == "off"]
            if off:
                self.text(left + 100, 350, t["handheld_off"].format(what=t["and"].join(off)), YELLOW, 11,
                          False, "center", 210)
        elif self.pending:
            self.text(left + 100, 262, t["connecting"], YELLOW, 22, True, "center")
            self.text(left + 100, 294, self.pending[0], WHITE, 15, True, "center", 200)
        else:
            self.text(left + 100, 262, t["idle"], MUTED, 20, True, "center")
        # Right panel: devices and settings.
        self.rect(panel_x, 98, panel_w, 340, PANEL, 8)
        self.rect(panel_x, 98, panel_w, 3, CYAN)
        self.text(panel_x + 18, 110, t["devices"], WHITE, 17, True)
        items = self.items()
        self.selected = min(self.selected, len(items) - 1)
        self.top = max(min(self.top, self.selected), self.selected - ROWS + 1, 0)
        for i, (key, label, value, color, _) in enumerate(items[self.top:self.top + ROWS]):
            index = self.top + i
            top = 140 + i * 35
            if index == self.selected:
                self.rect(panel_x + 10, top - 3, panel_w - 20, 33, SELECTED, 6)
                self.rect(panel_x + 10, top - 3, 4, 33, CYAN, 2)
            label_color = CYAN if index == self.selected else (MUTED if key == "info" else WHITE)
            self.text(panel_x + 24, top, label, label_color, 14, key == "device", width=190)
            if value:
                self.text(panel_x + panel_w - 22, top + 15, value, color, 11, True, "right", 200)
        if self.top + ROWS < len(items):
            self.text(panel_x + panel_w / 2, 420, "▼", MUTED, 12, False, "center")
        # Footer and notice.
        if time.time() < self.message_until:
            self.rect(w / 2 - 290, 404, 580, 30, BG)
            self.rect(w / 2 - 290, 404, 580, 30, CYAN, 6, 2)
            self.text(w / 2, 410, self.message, CYAN, 12, True, "center", 560)
        self.rect(0, 448, w, 32, (9, 13, 18))
        self.text(24, 456, t["footer"], MUTED, 11, width=w - 40)
        if not self.offscreen:
            pygame.display.flip()

    def run(self, keys=None, screenshot=None):
        clock = pygame.time.Clock()
        self.scan(wait=bool(screenshot))
        for action in keys or []:
            self.handle(action)
        if screenshot:
            self.message_until = time.time() + 5 if self.message else 0
            self.draw()
            pygame.image.save(self.screen, screenshot)
            return
        while self.running:
            self.poll()
            if time.time() - self.refreshed > 1:
                self.refresh()
            self.draw()
            clock.tick(20)


def render_icon(path):
    """Gamelist image for EmulationStation: a TV with the cast symbol."""
    pygame.font.init()
    surface = pygame.Surface((480, 360))
    surface.fill(BG)
    pygame.draw.rect(surface, CYAN, (0, 0, 480, 8))
    pygame.draw.rect(surface, WHITE, (110, 70, 260, 160), 7, border_radius=16)
    pygame.draw.rect(surface, WHITE, (205, 230, 70, 12))
    pygame.draw.rect(surface, WHITE, (170, 242, 140, 9), border_radius=4)
    cx, cy = 150, 200
    for r in (20, 38, 56):
        pygame.draw.arc(surface, CYAN, (cx - r, cy - r, 2 * r, 2 * r), 0, 1.5708, 7)
    pygame.draw.circle(surface, CYAN, (cx, cy), 8)
    font = pygame.font.Font(FONT_BOLD, 44)
    title = font.render("CHROMECAST", True, WHITE)
    surface.blit(title, ((480 - title.get_width()) // 2, 276))
    pygame.image.save(surface, path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keys", default="", help="Test: comma-separated up,down,left,right,a,x,b")
    parser.add_argument("--screenshot", help="Test: render once into this PNG and exit")
    parser.add_argument("--icon", help="Write the gamelist image to this PNG and exit")
    options = parser.parse_args()
    if options.icon:
        render_icon(options.icon)
        return
    app = CastApp(options.screenshot)
    try:
        app.run([k for k in options.keys.split(",") if k], options.screenshot)
    finally:
        pygame.quit()


if __name__ == "__main__":
    sys.exit(main())
