# Raport — ewaluacja agenta

## Kroki

1. Wytrenuj model (`train.py`) na serwerze lub mocku.
2. Uruchom `evaluate.py` — zapisze `logs/eval_max_wave.csv`.
3. Uruchom `plot_results.py` — wykres `logs/eval_max_wave.png`.

## Nagranie do pracy

Podczas ewaluacji na żywym serwerze (`ARENA_MOCK=0`):

- Obserwuj gracza `AgentBot` w grze.
- Nagraj OBS / QuickTime podczas `evaluate.py`.
- W raporcie dołącz wykres i tabelę średniej `max_wave`.

## Metryki do raportu

| Metryka | Źródło |
|---------|--------|
| Średnia max_wave | `evaluate.py` stdout |
| Rozkład fal | `logs/eval_max_wave.png` |
| Win rate per fala | z CSV (cum. survival w plot_results) |
