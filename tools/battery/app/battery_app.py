#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Battery app for the RG40XX H on Knulli (Tools section).

Shows the battery state and switches the charge limit and the low-battery shutdown through
battery-tools. Works on the handheld screen (640x480) and on a widescreen TV: the layout is
480 units high and its width follows the display, so text is never stretched. The interface is
in English with a switch to Russian; the choice is kept in battery-app.conf.

Test mode: --keys down,a,right --screenshot out.png renders those inputs and saves a frame.
"""
import argparse
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

os.environ.setdefault("XDG_RUNTIME_DIR", "/var/run")
os.environ.setdefault("SDL_VIDEODRIVER", "mali")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame  # noqa: E402

TOOL = os.environ.get("BATTERY_TOOLS", "/userdata/system/bin/battery-tools")
FONT_BOLD = "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"
FONT_NORMAL = "/usr/share/fonts/dejavu/DejaVuSans.ttf"
SETTINGS = os.environ.get("BATTERY_APP_CONF", "/userdata/system/configs/battery-app.conf")
# EmulationStation's controller config gives the SDL button numbers of A, B, Start and Menu.
ES_INPUT = ("/userdata/system/configs/emulationstation/es_input.cfg",
            "/usr/share/emulationstation/es_input.cfg")
DEFAULT_BUTTONS = {"a": 3, "b": 4, "start": 10, "hotkey": 11}  # RG40XX H on Knulli.

BG = (14, 19, 26)
PANEL = (24, 32, 43)
SELECTED = (36, 58, 82)
LINE = (44, 58, 76)
WHITE = (236, 242, 246)
MUTED = (134, 152, 170)
GREEN = (72, 214, 140)
YELLOW = (255, 204, 92)
RED = (240, 96, 82)
CYAN = (70, 200, 240)

RANGES = [(40, 60), (50, 80), (20, 80)]
THRESHOLDS = [10, 15, 20, 25]
LANGUAGES = ["en", "ru"]

TEXT = {
    "en": {
        "title": "BATTERY", "subtitle": "Charge limit and low-battery protection",
        "settings": "SETTINGS", "on": "ON", "off": "OFF", "language_name": "English",
        "limit": "Charge limit", "range": "Charge range", "full": "Charge to 100% once",
        "full_active": "ACTIVE", "full_press": "PRESS A", "lowbat": "Low-battery shutdown",
        "percent": "Shutdown threshold", "language": "Language / Язык", "exit": "Exit",
        "storage": "storage", "everyday": "everyday", "cycles": "max cycles", "custom": "custom",
        "limit_toggled": "Charge limit switched", "range_set": "Range {low}–{high}%",
        "plug_in": "Plug in the charger, then try again",
        "full_set": "Charging to 100%, then the limit comes back",
        "lowbat_toggled": "Low-battery shutdown switched",
        "percent_set": "Shutdown threshold {value}%",
        "voltage": "Voltage", "temperature": "Temperature", "health": "Health",
        "to_full": "Time to full", "to_empty": "Time left", "volts": "V",
        "hours": "{h} h {m:02d} min", "minutes": "{m} min",
        "held": "On cable, charge held", "charging": "Charging ⚡",
        "services_off": "Services are not running: settings apply once they start",
        "footer": "D-pad — select    A — change    ◀ ▶ — value    B — exit",
        "status": {"Charging": "Charging", "Discharging": "Discharging", "Full": "Full",
                   "Not charging": "Not charging"},
        "health_names": {"Good": "good", "Overheat": "overheat", "Dead": "dead",
                         "Cold": "cold"},
    },
    "ru": {
        "title": "BATTERY", "subtitle": "Ограничение заряда и защита от разряда",
        "settings": "НАСТРОЙКИ", "on": "ВКЛ", "off": "ВЫКЛ", "language_name": "Русский",
        "limit": "Ограничение заряда", "range": "Диапазон заряда",
        "full": "Зарядить до 100% один раз", "full_active": "ИДЁТ", "full_press": "НАЖМИТЕ A",
        "lowbat": "Выключение при низком заряде", "percent": "Порог выключения",
        "language": "Language / Язык", "exit": "Выход",
        "storage": "хранение", "everyday": "повседневно", "cycles": "максимум циклов",
        "custom": "свой",
        "limit_toggled": "Ограничение заряда переключено", "range_set": "Диапазон {low}–{high}%",
        "plug_in": "Подключите зарядку, затем повторите",
        "full_set": "Зарядка до 100%, потом ограничение вернётся",
        "lowbat_toggled": "Выключение при низком заряде переключено",
        "percent_set": "Порог выключения {value}%",
        "voltage": "Напряжение", "temperature": "Температура", "health": "Состояние",
        "to_full": "До полного", "to_empty": "До разряда", "volts": "В",
        "hours": "{h} ч {m:02d} мин", "minutes": "{m} мин",
        "held": "На кабеле, заряд удерживается", "charging": "Заряжается ⚡",
        "services_off": "Службы не запущены: настройки применятся после запуска",
        "footer": "Крестовина — выбор    A — изменить    ◀ ▶ — значение    B — выход",
        "status": {"Charging": "Заряжается", "Discharging": "Разряжается", "Full": "Заряжена",
                   "Not charging": "Не заряжается"},
        "health_names": {"Good": "хорошее", "Overheat": "перегрев", "Dead": "неисправна",
                         "Cold": "переохлаждение"},
    },
}
RANGE_NAMES = {(40, 60): "storage", (50, 80): "everyday", (20, 80): "cycles"}


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
    """SDL button numbers for A, B, Start and Menu from EmulationStation's controller config."""
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


