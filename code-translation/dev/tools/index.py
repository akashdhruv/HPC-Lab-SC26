#!/usr/bin/env python3
"""Readiness map of the Fortran units in app/src.

A unit is ready when everything it uses or calls is already C++; interface shims
(*_fi.F90) count as C++.

    index.py           readiness table
    index.py --json    the same as JSON
    index.py order     Fortran files in compile order (used by the Makefile)
"""

import json
import re
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "app" / "src"

DEFINES = re.compile(
    r"^\s*(?:\w+(?:\s*\([^)]*\))?\s+)*(program|module|subroutine|function)\s+(\w+)",
    re.IGNORECASE | re.MULTILINE,
)
USES = re.compile(
    r"^\s*use\s*(?:,\s*intrinsic\s*::)?\s*(\w+)", re.IGNORECASE | re.MULTILINE
)
CALLS = re.compile(r"\bcall\s+(\w+)", re.IGNORECASE)
EXTERNALS = re.compile(r"external[ \t]*::[ \t]*([\w \t,]+)", re.IGNORECASE)
INTRINSIC_MODULES = {"iso_c_binding", "iso_fortran_env", "ieee_arithmetic"}


def scan(path):
    """
    Symbols a Fortran file defines, the modules it uses and the procedures it calls
    """
    code = re.sub(r"!.*", "", path.read_text())

    calls = {name.lower() for name in CALLS.findall(code)}
    for group in EXTERNALS.findall(code):
        calls |= {name.strip().lower() for name in group.split(",") if name.strip()}

    return {
        "defines": {name.lower() for _, name in DEFINES.findall(code)},
        "uses": {name.lower() for name in USES.findall(code)} - INTRINSIC_MODULES,
        "calls": calls,
    }


def is_shim(filename):
    """
    Interface shims belong to the C++ side
    """
    return filename.endswith("_fi.F90")


def scan_all():
    """
    Every .F90 in app/src, scanned, by name
    """
    return {path.name: scan(path) for path in sorted(SRC.glob("*.F90"))}


def readiness():
    """
    One row per unit: its untranslated dependencies, who depends on it, ready or not
    """
    files = scan_all()

    owner = {}
    for filename, info in files.items():
        if not is_shim(filename):
            for symbol in info["defines"]:
                owner[symbol] = filename

    deps = {}
    for filename, info in files.items():
        if not is_shim(filename):
            needed = {
                owner[symbol]
                for symbol in info["uses"] | info["calls"]
                if symbol in owner
            }
            deps[filename] = sorted(needed - {filename})

    rows = []
    for filename, needed in deps.items():
        fanin = sorted(
            other for other, other_deps in deps.items() if filename in other_deps
        )
        rows.append(
            {"file": filename, "deps": needed, "fanin": fanin, "ready": not needed}
        )

    return rows


def compile_order():
    """
    Fortran files ordered so that every module is compiled before its users
    """
    files = scan_all()
    module_file = {
        symbol: name for name, info in files.items() for symbol in info["defines"]
    }
    order = []

    def visit(filename, stack=()):
        if filename in order:
            return
        if filename in stack:
            sys.exit(f"module cycle through {filename}")

        for module in sorted(files[filename]["uses"]):
            if module_file.get(module, filename) != filename:
                visit(module_file[module], stack + (filename,))

        order.append(filename)

    for filename in files:
        visit(filename)

    return order


def print_table(rows):
    """
    Ready units first, then by number of dependencies
    """
    rows = sorted(
        rows, key=lambda row: (not row["ready"], len(row["deps"]), row["file"])
    )

    print(f"{'file':<18} {'ready':<6} {'deps (untranslated)':<40} fanin")
    for row in rows:
        ready = "yes" if row["ready"] else "no"
        deps = ", ".join(row["deps"]) or "-"
        fanin = ", ".join(row["fanin"]) or "-"
        print(f"{row['file']:<18} {ready:<6} {deps:<40} {fanin}")

    print(
        f"\nFortran units left: {len(rows)}   C++ files: {len(list(SRC.glob('*.cpp')))}"
    )


def main(args):
    if args[:1] == ["order"]:
        print(" ".join(f"src/{name}" for name in compile_order()))
    elif "--json" in args:
        print(json.dumps(readiness(), indent=2))
    else:
        print_table(readiness())


if __name__ == "__main__":
    main(sys.argv[1:])
