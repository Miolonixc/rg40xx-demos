# Батарея для RG40XX H (Knulli)

Ограничение заряда на зарядке, корректное выключение при низком заряде и вибрация при подключении зарядки, с приложением в разделе «Инструменты».

## Что входит

| Файл | Куда ставится | Назначение |
| --- | --- | --- |
| `battery-tools` | `/userdata/system/bin/` | Утилита: состояние и все настройки |
| `services/chargelimit` | `/userdata/system/services/` | Держит заряд в диапазоне, пока подключена зарядка |
| `services/lowbattery` | `/userdata/system/services/` | Выключает приставку при низком заряде на батарее |
| `services/chargevibe` | `/userdata/system/services/` | Коротко вибрирует при подключении зарядки |
| `app/battery_app.py`, `app/Battery.sh` | `/userdata/roms/tools/` | Приложение Battery |

Настройки хранятся в `/userdata/system/configs/battery-tools.conf`. Службы перечитывают файл на каждой проверке, поэтому изменения применяются без перезапуска.

## Установка с Mac

```sh
tools/battery/install.sh 192.168.2.173
```

Установщик сохраняет существующие настройки, включает все три службы в автозапуск (`system.services` в `knulli.conf`) и добавляет Battery в `gamelist.xml` раздела «Инструменты». EmulationStation держит списки в памяти и записывает их обратно при перезагрузке, поэтому установщик сначала просит её сохранить списки (`/reloadgames` на порту 1234), затем правит файл и перезагружает списки ещё раз.

## Приложение

Называется Battery и в списке «Инструментов», и в шапке. Интерфейс на английском; пункт **Language / Язык** переключает на русский, выбор хранится в `/userdata/system/configs/battery-app.conf`.

Крестовина выбирает пункт, A меняет его, влево/вправо перебирают значения. Выход — B, Start, Menu или пункт Exit. Номера кнопок приложение берёт из `es_input.cfg` EmulationStation. Запасной вариант — `port-exit-watcher.py`: он закрывает само приложение по Menu или Select+Start. Нажатые кнопки пишутся в `/tmp/battery_app.log`.

- **Ограничение заряда** — вкл/выкл.
- **Диапазон** — 40–60% (хранение, игра на ТВ с кабелем), 50–80% (повседневно), 20–80% (максимум циклов).
- **Зарядить до 100% один раз** — перед поездкой. Действует до полного заряда или отключения кабеля, затем ограничение возвращается само.
- **Выключение при низком заряде** — вкл/выкл, порог 10/15/20/25%.
- **Вибрация при зарядке** — вкл/выкл.

## Утилита

```sh
battery-tools status          # состояние
battery-tools limit off       # on | off | toggle
battery-tools range 50 80
battery-tools full            # один раз до 100%
battery-tools lowbat-percent 20
battery-tools vibrate off     # on | off | toggle
```

## Как работает ограничение

У PMIC AXP2202 (в основном ядре — AXP717) нет sysfs-настройки для запрета зарядки, поэтому `chargelimit` меняет по I2C один бит: бит 1 регистра `0x19` (`MODULE_EN_CONTROL_2`, «зарядка разрешена»). Этот же бит использует драйвер основного ядра Linux. Остальные биты не трогаются.

- На зарядке при заряде ≥ верхней границы зарядка выключается, приставка питается от кабеля.
- При заряде ≤ нижней границы зарядка снова разрешается.
- Без кабеля, при выключенном ограничении и при остановке службы зарядка всегда разрешена.

## Вибрация при подключении зарядки

`chargevibe` раз в секунду читает `axp2202-usb/online` и при переходе 0 → 1 включает вибромотор на 0,3 с через `/sys/class/power_supply/axp2202-battery/moto` (тот же переключатель использует штатный `knulli-rumble`). Зарядка, подключённая уже при загрузке, не вызывает вибрации. Ограничение заряда тоже: пока `chargelimit` держит заряд, `online` остаётся 1. Если кабель болтается, вибрация повторяется не чаще раза в 5 с. Проверить мотор: `/userdata/system/services/chargevibe test`.

Журналы: `/userdata/system/logs/chargelimit.log`, `/userdata/system/logs/lowbattery.log`.

## Удаление

```sh
ssh root@192.168.2.173 'for s in chargelimit lowbattery chargevibe; do knulli-services stop $s; knulli-services disable $s; rm /userdata/system/services/$s; done; rm -r /userdata/system/bin/battery-tools /userdata/system/configs/battery-tools.conf /userdata/system/configs/battery-app.conf /userdata/roms/tools/Battery.sh /userdata/roms/tools/battery /userdata/roms/tools/images/battery.png'
```

Запись в `gamelist.xml` раздела «Инструменты» удаляется вручную; копия до установки — `gamelist.xml.bak-battery-20261027`.