def read_state():
    try:
        out = subprocess.run([TOOL, "status", "--raw"], capture_output=True, text=True,
                             timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return {}
    return dict(line.split("=", 1) for line in out.splitlines() if "=" in line)


def run_tool(*args):
    try:
        result = subprocess.run([TOOL, *args], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def number(state, key, default=0):
    try:
        return int(state.get(key, default))
    except ValueError:
        return default


def duration(text, seconds):
    if seconds <= 0:
        return "—"
    hours, minutes = seconds // 3600, seconds % 3600 // 60
    return text["hours"].format(h=hours, m=minutes) if hours else text["minutes"].format(m=minutes)


class BatteryApp:
    def __init__(self, screenshot=None):
        pygame.init()
        pygame.joystick.init()
        self.joysticks = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
        self.buttons = button_map(self.joysticks[0].get_name() if self.joysticks else "")
        print("Buttons", self.buttons, file=sys.stderr)
        self.language = load_language()
        self.offscreen = bool(screenshot)
        if self.offscreen:  # Knulli's SDL has no dummy/offscreen video driver; draw in memory.
            self.screen = pygame.Surface((1280, 720))
        else:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            pygame.mouse.set_visible(False)
        width, height = self.screen.get_size()
        self.scale = height / 480
        self.width = width / self.scale  # Layout width in 480-high units.
        self.fonts = {}
        self.state = read_state()
        self.refreshed = time.time()
        self.selected = 0
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

    def text(self, x, y, value, color=WHITE, size=16, bold=False, align="left"):
        surface = self.font(size, bold).render(value, True, color)
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

    # Menu.
    def items(self):
        s, t = self.state, self.t
        limit = s.get("limit_enabled") == "1"
        low, high = number(s, "low", 40), number(s, "high", 60)
        lowbat = s.get("lowbat_enabled") == "1"
        full = s.get("full_once") == "1"
        range_name = t[RANGE_NAMES.get((low, high), "custom")]
        return [
            ("limit", t["limit"], t["on"] if limit else t["off"], GREEN if limit else MUTED),
            ("range", t["range"], f"◀ {low}–{high}% · {range_name} ▶", WHITE),
            ("full", t["full"], t["full_active"] if full else t["full_press"],
             YELLOW if full else MUTED),
            ("lowbat", t["lowbat"], t["on"] if lowbat else t["off"], GREEN if lowbat else MUTED),
            ("percent", t["percent"], f"◀ {number(s, 'lowbat_percent', 15)}% ▶", WHITE),
            ("language", t["language"], f"◀ {t['language_name']} ▶", CYAN),
            ("exit", t["exit"], "", WHITE),
        ]

    def notify(self, message):
        self.message, self.message_until = message, time.time() + 2.5

    def activate(self, direction=0):
        key = self.items()[self.selected][0]
        s, t = self.state, self.t
        if key == "limit" and not direction:
            run_tool("limit", "toggle")
            self.notify(t["limit_toggled"])
        elif key == "range":
            current = (number(s, "low", 40), number(s, "high", 60))
            index = RANGES.index(current) if current in RANGES else -1
            low, high = RANGES[(index + (direction or 1)) % len(RANGES)]
            run_tool("range", str(low), str(high))
            self.notify(t["range_set"].format(low=low, high=high))
        elif key == "full" and not direction:
            if s.get("charger") != "1":
                self.notify(t["plug_in"])
            else:
                run_tool("full")
                self.notify(t["full_set"])
        elif key == "lowbat" and not direction:
            run_tool("lowbat", "toggle")
            self.notify(t["lowbat_toggled"])
        elif key == "percent":
            current = number(s, "lowbat_percent", 15)
            index = THRESHOLDS.index(current) if current in THRESHOLDS else 1
            value = THRESHOLDS[(index + (direction or 1)) % len(THRESHOLDS)]
            run_tool("lowbat-percent", str(value))
            self.notify(t["percent_set"].format(value=value))
        elif key == "language":
            index = LANGUAGES.index(self.language)
            self.language = LANGUAGES[(index + (direction or 1)) % len(LANGUAGES)]
            save_language(self.language)
        elif key == "exit" and not direction:
            self.running = False
        self.state = read_state()
        self.refreshed = time.time()

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
        elif action == "b":
            self.running = False

    def poll(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                keys = {pygame.K_UP: "up", pygame.K_DOWN: "down", pygame.K_LEFT: "left",
                        pygame.K_RIGHT: "right", pygame.K_RETURN: "a", pygame.K_SPACE: "a",
                        pygame.K_ESCAPE: "b", pygame.K_BACKSPACE: "b"}
                if event.key in keys:
                    self.handle(keys[event.key])
            elif event.type == pygame.JOYBUTTONDOWN:
                print("Button", event.button, file=sys.stderr)
                buttons = self.buttons
                if event.button == buttons["a"]:
                    self.handle("a")
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
    def draw_battery(self, x, y, s):
        capacity = max(0, min(100, number(s, "capacity", 0)))
        charging = s.get("status") == "Charging"
        color = RED if capacity <= 15 else (YELLOW if capacity <= 30 else GREEN)
        self.rect(x, y, 150, 72, WHITE, 10, 3)
        self.rect(x + 150, y + 22, 9, 28, WHITE, 3)
        if capacity:
            self.rect(x + 7, y + 7, 136 * capacity / 100, 58, color, 6)
        limit = s.get("limit_enabled") == "1" and s.get("full_once") != "1"
        if limit:
            for mark in (number(s, "low", 40), number(s, "high", 60)):
                self.rect(x + 7 + 136 * mark / 100 - 1, y + 3, 2, 66, CYAN)
        self.text(x + 75, y + 84, f"{capacity}%", WHITE, 40, True, "center")
        status = s.get("status", "?")
        name = self.t["status"].get(status, status)
        if s.get("charger") == "1" and s.get("charging_allowed") == "0":
            name = self.t["held"]
        elif charging:
            name = self.t["charging"]
        self.text(x + 75, y + 140, name, YELLOW if charging else MUTED, 15, False, "center")

    def draw(self):
        s, t = self.state, self.t
        self.screen.fill(BG)
        w = self.width
        self.rect(0, 0, w, 4, YELLOW)
        self.text(24, 22, t["title"], WHITE, 30, True)
        self.text(26, 62, t["subtitle"], YELLOW, 13)
        panel_w = 356
        panel_x = w - panel_w - 20
        # Left column (gauge and measurements, 224 wide) centred in the space before the panel.
        left = max(24, (panel_x - 224) / 2)
        self.draw_battery(left + 12, 120, s)
        voltage = number(s, "voltage_uv", 0) / 1e6
        temp = number(s, "temp_decic", 0) / 10
        health = t["health_names"].get(s.get("health", ""), s.get("health", "?"))
        rows = [(t["voltage"], f"{voltage:.2f} {t['volts']}"),
                (t["temperature"], f"{temp:.1f} °C"), (t["health"], health)]
        if s.get("status") == "Charging":
            rows.append((t["to_full"], duration(t, number(s, "time_to_full_s", 0))))
        elif s.get("charger") != "1":
            rows.append((t["to_empty"], duration(t, number(s, "time_to_empty_s", 0))))
        for i, (label, value) in enumerate(rows):
            self.text(left, 320 + i * 24, label, MUTED, 13)
            self.text(left + 224, 320 + i * 24, value, WHITE, 13, False, "right")
        # Right panel: settings.
        self.rect(panel_x, 98, panel_w, 340, PANEL, 8)
        self.rect(panel_x, 98, panel_w, 3, YELLOW)
        self.text(panel_x + 18, 110, t["settings"], WHITE, 17, True)
        for i, (_, label, value, color) in enumerate(self.items()):
            top = 142 + i * 40
            if i == self.selected:
                self.rect(panel_x + 10, top - 5, panel_w - 20, 37, SELECTED, 6)
                self.rect(panel_x + 10, top - 5, 4, 37, YELLOW, 2)
            self.text(panel_x + 24, top, label, YELLOW if i == self.selected else WHITE, 14)
            if value:
                self.text(panel_x + panel_w - 22, top + 15, value, color, 12, True, "right")
        services = s.get("chargelimit_service") == "1" and s.get("lowbattery_service") == "1"
        if not services:
            self.text(panel_x + 18, 424, t["services_off"], RED, 10)
        # Footer and notice.
        if time.time() < self.message_until:
            self.rect(w / 2 - 230, 404, 460, 30, BG)
            self.rect(w / 2 - 230, 404, 460, 30, YELLOW, 6, 2)
            self.text(w / 2, 410, self.message, YELLOW, 13, True, "center")
        self.rect(0, 448, w, 32, (9, 13, 18))
        self.text(24, 456, t["footer"], MUTED, 12)
        if not self.offscreen:
            pygame.display.flip()

    def run(self, keys=None, screenshot=None):
        clock = pygame.time.Clock()
        for action in keys or []:
            self.handle(action)
        if screenshot:
            self.message_until = time.time() + 5 if self.message else 0
            self.draw()
            pygame.image.save(self.screen, screenshot)
            return
        while self.running:
            self.poll()
            if time.time() - self.refreshed > 2:
                self.state = read_state()
                self.refreshed = time.time()
            self.draw()
            clock.tick(20)


def render_icon(path):
    """Gamelist image for EmulationStation: a battery held between the limit marks."""
    pygame.font.init()
    surface = pygame.Surface((480, 360))
    surface.fill(BG)
    pygame.draw.rect(surface, YELLOW, (0, 0, 480, 8))
    pygame.draw.rect(surface, WHITE, (90, 110, 270, 130), 6, border_radius=16)
    pygame.draw.rect(surface, WHITE, (360, 150, 18, 50), border_radius=5)
    pygame.draw.rect(surface, GREEN, (104, 124, 242 * .55, 102), border_radius=10)
    for mark in (.4, .6):
        pygame.draw.rect(surface, CYAN, (104 + 242 * mark - 2, 116, 4, 118))
    font = pygame.font.Font(FONT_BOLD, 46)
    title = font.render("BATTERY", True, WHITE)
    surface.blit(title, ((480 - title.get_width()) // 2, 268))
    pygame.image.save(surface, path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keys", default="", help="Test: comma-separated up,down,left,right,a,b")
    parser.add_argument("--screenshot", help="Test: render once into this PNG and exit")
    parser.add_argument("--icon", help="Write the gamelist image to this PNG and exit")
    options = parser.parse_args()
    if options.icon:
        render_icon(options.icon)
        return
    app = BatteryApp(options.screenshot)
    try:
        app.run([k for k in options.keys.split(",") if k], options.screenshot)
    finally:
        pygame.quit()


if __name__ == "__main__":
    sys.exit(main())
