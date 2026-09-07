# RG40XX H Demos

Нативные демки и порты для Anbernic RG40XX H (Linux ARM, H700, 1GB RAM).

## Структура

```
rg40xx-demos/
├── sdl-demos/        # SDL2 демки (C)
├── raylib-demos/     # Raylib демки (C)
├── quake/            # Quake 1 порт (TyrQuake)
├── doom/             # Doom порт (Chocolate Doom)
├── cave-story/       # Cave Story (NXEngine)
├── supertux/         # SuperTux порт
└── scripts/          # Скрипты сборки и установки
```

## Быстрый старт

```bash
# Клонировать на RG40XX H (или кросс-компилировать)
git clone https://github.com/Miolonixc/rg40xx-demos.git
cd rg40xx-demos

# Собрать SDL2 демку
./scripts/build-sdl-demos.sh

# Установить Quake
./scripts/install-quake.sh
```

## Целевые платформы

- **CPU**: H700 quad-core ARM Cortex-A53 @ 1.5GHz
- **GPU**: Mali G31 MP2
- **RAM**: 1GB LPDDR4
- **OS**: Linux 64-bit (32-bit userland)
- **Экран**: 4" IPS 640x480
- **Ввод**: GPIO-кнопки, аналоговые стики

## Лицензии

Каждая демка сохраняет свою оригинальную лицензию. Скрипты сборки — MIT.
