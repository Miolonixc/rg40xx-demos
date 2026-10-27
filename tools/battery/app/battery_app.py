#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Battery app for the RG40XX H on Knulli (Tools section).

Shows the battery state and switches the charge limit and the low-battery shutdown through
battery-tools. Works on the handheld screen (640x480) and on a widescreen TV: the layout is
480 units high and its width follows the display, so text is never stretched.

Test mode: --keys down,a,right --screenshot out.png renders those inputs and saves a frame.
"""
import argparse
import os
import subprocess
import sys
import time

os.environ.setdefault("XDG_RUNTIME_DIR", "/var/run")
os.environ.setdefault("SDL_VIDEODRIVER", "mali")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame  # noqa: E402

TOOL = os.environ.get("BATTERY_TOOLS", "/userdata/system/bin/battery-tools")
FONT_BOLD = "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"
FONT_NORMAL = "/usr/share/fonts/dejavu/DejaVuSans.ttf"

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
RANGE_NAMES = {(40, 60): "хранение", (50, 80): "повседневно", (20, 80): "максимум циклов"}
THRESHOLDS = [10, 15, 20, 25]
STATUS_NAMES = {"Charging": "Заряжается", "Discharging": "Разряжается", "Full": "Заряжена",
                "Not charging": "Не заряжается"}
HEALTH_NAMES = {"Good": "хорошее", "Overheat": "перегрев", "Dead": "неисправна",
                "Cold": "переохлаждение"}


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


def duration(seconds):
    if seconds <= 0:
        return "—"
    hours, minutes = seconds // 3600, seconds % 3600 // 60
    return f"{hours} ч {minutes:02d} мин" if hours else f"{minutes} мин"


class BatteryApp:
    def __init__(self, screenshot=None):
        pygame.init()
        pygame.joystick.init()
        self.joysticks = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
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

    # Menu.
    def items(self):
        s = self.state
        limit = s.get("limit_enabled") == "1"
        low, high = number(s, "low", 40), number(s, "high", 60)
        lowbat = s.get("lowbat_enabled") == "1"
        full = s.get("full_once") == "1"
        return [
            ("limit", "Ограничение заряда", "ВКЛ" if limit else "ВЫКЛ", GREEN if limit else MUTED),
            ("range", "Диапазон заряда",
             f"◀ {low}–{high}% · {RANGE_NAMES.get((low, high), 'свой')} ▶", WHITE),
            ("full", "Зарядить до 100% один раз", "ИДЁТ" if full else "НАЖМИТЕ A",
             YELLOW if full else MUTED),
            ("lowbat", "Выключение при низком заряде", "ВКЛ" if lowbat else "ВЫКЛ",
             GREEN if lowbat else MUTED),
            ("percent", "Порог выключения", f"◀ {number(s, 'lowbat_percent', 15)}% ▶", WHITE),
            ("exit", "Выход", "", WHITE),
        ]

    def notify(self, message):
        self.message, self.message_until = message, time.time() + 2.5

    def activate(self, direction=0):
        key = self.items()[self.selected][0]
        s = self.state
        if key == "limit" and not direction:
            run_tool("limit", "toggle")
            self.notify("Ограничение заряда переключено")
        elif key == "range":
            current = (number(s, "low", 40), number(s, "high", 60))
            index = RANGES.index(current) if current in RANGES else -1
            low, high = RANGES[(index + (direction or 1)) % len(RANGES)]
            run_tool("range", str(low), str(high))
            self.notify(f"Диапазон {low}–{high}%")
        elif key == "full" and not direction:
            if s.get("charger") != "1":
                self.notify("Подключите зарядку, затем повторите")
            else:
                run_tool("full")
                self.notify("Зарядка до 100%, потом ограничение вернётся")
        elif key == "lowbat" and not direction:
            run_tool("lowbat", "toggle")
            self.notify("Выключение при низком заряде переключено")
        elif key == "percent":
            current = number(s, "lowbat_percent", 15)
            index = THRESHOLDS.index(current) if current in THRESHOLDS else 1
            value = THRESHOLDS[(index + (direction or 1)) % len(THRESHOLDS)]
            run_tool("lowbat-percent", str(value))
            self.notify(f"Порог выключения {value}%")
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
                # RG40XX H: 0 A, 1 B, 9 Start, 10 Menu (same mapping as the Ports Manager tool).
                if event.button == 0:
                    self.handle("a")
                elif event.button in (1, 9, 10):
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
        name = STATUS_NAMES.get(status, status)
        if s.get("charger") == "1" and s.get("charging_allowed") == "0":
            name = "На кабеле, заряд удерживается"
        elif charging:
            name = "Заряжается ⚡"
        self.text(x + 75, y + 140, name, YELLOW if charging else MUTED, 15, False, "center")

    def draw(self):
        s = self.state
        self.screen.fill(BG)
        w = self.width
        self.rect(0, 0, w, 4, YELLOW)
        self.text(24, 22, "БАТАРЕЯ", WHITE, 30, True)
        self.text(26, 62, "Ограничение заряда и защита от разряда", YELLOW, 13)
        panel_w = 356
        panel_x = w - panel_w - 20
        # Left column (gauge and measurements, 224 wide) centred in the space before the panel.
        left = max(24, (panel_x - 224) / 2)
        self.draw_battery(left + 12, 120, s)
        voltage = number(s, "voltage_uv", 0) / 1e6
        temp = number(s, "temp_decic", 0) / 10
        health = HEALTH_NAMES.get(s.get("health", ""), s.get("health", "?"))
        rows = [("Напряжение", f"{voltage:.2f} В"), ("Температура", f"{temp:.1f} °C"),
                ("Состояние", health)]
        if s.get("status") == "Charging":
            rows.append(("До полного", duration(number(s, "time_to_full_s", 0))))
        elif s.get("charger") != "1":
            rows.append(("До разряда", duration(number(s, "time_to_empty_s", 0))))
        for i, (label, value) in enumerate(rows):
            self.text(left, 320 + i * 24, label, MUTED, 13)
            self.text(left + 224, 320 + i * 24, value, WHITE, 13, False, "right")
        # Right panel: settings.
        self.rect(panel_x, 98, panel_w, 328, PANEL, 8)
        self.rect(panel_x, 98, panel_w, 3, YELLOW)
        self.text(panel_x + 18, 112, "НАСТРОЙКИ", WHITE, 17, True)
        for i, (_, label, value, color) in enumerate(self.items()):
            top = 150 + i * 44
            if i == self.selected:
                self.rect(panel_x + 10, top - 6, panel_w - 20, 40, SELECTED, 6)
                self.rect(panel_x + 10, top - 6, 4, 40, YELLOW, 2)
            self.text(panel_x + 24, top, label, YELLOW if i == self.selected else WHITE, 14)
            if value:
                self.text(panel_x + panel_w - 22, top + 17, value, color, 12, True, "right")
        services = s.get("chargelimit_service") == "1" and s.get("lowbattery_service") == "1"
        if not services:
            self.text(panel_x + 18, 400, "Службы не запущены: настройки применятся после запуска",
                      RED, 10)
        # Footer and notice.
        if time.time() < self.message_until:
            self.rect(w / 2 - 230, 404, 460, 30, BG)
            self.rect(w / 2 - 230, 404, 460, 30, YELLOW, 6, 2)
            self.text(w / 2, 410, self.message, YELLOW, 13, True, "center")
        self.rect(0, 448, w, 32, (9, 13, 18))
        self.text(24, 456, "Крестовина — выбор    A — изменить    ◀ ▶ — значение    B — выход",
                  MUTED, 12)
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
    title = font.render("БАТАРЕЯ", True, WHITE)
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
