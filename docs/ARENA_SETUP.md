# Ustawienie areny pod Twój świat

Plugin spawnuje moby w punktach z `config.yml` / `waves.yaml`. Domyślnie to okrąg wokół **(0.5, 64, 0.5)**.

## Jeśli arena jest przy spawnie (Twój przypadek)

1. Wejdź na serwer, stój na **środku** areny.
2. Naciśnij **F3** i zapisz współrzędne (np. `X=12.5 Y=70 Z=-8.5`).
3. Wpisz je w **obu** plikach:
   - `server/plugins/WaveArena/config.yml` → `arena.center-x/y/z`
   - `configs/waves.yaml` → `arena.center`

4. **Y** slotów spawnu = wysokość **podłogi** areny (nie ściany).

5. Sloty na obwodzie: promień ~10 bloków od środka (dla areny 21×21).
   Możesz ustawić ręcznie 4 rogi + 4 boki lub użyć komendy w grze po `/wavearena reset` i poprawić pozycje mobów.

## Słońce / moby

Plugin od wersji z poprawkami:
- ustawia **noc** w świecie areny (`doDaylightCycle: false`),
- daje mobom **Fire Resistance**.

Opcjonalnie zbuduj **dach** z bedrocka — wtedy i tak działa.

## Ekwipunek agenta

Po `/wavearena reset`:
- żelazny miecz,
- skórzana klata + spodnie.

Atak w RL nadal liczy plugin (`attack-damage` w config), miecz jest do gry „na oko”.
