"""Evaluator of <R>: score = -(mean over steps of err_shape), the shape mismatch M in cells.

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
sys.path.insert(0, str(ROOT / ".agents" / "skills" / "optimize" / "scripts"))

from evaluation import Evaluator, read_csv, run

MODE = "fp8"
COLUMN = "err_shape"  # M: mean distance between the interfaces, in cells
CASE = "nx=64 ny=64 tmax=0.5"  # raptorize's eval run
GUARD_COLUMNS = ["area", "mass", "phi_min", "phi_max"]
GUARD_TOL = 1e-10

OUT = HERE / "results" / f"eval_{os.getpid()}"
REFERENCE = HERE / "results" / "fp64_reference.csv"
COMMAND = (
    f"mpirun --oversubscribe -n 4 ./bubble params/bubble.ini {CASE} "
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
    -(mean over steps of COLUMN), and that mean; (None, None) if missing or not finite
    """
    errors = read_csv(history).get(COLUMN, []) if history.is_file() else []
    if not errors or not all(map(math.isfinite, errors)):
        return None, None

    mean = sum(errors) / len(errors)
    return -mean, mean


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

        # The guard first: the seed itself may be NaN in MODE, and its fp64 run is the reference
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

        score, rms = accuracy(OUT / "history.csv")
        if score is None:
            return EVALUATOR.fail("NAN_OR_INF", f"{COLUMN} missing or non-finite in {MODE}.")

        summary = f"{CASE} in {MODE}: mean shape mismatch M = {rms:.4f} cells."
        return EVALUATOR.result({"score": score}, [("SUMMARY", summary)])

    finally:
        shutil.rmtree(OUT, ignore_errors=True)
        shutil.rmtree(fp64, ignore_errors=True)


if __name__ == "__main__":
    EVALUATOR.main(evaluate)
