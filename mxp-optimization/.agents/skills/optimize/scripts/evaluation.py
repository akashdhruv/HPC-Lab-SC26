"""Module with implementation of the Evaluator class: build, audit and run one candidate of
the EVOLVE-BLOCK, and format its score.

A run's evaluator.py creates one Evaluator and adds the score formula. With --program-dir D
the candidate D/initial_program.py is swapped into app/ for one evaluation; without it the
current tree is scored.
"""

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

BLOCK = re.compile(
    r"^\s*// EVOLVE-BLOCK-START\s*\n(.*?)^\s*// EVOLVE-BLOCK-END", re.M | re.S
)
COMMENTS = re.compile(r"//[^\n]*|/\*.*?\*/|\"(?:\\.|[^\"\\])*\"", re.S)

# The block is FP64 code that RAPTOR truncates: no new types, no preprocessor, and no
# library calls, which RAPTOR does not truncate (std::min, max, abs, fabs are exact)
RAPTOR_RULES = [
    (r"\b(float|long\s+double|auto|typedef|using|template|struct|class)\b", "DATATYPE"),
    (r"(?m)^\s*#", "PREPROCESSOR"),
    (r"\bstd::(?!(min|max|abs|fabs)\b)\w+\s*\(", "LIBRARY_CALL"),
    (r"(?<![\w:.])(fma|pow|sqrt|exp|log|sin|cos|tan|__builtin\w*)\s*\(", "LIBRARY_CALL"),
    (r"reinterpret_cast|memcpy|bit_cast|\bunion\b", "FP_EMULATION"),
]

# A native float seed: no 64-bit floating point at all
LOWPREC_RULES = [
    (r"\b(double|float64_t|__float128)\b", "FORBIDDEN_TOKEN"),
    (r"(?m)^\s*#", "PREPROCESSOR"),
]

FP64_ASM = re.compile(
    r"\b(v?(add|sub|mul|div|sqrt|min|max)[sp]d|v?f[n]?m(add|sub)\d+[sp]d)\b"
)


class Evaluator:
    """
    One candidate: build, audit, run, result
    """

    def __init__(
        self,
        root,
        source,
        command,
        outdir,
        metrics,
        build=("make", "RAPTOR=1", "-j4"),
        rules=RAPTOR_RULES,
        fp64_scan=None,
        timeout=600,
    ):
        """
        Constructor

        Parameters
        ----------
        root      : mxp-optimization/, where make builds the app
        source    : the kernel's file, relative to app/
        command   : the run, in app/
        outdir    : its output directory, removed before each run
        metrics   : metric names, primary first
        build     : build command, in root
        rules     : (regex, label) pairs the block must not match
        fp64_scan : (object file, name tag): scan those functions for FP64 instructions
        timeout   : seconds for the run
        """
        self.root = Path(root)
        self.app = self.root / "app"
        self.source = source
        self.command = command
        self.outdir = Path(outdir)
        self.metrics = metrics
        self.build = list(build)
        self.rules = rules
        self.fp64_scan = fp64_scan
        self.timeout = timeout

    def main(self, evaluate):
        """
        Command line of evaluator.py
        """
        parser = argparse.ArgumentParser()
        parser.add_argument("--program-dir")
        parser.add_argument("--output-file")
        args = parser.parse_args()

        source = self.app / self.source
        original = source.read_text()

        if not args.program_dir:
            result = evaluate()
            self.log(original, result)
            print(json.dumps(result, indent=2))
            return

        candidate = Path(args.program_dir, "initial_program.py").read_text()

        if BLOCK.sub("", candidate) != BLOCK.sub("", original):
            result = self.fail("CHANGED_OUTSIDE_BLOCK", "only the block may change.")
        else:
            source.write_text(candidate)
            signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
            try:
                result = evaluate()
            finally:
                source.write_text(original)

        self.log(candidate, result)
        Path(args.output_file).write_text(json.dumps(result))

    def prepare(self):
        """
        Audit the block, build, scan the binary, run; None on success, else the failure
        """
        problem = self.audit()
        if problem:
            return self.fail(*problem)

        code, output = run(self.build, 900, self.root)
        if code:
            return self.fail("COMPILATION_ERROR", output[-4000:])

        if self.fp64_scan:
            problem = self.scan_fp64(*self.fp64_scan)
            if problem:
                return self.fail(*problem)

        shutil.rmtree(self.outdir, ignore_errors=True)
        self.outdir.parent.mkdir(parents=True, exist_ok=True)

        code, output = run(self.command, self.timeout, self.app)
        if code:
            label = "RUNTIME_TIMEOUT" if code == 124 else "RUNTIME_CRASH"
            return self.fail(label, output[-4000:])

        return None

    def audit(self):
        """
        First broken rule as (label, text), else None
        """
        blocks = BLOCK.findall((self.app / self.source).read_text())
        if not blocks:
            return "MISSING_EVOLVE_BLOCK", f"{self.source} has no EVOLVE-BLOCK."

        for block in blocks:
            code = COMMENTS.sub("", block)
            for pattern, label in self.rules:
                match = re.search(pattern, code)
                if match:
                    return label, f"'{match.group(0)}' is not allowed in the block."

        return None

    def scan_fp64(self, objfile, tag):
        """
        First FP64 instruction in the compiled functions whose name contains tag
        """
        objfile = self.app / objfile
        if not shutil.which("objdump") or not objfile.is_file():
            return "AUDIT_UNAVAILABLE", f"objdump or {objfile.name} missing."

        function = ""
        for line in run(["objdump", "-d", "-C", str(objfile)], 60)[1].splitlines():
            header = re.match(r"^[0-9a-fA-F]+\s+<(.+)>:\s*$", line)
            if header:
                function = header.group(1)
            elif tag in function and FP64_ASM.search(line):
                instruction = FP64_ASM.search(line).group(1)
                return "FP64_INSTRUCTION", f"'{instruction}' in '{function}'."

        return None

    @staticmethod
    def fail(label, text):
        return {"score": None, "insights": [{"label": label, "text": text}]}

    def result(self, scores, insights):
        """
        Scores (primary first) and the insights that explain them
        """
        assert set(scores) == set(self.metrics), f"{list(scores)} != {self.metrics}"

        return {
            "scores": [{"metric": key, "score": value} for key, value in scores.items()],
            "insights": [{"label": label, "text": text} for label, text in insights],
        }

    @staticmethod
    def log(source, result):
        """
        Append one line per evaluation to $EVAL_LOG (set by the search)
        """
        if not os.environ.get("EVAL_LOG"):
            return

        insight = (result.get("insights") or [{}])[0]
        line = {
            "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "sha1": hashlib.sha1(source.encode()).hexdigest(),
            "score": (result.get("scores") or [{}])[0].get("score"),
            "label": insight.get("label"),
            "text": (insight.get("text") or "")[:400],
        }

        with open(os.environ["EVAL_LOG"], "a") as stream:
            stream.write(json.dumps(line) + "\n")


def run(command, timeout, cwd=None):
    """
    Exit code and output of a command run without a shell; 124 on timeout
    """
    if isinstance(command, str):
        command = shlex.split(command)

    try:
        done = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, cwd=cwd
        )
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout} s"

    return done.returncode, done.stdout + done.stderr


def read_csv(path):
    """
    Columns of a CSV file as lists of floats (NaN for non-numbers)
    """

    def number(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return math.nan

    with open(path, newline="") as stream:
        rows = list(csv.DictReader(stream))

    if not rows:
        return {}

    return {key.strip(): [number(row[key]) for row in rows] for key in rows[0]}
