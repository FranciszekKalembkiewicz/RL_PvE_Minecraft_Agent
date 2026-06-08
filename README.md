# Minecraft RL — Wave Arena

Agent PPO trenowany na arenie z falami mobów (zombie, szkielet, creeper) w **prawdziwym Minecraft** (Paper 1.20.4).

## Struktura

| Ścieżka | Opis |
|---------|------|
| `docs/ASSUMPTIONS.md` | Założenia projektu |
| `configs/waves.yaml` | Arena, sloty, fale, nagrody, trening |
| `bridge/protocol.md` | Protokół TCP JSON |
| `server/` | Paper + plugin WaveArena |
| `env/arena_mc_env.py` | Środowisko Gymnasium |
| `train.py` / `evaluate.py` | Trening i ewaluacja |

## Konfiguracja lokalna

```bash
cp configs/waves.example.yaml configs/waves.yaml
cp server/plugins/WaveArena/config.example.yml server/plugins/WaveArena/config.yml
# Ustaw swój nick Minecraft w obu plikach (agent.username / agent-username)
```

## Szybki start (dev bez serwera)

```bash
pip install -r requirements.txt
ARENA_MOCK=1 python test_env.py
ARENA_MOCK=1 python train.py          # krótki trening na mocku
ARENA_MOCK=1 python evaluate.py
python report/plot_results.py
```

## Pełny pipeline (Minecraft)

### 1. Serwer

```bash
cd server
chmod +x setup_server.sh start.sh
./setup_server.sh
cd plugins/WaveArena && mvn package -q
cp target/WaveArena-1.0.0.jar ../../plugins/
cd ../..
./start.sh
```

Ustaw w `server.properties`: `online-mode=false`. Zbuduj arenę (patrz `server/README.md`).

### 2. Agent w grze

Dołącz klientem Minecraft jako **`AgentBot`** (nick z `configs/waves.yaml`).

### 3. Trening na żywym serwerze

```bash
# Terminal 1: serwer Paper
# Terminal 2:
unset ARENA_MOCK   # lub export ARENA_MOCK=0
python train.py
tensorboard --logdir logs
```

### 4. Ewaluacja i raport

```bash
python evaluate.py
python report/plot_results.py
```

Nagraj gameplay (OBS) podczas `evaluate.py` z `ARENA_MOCK=0`.

## Metryka

**`max_wave`** — najwyższa ukończona fala w epizodzie. Zapis w `logs/eval_max_wave.csv`.

## Komendy w grze

- `/wavearena reset` — reset epizodu
- `/wavearena status` — stan
- `/wavearena next` — następna fala (test)

## Uwagi

- Trening w MC jest wolny — `n_envs: 1` w config.
- Po zmianie pozycji areny zaktualizuj `configs/waves.yaml` i `server/plugins/WaveArena/config.yml`.
- Plugin buduje się z Javą 17+ i Maven.
