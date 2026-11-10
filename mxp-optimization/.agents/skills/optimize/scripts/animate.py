"""Module with implementation of the Animation class: fp64, the seed and a candidate of one
optimize run, on the eval case with frames, as one mp4.

    animate.py <R> [id]        (in the container: dev/bin/animate <R> [id])

id is a harvested candidate (results/candidates/<id>.cpp); without it, app/src/advect.cpp (the
applied one). Each kernel is swapped into app/, built and run, and app/ is put back. Writes
<R>/results/animation/ (the runs) and <R>/results/animation.mp4 (matplotlib frames, ffmpeg).
"""

import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

import yaml
from pathlib import Path

import matplotlib
import numpy

matplotlib.use("Agg")

# pylint: disable=wrong-import-position
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter, FuncAnimation

# pylint: enable=wrong-import-position

HERE = Path(__file__).resolve().parent
MXP = HERE.parents[3]  # .agents/skills/optimize/scripts
APP = MXP / "app"

RUN = "mpirun --oversubscribe -n 4 ./bubble params/bubble.ini"
CASE = "nx=64 ny=64 tmax=0.5"  # the eval run of the optimize template
FRAMES = "plot_interval=20 verbosity=0"
COLOURS = {"fp64": "#1d1d1b", "seed": "#c4552d", "candidate": "#2f6db3"}


class Animation:
    """
    The runs of one optimize instance R, and the mp4 that plays them
    """

    def __init__(self, path):
        self.path = Path(path).resolve()
        self.out = self.path / "results" / "animation"
        evaluator = (self.path / "evaluator.py").read_text()
        self.mode = re.search(r'^MODE = "(\w+)"', evaluator, re.M).group(1)
        spec = yaml.safe_load((self.path / "experiment.yaml").read_text()) or {}
        self.kernel_path = MXP / spec.get("source", "app/src/advect.cpp")

    def run(self, candidate=None):
        """
        fp64 and the seed, then the candidate; returns the mp4's path
        """
        status = self.path / "results" / "status.json"
        if status.is_file() and json.loads(status.read_text())["state"] == "running":
            sys.exit("a search is running in app/: wait for it or stop it first")

        source = self.path / "results" / "candidates" / f"{candidate}.cpp" if candidate else self.kernel_path
        label = f"candidate {candidate}" if candidate else "applied candidate"
        seed = self.path / "seed.cpp"
        if source.read_bytes() == seed.read_bytes():
            sys.exit(f"{source.name} is the seed: harvest, then pass a candidate id")

        reference = self.kernel(seed, ["fp64", self.mode], "seed")
        evolved = self.kernel(source, [self.mode], "candidate")
        runs = {
            "fp64": reference["fp64"],
            "seed": reference[self.mode],
            "candidate": evolved[self.mode],
        }

        movie = self.path / "results" / "animation.mp4"
        self.render(runs, label, movie)
        return movie

    def kernel(self, source, modes, name):
        """
        Build app/ with source as the kernel and run each mode; returns {mode: outdir}
        """
        original = self.kernel_path.read_bytes()
        shutil.copy(source, self.kernel_path)
        try:
            shell(["make", "RAPTOR=1", "-j4"], MXP)
            outdirs = {}
            for mode in modes:
                outdirs[mode] = self.out / (name if mode != "fp64" else "fp64")
                shutil.rmtree(outdirs[mode], ignore_errors=True)
                outdirs[mode].parent.mkdir(parents=True, exist_ok=True)
                print(f"[animate] {name} kernel, {mode}", flush=True)
                command = [*RUN.split(), *CASE.split(), *FRAMES.split()]
                shell([*command, f"precision={mode}", f"outdir={outdirs[mode]}"], APP)
        finally:
            self.kernel_path.write_bytes(original)
        return outdirs

    def render(self, runs, label, movie):
        """
        Three panels (fp64; seed and candidate with |phi - phi_fp64| in cells) over the shape
        mismatch M against time, one frame per dump
        """
        names = sorted(path.name for path in runs["fp64"].glob("dfun_*.pvti"))
        frames = [{key: read_frame(outdir / name) for key, outdir in runs.items()} for name in names]
        spacing = frames[0]["fp64"][1]
        history = {key: read_history(runs[key]) for key in ("seed", "candidate")}

        figure = plt.figure(figsize=(12, 7.5), dpi=120)
        grid = figure.add_gridspec(2, 3, height_ratios=[3, 1.2], hspace=0.25, top=0.88, bottom=0.08)
        panels = {key: figure.add_subplot(grid[0, k]) for k, key in enumerate(COLOURS)}
        chart = figure.add_subplot(grid[1, :])
        titles = {
            "fp64": "fp64: the original WENO5",
            "seed": f"seed in {self.mode}",
            "candidate": f"{label} in {self.mode}",
        }

        def draw(k):
            time, _, exact = frames[k]["fp64"]
            for key, axis in panels.items():
                axis.clear()
                axis.set_xticks([])
                axis.set_yticks([])
                field = frames[k][key][2]
                if not numpy.isfinite(field).all():
                    axis.text(0.5, 0.5, "NaN", ha="center", va="center", fontsize=28,
                              color=COLOURS[key], transform=axis.transAxes)
                    axis.set_title(f"{titles[key]}\nnot finite", fontsize=11)
                    continue
                if key == "fp64":
                    axis.contourf(exact, levels=[0, exact.max() + 1], colors=["#dfe9f5"])
                    axis.set_title(f"{titles[key]}\nt = {time:.3f}", fontsize=11)
                else:
                    error = numpy.abs(field - exact) / spacing
                    axis.imshow(error, origin="lower", cmap="Greys", vmin=0, vmax=1,
                                interpolation="nearest")
                    shape = history[key][numpy.argmin(abs(history[key][:, 0] - time)), 1]
                    axis.set_title(f"{titles[key]}\nM = {shape:.3f} cells", fontsize=11)
                    axis.contour(field, levels=[0], colors=COLOURS[key], linewidths=1.6)
                axis.contour(exact, levels=[0], colors=COLOURS["fp64"], linewidths=1.0)
                axis.set_aspect("equal")

            chart.clear()
            for key, values in history.items():
                if len(values) > 1:  # a NaN run keeps only its t = 0 row
                    chart.plot(values[:, 0], values[:, 1], color=COLOURS[key], label=key)
            chart.axvline(time, color="0.5", linewidth=1)
            chart.set_xlim(0, frames[-1]["fp64"][0])
            chart.set_ylim(bottom=0)
            chart.set_xlabel("t")
            chart.set_ylabel("M (cells)")
            chart.grid(color="#e1e0d9", linewidth=0.5)
            chart.legend(loc="upper left", fontsize=9)

        figure.suptitle(
            f"Deforming bubble, {CASE}: black line fp64, grey |phi - phi_fp64| (0 to 1 cell)",
            fontsize=12,
        )
        writer = FFMpegWriter(fps=8, codec="libx264", extra_args=["-pix_fmt", "yuv420p"])
        FuncAnimation(figure, draw, frames=len(frames)).save(movie, writer=writer)
        plt.close(figure)


