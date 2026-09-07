# RG40XX H Demos (Knulli OS Edition)

Нативные демки и порты для Anbernic RG40XX H под **Knulli OS 2.173** (Buildroot-based).

## Важно про Knulli OS

Knulli OS — минималистичный Linux на базе Buildroot. Особенности:
- **Нет gcc/make из коробки** — только рантайм-библиотеки
- **Нет apt/dnf** — пакеты через `opkg` (если настроен) или только кросс-компиляция
- **Есть SDL2** — используется для эмуляторов (RetroArch)
- **Нет raylib** — нужно компилировать статически
- **Mali G31** — OpenGL ES 3.0 доступен через libMali

## Варианты запуска

### 1. Кросс-компиляция на хосте (рекомендуется)

```bash
# На x86_64 хосте с установленным arm-linux-gnueabihf toolchain
make CROSS=arm-linux-gnueabihf- PLATFORM=PLATFORM_ANDROID
```

### 2. Статическая сборка raylib

Raylib можно собрать статически и прилинковать к демке — тогда на устройстве не нужны .so файлы.

### 3. Нативная сборка (если есть SDK от Knulli)

Если Knulli предоставляет SDK — можно собирать на устройстве.

## Структура

```
rg40xx-demos/
├── sdl-demos/        # SDL2 демки (работают из коробки на Knulli)
├── raylib-demos/     # Raylib демки (нужна статическая линковка)
├── quake/            # TyrQuake
├── doom/             # Chocolate Doom
├── cave-story/       # NXEngine
└── scripts/          # Скрипты сборки
```

## Быстрый старт на Knulli OS

```bash
# 1. Подключиться по SSH к RG40XX H
ssh root@<ip-rg40xx>

# 2. Скачать демки
cd /tmp
wget https://github.com/Miolonixc/rg40xx-demos/releases/latest/download/rg40xx-sdl-demos.tar.gz
tar xzf rg40xx-sdl-demos.tar.gz

# 3. Запустить SDL2 демку (работает без установки!)
./bouncing-balls
```

## Целевые платформы

- **CPU**: Allwinner H700 quad-core ARM Cortex-A53 @ 1.5GHz
- **GPU**: Mali G31 MP2 (OpenGL ES 3.0)
- **RAM**: 1GB LPDDR4
- **OS**: Knulli OS 2.173 (Buildroot, kernel 4.9.170)
- **Экран**: 4" IPS 640x480
- **Ввод**: GPIO-кнопки, аналоговые стики

## Лицензии

Каждая демка сохраняет свою оригинальную лицензию. Скрипты сборки — MIT.
