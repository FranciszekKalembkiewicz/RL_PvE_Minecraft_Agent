# Serwer Paper — arena RL

## Szybki start

```bash
cd server
./setup_server.sh    # pobiera Paper 1.20.4 (wymaga curl)
./start.sh           # uruchamia serwer
```

Po pierwszym starcie:
1. Zbuduj okrągłą arenę (promień ~14 bloków) wokół punktu **(0, 64, 0)**.
2. Zaktualizuj `configs/waves.yaml` i `plugins/WaveArena/config.yml` jeśli środek się różni.
3. Skompiluj plugin: `cd plugins/WaveArena && mvn package -q`
4. Skopiuj JAR: `cp target/WaveArena-*.jar ../../plugins/`
5. Włącz `online-mode=false` w `server.properties` (bot offline).
6. Dołącz jako `AgentBot` (drugi klient) lub ustaw plugin na auto-login.

## Budowa areny (Creative)

1. `/gamemode creative`
2. Środek: blok referencyjny na `(0, 64, 0)` — to `arena.center` w config.
3. Platforma: okrąg promień 14, materiał np. stone_bricks.
4. Bariera: fence/wall na krawędzi (wysokość 3).
5. Oświetlenie + `/gamerule mobGriefing false` (opcjonalnie).

Sloty spawnu są już obliczone geometrycznie w `configs/waves.yaml` (12 punktów co 30°). Po zbudowaniu areny w **innym** miejscu świata uruchom w grze:

```
/wavearena calibrate
```

(jeśli dodasz komendę) lub ręcznie przepisz współrzędne Y każdego slotu na wysokość podłogi.

## Komendy pluginu (w grze)

| Komenda | Opis |
|---------|------|
| `/wavearena reset` | Reset epizodu + fala 1 |
| `/wavearena next` | Ręcznie następna fala (test) |
| `/wavearena status` | Stan fali i mobów |
| `/wavearena bridge` | Info o porcie TCP |

## Test bez Pythona

```
/wavearena reset
/wavearena status
```

Zabij moby — plugin powinien automatycznie wywołać następną falę po pauzie.
