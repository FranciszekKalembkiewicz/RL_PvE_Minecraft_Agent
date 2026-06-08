"""Plot max_wave histogram from evaluate.py CSV."""

from pathlib import Path

import numpy as np

try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None


def main():
    csv_path = Path("logs/eval_max_wave.csv")
    if not csv_path.exists():
        print(f"Brak pliku {csv_path} — uruchom najpierw evaluate.py")
        return 1

    data = np.loadtxt(csv_path, skiprows=1)
    if data.ndim == 0:
        data = np.array([data])

    print(f"Epizody: {len(data)} | mean={data.mean():.2f} | max={data.max():.0f}")

    if plt is None:
        print("Zainstaluj matplotlib: pip install matplotlib")
        return 0

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    axes[0].hist(data, bins=range(int(data.max()) + 2), edgecolor="black", alpha=0.75)
    axes[0].set_xlabel("max_wave")
    axes[0].set_ylabel("Liczba epizodów")
    axes[0].set_title("Rozkład przetrwanych fal")

    waves = np.arange(1, int(data.max()) + 1)
    survival = [np.mean(data >= w) * 100 for w in waves]
    axes[1].plot(waves, survival, marker="o")
    axes[1].set_xlabel("Fala")
    axes[1].set_ylabel("% epizodów")
    axes[1].set_title("Krzywa przeżycia (cum.)")
    axes[1].set_ylim(0, 105)

    plt.tight_layout()
    out = Path("logs/eval_max_wave.png")
    plt.savefig(out, dpi=120)
    print(f"Zapisano wykres: {out}")
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
