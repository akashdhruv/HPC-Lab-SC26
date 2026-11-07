#!/usr/bin/env python3
"""Compare the diag lines of a run with tests/golden.out.

Every number must agree within |a - b| <= atol + rtol * |b|.

    compare.py <output> [golden] [--rtol 1e-12] [--atol 1e-14]
"""

import argparse
import sys
from pathlib import Path

COLUMNS = ["step", "time", "mass_u", "mass_v", "max_v", "min_u", "imax", "jmax", "frac"]
GOLDEN = Path(__file__).with_name("golden.out")


def read_diag(path):
    """
    Numbers of every line that starts with "diag"
    """
    rows = []
    for line in Path(path).read_text().splitlines():
        if line.startswith("diag"):
            rows.append([float(value) for value in line.split()[1:]])

    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("golden", nargs="?", default=str(GOLDEN))
    parser.add_argument("--rtol", type=float, default=1e-12)
    parser.add_argument("--atol", type=float, default=1e-14)
    args = parser.parse_args()

    got, want = read_diag(args.output), read_diag(args.golden)
    if len(got) != len(want):
        print(f"FAIL: {len(got)} diag lines, golden has {len(want)}")
        return 1

    worst, failures = (0.0, "none"), []
    for row, (got_row, want_row) in enumerate(zip(got, want)):
        for column, (a, b) in enumerate(zip(got_row, want_row)):
            difference = abs(a - b) / abs(b) if b else abs(a - b)
            where = f"line {row} {COLUMNS[column]}: got {a!r}, want {b!r}"
            worst = max(worst, (difference, where))
            if abs(a - b) > args.atol + args.rtol * abs(b):
                failures.append(where)

    print(f"worst relative difference {worst[0]:.3e} ({worst[1]})")
    if failures:
        print(f"FAIL: {len(failures)} values outside rtol={args.rtol:g}")
        print("\n".join(failures[:5]))
        return 1

    print(f"PASS: {len(got)} diag lines agree with the golden run (rtol={args.rtol:g})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
