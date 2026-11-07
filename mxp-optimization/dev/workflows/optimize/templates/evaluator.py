"""Evaluator of <R>: score = -log10(RMS over steps of err_rms) of the RAPTOR-emulated mode.

The block is FP64 code that RAPTOR truncates. A candidate must compute the same scheme: its
fp64 run must reproduce the seed's fp64 diagnostics (the equivalence guard). The constants
are the plan's decisions; `make evaluate EXP=<R>` scores the current tree.
"""

import math
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "dev" / "workflows" / "optimize"))

from evaluation import Evaluator, read_csv, run

MODE = "bf16"
COLUMN = "err_rms"
GRID, STEPS = 128, 100
GUARD_COLUMNS = ["area", "mass", "phi_min", "phi_max"]
GUARD_TOL = 1e-10

OUT = HERE / "results" / f"eval_{os.getpid()}"
REFERENCE = HERE / "results" / "fp64_reference.csv"
COMMAND = (
    f"mpirun -n 1 ./bubble params/bubble.ini nx={GRID} ny={GRID} max_steps={STEPS} "
    "plot_interval=0 verbosity=0 precision={mode} outdir={out}"
)

EVALUATOR = Evaluator(
    root=ROOT,
    source="src/advect.cpp",
    command=COMMAND.format(mode=MODE, out=OUT),
    outdir=OUT,
    metrics=["score"],
)


def accuracy(history):
    """
    -log10 of the RMS over steps of COLUMN, and that RMS; (None, None) if missing
    """
    errors = read_csv(history).get(COLUMN, []) if history.is_file() else []
    if not errors or not all(map(math.isfinite, errors)):
        return None, None

    rms = math.sqrt(sum(error * error for error in errors) / len(errors))
    return -math.log10(rms + 1e-30), rms


def equivalent(history):
    """
    Largest relative gap of the guard columns to the seed's fp64 run
    """
    got, want = read_csv(history), read_csv(REFERENCE)
    gap = 0.0
    for column in GUARD_COLUMNS:
        for a, b in zip(got.get(column, []), want[column]):
            gap = max(gap, abs(a - b) / max(abs(b), 1e-30))

    return gap


def evaluate():
    fp64 = OUT.with_name(OUT.name + "_fp64")
    try:
        failed = EVALUATOR.prepare()
        if failed:
            return failed

        score, rms = accuracy(OUT / "history.csv")
        if score is None:
            return EVALUATOR.fail("NAN_OR_INF", f"{COLUMN} missing or non-finite.")

        code, output = run(COMMAND.format(mode="fp64", out=fp64), 300, ROOT / "app")
        if code:
            return EVALUATOR.fail("FP64_RUN_FAILED", output[-2000:])

        if not REFERENCE.is_file():
            shutil.copy(fp64 / "history.csv", REFERENCE)

        gap = equivalent(fp64 / "history.csv")
        if gap > GUARD_TOL:
            return EVALUATOR.fail(
                "EQUIVALENCE_FAILED", f"fp64 run differs from the seed's by {gap:.2e}."
            )

        summary = f"{STEPS} steps on {GRID}^2 in {MODE}: rms {COLUMN} = {rms:.3e}."
        return EVALUATOR.result({"score": score}, [("SUMMARY", summary)])

    finally:
        shutil.rmtree(OUT, ignore_errors=True)
        shutil.rmtree(fp64, ignore_errors=True)


if __name__ == "__main__":
    EVALUATOR.main(evaluate)
