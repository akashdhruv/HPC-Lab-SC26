"""Module with implementation of history plots for the Deforming Bubble app.

    python3 tools/plot_history.py [outdir]      # default: out

Reads <outdir>/history.csv (written by src/io.cpp) and writes into <outdir>:

    history_conservation.png   area and mass, and their drift from t = 0
    history_divergence.png     max |div u|, dt, cumulative sign flips
    history_extrema.png        phi_min and phi_max
"""

import argparse
import csv
import os

import numpy
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # pylint: disable=wrong-import-position

DIV_TOL = 1.0e-12  # discrete divergence bar
AREA_BAR = 0.05  # area drift bar of tests/test_conservation


def read_history(filename):
    """
    Read history.csv

    Returns
    -------
    dictionary {column : numpy array}
    """
    with open(filename, newline="", encoding="utf-8") as csvfile:
        rows = list(csv.DictReader(csvfile))

    if not rows:
        raise ValueError(f"[plot_history] {filename} has no data rows")

    return {
        key.strip(): numpy.array([float(row[key]) for row in rows]) for key in rows[0]
    }


def save(fig, outdir, name):
    """
    Save and close a figure as <outdir>/history_<name>.png

    Returns
    -------
    path to the png
    """
    png = os.path.join(outdir, f"history_{name}.png")
    fig.tight_layout()
    fig.savefig(png, dpi=110)
    plt.close(fig)
    return png


def plot_conservation(history, outdir):
    """
    Area and mass versus time, and their relative drift from t = 0
    """
    time = history["time"]
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(7, 7), sharex=True)

    for key, color in [("area", "crimson"), ("mass", "steelblue")]:
        top.plot(time, history[key], color=color, label=key)
        drift = 100 * (history[key] - history[key][0]) / history[key][0]
        bottom.plot(time, drift, color=color, label=f"{key} drift")

    for limit in [AREA_BAR, -AREA_BAR]:
        bottom.axhline(100 * limit, color="0.2", ls="--", lw=1)

    top.set_ylabel("area / mass")
    bottom.set_ylabel("drift [%]")
    bottom.set_xlabel("t")
    for axis in [top, bottom]:
        axis.grid(alpha=0.3)
        axis.legend()

    return save(fig, outdir, "conservation")


def plot_divergence(history, outdir):
    """
    Max |div u| against its bar, dt, and cumulative redistance sign flips
    """
    time = history["time"]
    fig, axes = plt.subplots(3, 1, figsize=(7, 8), sharex=True)

    axes[0].semilogy(time, numpy.maximum(history["max_divergence"], 1e-300))
    axes[0].axhline(DIV_TOL, color="crimson", ls="--", lw=1)
    axes[0].set_ylabel("max |div u|")

    axes[1].plot(time, history["dt"], color="darkorange")
    axes[1].set_ylabel("dt")

    axes[2].plot(time, numpy.cumsum(history["sign_flips"]), color="purple")
    axes[2].set_ylabel("cumulative sign flips")
    axes[2].set_xlabel("t")

    for axis in axes:
        axis.grid(alpha=0.3)

    return save(fig, outdir, "divergence")


def plot_extrema(history, outdir):
    """
    phi_min and phi_max versus time
    """
    fig, axis = plt.subplots(figsize=(7, 4))

    axis.plot(history["time"], history["phi_max"], color="crimson", label="phi_max")
    axis.plot(history["time"], history["phi_min"], color="steelblue", label="phi_min")
    axis.set_xlabel("t")
    axis.grid(alpha=0.3)
    axis.legend()

    return save(fig, outdir, "extrema")


def main():
    """
    Plot every history figure for one output directory
    """
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("outdir", nargs="?", default="out")
    outdir = parser.parse_args().outdir

    history = read_history(os.path.join(outdir, "history.csv"))
    area = history["area"]
    print(f"[plot_history] area drift {100 * abs(area[-1] - area[0]) / area[0]:.4f}%")
    print(f"[plot_history] max |div u| {history['max_divergence'].max():.3e}")

    for plot in [plot_conservation, plot_divergence, plot_extrema]:
        print(f"[plot_history] wrote {plot(history, outdir)}")


if __name__ == "__main__":
    main()
