# Założenia projektu: RL agent na arenie fal (Minecraft)

## Cel projektu

Wytrenować agenta RL (PPO), który startuje na środku okrągłej areny i przetrwa jak najwięcej **fal** mobów. Główna metryka: **`max_wave`** — najwyższa fala ukończona w epizodzie.

## Środowisko

| Parametr | Wartość |
|----------|---------|
| Gra | Minecraft Java **Paper 1.20.4** |
| Arena | Okrągła platforma, promień **14** bloków |
| Środek areny | Zdefiniowany w `configs/waves.yaml` (domyślnie `0.5, 64, 0.5`) |
| Sloty spawnu | **12** stałych punktów na obwodzie |
| Agent | Gracz `AgentBot` (offline-mode), sterowany przez plugin |
| Most | TCP JSON, port **5555** — patrz `bridge/protocol.md` |

## Fale mobów

| Fala | Liczba mobów | Sloty | Typ moba |
|------|--------------|-------|----------|
| 1 | 1 | `slot[0]` | Losowy z {ZOMBIE, SKELETON, CREEPER}, **stały do końca fali** |
| 2 | 5 | `slot[0..4]` | Nowy losowy typ, stały w fali |
| 3 | 8 | `slot[0..7]` | j.w. |
| 4 | 10 | `slot[0..9]` | j.w. |
| 5 | 12 | `slot[0..11]` | j.w. |
| 6+ | 12 | wszystkie sloty | j.w. (cap) |

### Przejścia

- **Fala zaliczona:** wszystkie moby z tagiem `arena_mob` martwe.
- **Porażka epizodu:** HP agenta ≤ 0 lub timeout fali (domyślnie **120 s**).
- **Między falami:** pauza 2 s, **pełne HP** agenta (curriculum treningowy).

## Przestrzeń akcji (8 dyskretnych)

| ID | Akcja |
|----|--------|
| 0 | Ruch do przodu (względem yaw) |
| 1 | Ruch do tyłu |
| 2 | Strafe lewo |
| 3 | Strafe prawo |
| 4 | Atak (melee w zasięgu) |
| 5 | No-op |
| 6 | Skok |
| 7 | Obrót +45° (yaw) |

## Przestrzeń obserwacji

Wektor o długości `3 + 12 × 5 = 63`:

- Agent: `hp_norm`, `x_norm`, `z_norm` (pozycja względem centrum, znormalizowana promieniem areny)
- Do **12** slotów mobów (posortowane po odległości): `hp_norm`, `dx_norm`, `dz_norm`, `dist_norm`, `angle_norm`
- Martwe / brak moba: zera w slocie

## Nagrody (obliczane w Pythonie)

| Zdarzenie | Nagroda |
|-----------|---------|
| Zbliżenie do najbliższego moba | `+0.05 × Δdist` |
| Trafienie (obrażenia) | `+1.0` |
| Zabicie moba | `+3.0` dodatkowo |
| Ukończenie fali | `+10 + 5 × (pozostały_czas / max)` |
| Śmierć agenta | `-10` |
| Kara za krok | `-0.005 × alive_count` |

## Curriculum treningowy

1. Tylko fala 1 (zombie wyłączone losowanie — opcjonalnie tylko ZOMBIE w config).
2. Po win rate > 70% na fali 1 → `max_wave_train = 2`.
3. Stopniowo do `max_wave_train = 10`.
4. Szkielety i creepery włączone od fali 2 (config `mob_types`).

## Ograniczenia i ryzyka

- Trening w prawdziwym MC jest wolny (minuty na epizod przy wielu falach).
- Creeper: eksplozja może zakończyć epizod wcześnie — włączyć po opanowaniu zombie.
- Szkielet: wymaga zbliżenia / bloków — akcja obrotu (7) jest dostępna.

## Metryki raportowe

- `max_wave` (główna)
- Win rate per fala
- Średnie HP po fali
- Czas epizodu
- TensorBoard: `logs/`, CSV: `logs/eval_results.csv`
