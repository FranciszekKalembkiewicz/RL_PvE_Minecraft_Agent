# Protokół mostu Python ↔ WaveArena (Paper)

Transport: **TCP**, jedna linia = jeden komunikat JSON zakończony `\n`.

Port domyślny: **5555** (konfigurowalny w `config.yml`).

## Komendy (Python → plugin)

### `reset`

Rozpoczyna nowy epizod: usuwa moby `arena_mob`, teleportuje agenta na środek, pełne HP, fala = 1, spawn pierwszej fali.

```json
{"cmd": "reset"}
```

### `step`

Wykonuje akcję agenta i symuluje `step_ticks` ticków serwera (domyślnie 2).

```json
{"cmd": "step", "action": 4}
```

Akcje: `0` przód, `1` tył, `2` lewo, `3` prawo, `4` atak, `5` noop, `6` skok, `7` obrót +45°.

### `status`

Zwraca stan bez wykonywania akcji.

```json
{"cmd": "status"}
```

## Odpowiedzi (plugin → Python)

Wspólne pola:

| Pole | Typ | Opis |
|------|-----|------|
| `ok` | bool | Sukces komendy |
| `error` | string? | Komunikat błędu |
| `wave` | int | Aktualna fala (1-based) |
| `max_wave` | int | Najwyższa ukończona fala w epizodzie |
| `alive_mobs` | int | Żywe moby z tagiem |
| `agent_hp` | float | HP agenta |
| `agent_max_hp` | float | Max HP |
| `agent_pos` | `{x,y,z}` | Pozycja świata |
| `arena_center` | `{x,y,z}` | Środek areny |
| `arena_radius` | float | Promień normalizacji |
| `mobs` | array | Lista mobów (patrz niżej) |
| `episode_done` | bool | Koniec epizodu (śmierć lub max fala+) |
| `wave_cleared` | bool | Ostatnia akcja zakończyła falę |
| `wave_failed` | bool | Timeout fali lub śmierć |
| `step` | int | Numer kroku w epizodzie |
| `kills_this_step` | int | Zabicia w tym kroku |
| `damage_dealt` | float | Obrażenia zadane w kroku |

Element `mobs[]`:

```json
{
  "hp": 18.5,
  "max_hp": 20.0,
  "x": 12.0,
  "y": 64.0,
  "z": 3.0,
  "type": "ZOMBIE"
}
```

## Przepływ epizodu RL

1. Python: `reset` → plugin startuje falę 1.
2. Pętla: `step` → Python liczy nagrodę z delty HP mobów / zdarzeń (`wave_cleared`, `kills_this_step`).
3. `episode_done == true` gdy agent martwy lub osiągnięto `max_waves` (config).

## Nagrody

Liczone **wyłącznie w Pythonie** (`env/arena_mc_env.py`) na podstawie odpowiedzi `step`/`reset`.

## Błędy

- Brak gracza `AgentBot` online → `ok: false`, `error: "agent_offline"`.
- Nieznana komenda → `ok: false`, `error: "unknown_cmd"`.