def read_frame(pvti):
    """
    (time, cell size, phi shaped (ny, nx)) of one .pvti, reassembled from its pieces
    """
    image = ET.parse(pvti).getroot().find("PImageData")
    whole = [int(value) for value in image.get("WholeExtent").split()]
    spacing = float(image.get("Spacing").split()[0])
    time = float(image.find("FieldData/DataArray").text)
    field = numpy.full((whole[3], whole[1]), numpy.nan)
    for piece in image.findall("Piece"):
        ilo, ihi, jlo, jhi = [int(value) for value in piece.get("Extent").split()[:4]]
        array = ET.parse(pvti.parent / piece.get("Source")).getroot().find(
            ".//CellData/DataArray[@Name='dfun']"
        )
        values = numpy.array(array.text.split(), dtype=float)
        field[jlo:jhi, ilo:ihi] = values.reshape(jhi - jlo, ihi - ilo)
    return time, spacing, field


def read_history(outdir):
    """
    (t, err_shape: M in cells) of a run's finite history rows, as an (n, 2) array
    """
    rows = (outdir / "history.csv").read_text().splitlines()
    header = rows[0].split(",")
    time, error = header.index("time"), header.index("err_shape")
    values = numpy.array([[float(row.split(",")[time]), float(row.split(",")[error])]
                          for row in rows[1:]])
    return values[numpy.isfinite(values[:, 1])]


def shell(command, cwd):
    """
    Run a command, exit with its output's tail on failure
    """
    done = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    if done.returncode:
        sys.exit(f"[animate] failed: {' '.join(command)}\n{(done.stdout + done.stderr)[-2000:]}")


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    print(Animation(sys.argv[1]).run(*sys.argv[2:]))
