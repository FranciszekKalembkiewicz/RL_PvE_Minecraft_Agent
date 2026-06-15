# Zanim pójdziesz spać (5 minut)

## 1. Przerwij obecny trening mixed 30k

W terminalu gdzie leci `train.py`:

```text
Ctrl+C
```

(Mixed psuje zombie — i tak używamy **dual model**.)

## 2. Serwer Minecraft

```bash
cd server
./start.sh
```

**Albo** jeśli serwer już działa — **zrestartuj go** po starcie skryptu (skrypt zmieni config).

## 3. Wejdź do gry jako `Franq__`

- Musisz być **online** całą noc (AFK w centrum areny OK).
- Bez gracza trening **nie ruszy**.

## 4. Uruchom pipeline nocny

```bash
cd "/Users/franciszekkalembkiewicz/Library/CloudStorage/OneDrive-PolitechnikaWroclawska/Studia/Semestr 6/Systemy inteligentne/RL - Minecraft PvE/minecraft_rl_project"
chmod +x scripts/overnight_dual_train.sh
nohup ./scripts/overnight_dual_train.sh &
```

Skrypt sam:
1. Kopiuje model **melee** (500k)
2. Ustawia trening **tylko SKELETON** + assist
3. Czeka na bridge `:5555` (max 30 min)
4. Trenuje **80k** od checkpointu 500k
5. Zapisuje `final_wave_ranged.zip`
6. Przywraca config pod demo (mixed moby, assist off)

## 5. Po starcie skryptu — w grze (OP)

Gdy skrypt wypisze komunikat o reload:

```text
/wavearena reload
/wavearena reset
```

(Jeśli zrestartowałeś serwer przed snem — wystarczy wejść jako Franq__.)

## 6. Rano sprawdź

```bash
cat logs/overnight_STATUS.txt
tail -50 logs/overnight_*.log
```

Demo:

```bash
conda activate minecraft_rl
cd minecraft_rl_project
unset ARENA_MOCK
/wavearena reload   # w grze, po restarcie serwera
DUAL_MODEL=1 DEMO_SLEEP=0.03 python demo.py
```

## Czas

- Trening 80k ≈ **1h 10min**
- Czekanie na bridge: do 30 min jeśli serwer późno wstanie
