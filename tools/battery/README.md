# Батарея для RG40XX H (Knulli)

Ограничение заряда на зарядке и корректное выключение при низком заряде, с приложением в разделе «Инструменты».

## Что входит

| Файл | Куда ставится | Назначение |
| --- | --- | --- |
| `battery-tools` | `/userdata/system/bin/` | Утилита: состояние и все настройки |
| `services/chargelimit` | `/userdata/system/services/` | Держит заряд в диапазоне, пока подключена зарядка |
| `services/lowbattery` | `/userdata/system/services/` | Выключает приставку при низком заряде на батарее |
| `app/battery_app.py`, `app/Battery.sh` | `/userdata/roms/tools/` | Приложение «Батарея» |

Настройки хранятся в `/userdata/system/configs/battery-tools.conf`. Службы перечитывают файл на каждой проверке (раз в 30/60 с), поэтому изменения применяются без перезапуска.

## Установка с Mac

```sh
tools/battery/install.sh 192.168.2.173
```

Установщик сохраняет существующие настройки, включает обе службы в автозапуск (`system.services` в `knulli.conf`) и добавляет «Батарею» в `gamelist.xml` раздела «Инструменты». Чтобы она появилась в меню, обновите списки игр в EmulationStation или перезагрузите приставку.

## Приложение

Крестовина выбирает пункт, A меняет его, влево/вправо перебирают значения, B выходит.

- **Ограничение заряда** — вкл/выкл.
- **Диапазон** — 40–60% (хранение, игра на ТВ с кабелем), 50–80% (повседневно), 20–80% (максимум циклов).
- **Зарядить до 100% один раз** — перед поездкой. Действует до полного заряда или отключения кабеля, затем ограничение возвращается само.
- **Выключение при низком заряде** — вкл/выкл, порог 10/15/20/25%.

## Утилита

```sh
battery-tools status          # состояние
battery-tools limit off       # on | off | toggle
battery-tools range 50 80
battery-tools full            # один раз до 100%
battery-tools lowbat-percent 20
```

## Как работает ограничение

У PMIC AXP2202 (в основном ядре — AXP717) нет sysfs-настройки для запрета зарядки, поэтому `chargelimit` меняет по I2C один бит: бит 1 регистра `0x19` (`MODULE_EN_CONTROL_2`, «зарядка разрешена»). Этот же бит использует драйвер основного ядра Linux. Остальные биты не трогаются.

- На зарядке при заряде ≥ верхней границы зарядка выключается, приставка питается от кабеля.
- При заряде ≤ нижней границы зарядка снова разрешается.
- Без кабеля, при выключенном ограничении и при остановке службы зарядка всегда разрешена.

Журналы: `/userdata/system/logs/chargelimit.log`, `/userdata/system/logs/lowbattery.log`.

## Удаление

```sh
ssh root@192.168.2.173 'for s in chargelimit lowbattery; do knulli-services stop $s; knulli-services disable $s; rm /userdata/system/services/$s; done; rm -r /userdata/system/bin/battery-tools /userdata/system/configs/battery-tools.conf /userdata/roms/tools/Battery.sh /userdata/roms/tools/battery /userdata/roms/tools/images/battery.png'
```

Запись в `gamelist.xml` раздела «Инструменты» удаляется вручную; копия до установки — `gamelist.xml.bak-battery-20261027`.
