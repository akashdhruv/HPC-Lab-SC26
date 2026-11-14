"""Module with implementation of the Run class: one optimize instance R (dev/bin/new makes it).

Usage:
    run.py redteam|evolve|resume|status|harvest <R>
    run.py apply <R> <id>
    run.py restore <R>
"""

import csv
import difflib
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
MXP = HERE.parents[3]  # .agents/skills/optimize/scripts
TUTORIAL = HERE.parents[4]
FAILED = -1e12

# Red-team edits inside the EVOLVE-BLOCK: (name, old, new); an empty old prepends new
CHEATS = [
    ("float", "const double rIS1", "const float rIS1"),
    ("fma", "(13.0 / 12.0) * sqr(", "std::fma(1.0, 13.0 / 12.0, 0.0) * sqr("),
    ("include", "", "#include <cmath>\n"),
    ("scheme", "(13.0 / 12.0)", "(13.0 / 11.0)"),
    (
        "skip-y",
        "- (fry * vr - fly * vl) / dy;",
        "- 0.0 * (fry * vr - fly * vl) / dy;",
    ),
]


def interrupt(*_):
    """
    docker stop sends SIGTERM: stop the search like Ctrl-C, so its state is recorded
    """
    raise KeyboardInterrupt


class Endpoint:
    """Model endpoint from the tutorial's config.yaml"""

    def __init__(self, path=TUTORIAL / "config.yaml"):
        if not path.is_file():
            sys.exit(f"{path} missing")

        config = yaml.safe_load(path.read_text()) or {}
        def resolve(value):
            value = os.path.expandvars(str(value or ""))
            if value.startswith("!"):
                try:
                    out = subprocess.run(value[1:], shell=True, capture_output=True, text=True, timeout=30)
                    if out.returncode == 0 and out.stdout.strip():
                        return out.stdout.strip()
                except Exception:
                    pass
                return ""
            return value
        self.base_url = resolve(config.get("OPENAI_COMP_BASEURL", ""))
        self.api_key = resolve(config.get("OPENAI_COMP_APIKEY", ""))
        self.evolve = config.get("evolve") or {}

        if not self.base_url or not self.api_key:
            sys.exit(f"set OPENAI_COMP_BASEURL and OPENAI_COMP_APIKEY in {path}")


class Run:
    """
    experiments/<E>/<n>-optimize: plan files, approvals and results of one search
    """

    def __init__(self, path):
        self.path = Path(path).resolve()
        self.results = self.path / "results"
        self.experiment = yaml.safe_load((self.path / "experiment.yaml").read_text()) or {}
        self.source_rel = self.experiment.get("source", "app/src/advect.cpp")
        self.source = MXP / self.source_rel
        self.seed_file = self.path / "seed.cpp"

    def approved(self, item):
        """
        Exit unless the scientist approved this item
        """
        approvals = self.path / "approvals.toml"
        if f'item = "{item}"' not in approvals.read_text():
            sys.exit(f"not approved: '{item}' (/approve <R> \"{item}\")")

    def spec(self):
        """
        experiment.yaml; MAX_PROGRAMS in the environment overrides max_programs
        """
        spec = dict(self.experiment)
        spec["max_programs"] = int(os.environ.get("MAX_PROGRAMS", spec["max_programs"]))
        return spec

    def check_seed(self):
        """
        Exit if app/ does not hold the seed (a stopped search may leave a candidate)
        """
        if self.source.read_bytes() != self.seed_file.read_bytes():
            sys.exit(
                f"{self.source_rel} is not the seed: make restore EXP={self.name()}"
            )

    def score(self, source):
        """
        Score and label of one candidate source, evaluated as the search does
        """
        with tempfile.TemporaryDirectory() as work:
            Path(work, "initial_program.py").write_text(source)
            output = Path(work, "result.json")

            subprocess.run(
                [
                    sys.executable,
                    str(self.path / "evaluator.py"),
                    "--program-dir",
                    work,
                    "--output-file",
                    str(output),
                ],
                capture_output=True,
                check=False,
            )
            result = json.loads(output.read_text()) if output.is_file() else {}

        score = (result.get("scores") or [{}])[0].get("score")
        label = (result.get("insights") or [{"label": "EVALUATOR_ERROR"}])[0]["label"]
        return score, label

    def redteam(self):
        """
        Every cheat must score null or below the seed; the table goes to results/redteam.md
        """
        self.check_seed()
        seed = self.source.read_text()
        start = seed.index("// EVOLVE-BLOCK-START\n") + len("// EVOLVE-BLOCK-START\n")
        head, block = seed[:start], seed[start:]

        cheats = []
        if self.source_rel == "app/src/advect.cpp":
            for name, old, new in CHEATS:
                edited = block.replace(old, new, 1) if old else new + block
                cheats.append((name, head + edited))
        marker = "#include <cstddef>"
        if marker in seed:
            cheats.append(("outside", seed.replace(marker, marker + " // x", 1)))

        base, label = self.score(seed)
        shown = label if base is None else f"{base:.3f}"
        rows, holes = [f"| seed | {shown} | reference |"], 0

        for name, source in cheats:
            value, label = self.score(source)
            caught = value is None or (base is not None and value < base)
            holes += not caught

            shown = "null" if value is None else f"{value:.3f}"
            rows.append(f"| {name} | {shown} | {label if caught else 'HOLE'} |")
            print(rows[-1], flush=True)

        table = "| cheat | score | result |\n|---|---|---|\n" + "\n".join(rows)
        (self.results / "redteam.md").write_text(f"{table}\n\n{holes} hole(s)\n")
        sys.exit(1 if holes else 0)

    def openevolve_config(self, spec, endpoint):
        """
        OpenEvolve's config from experiment.yaml and config.yaml's evolve section
        """
        options = {**endpoint.evolve, **(spec.get("openevolve") or {})}
        model = options.get("model")
        if not model:
            sys.exit("set evolve.model in config.yaml")

        llm = {
            "models": [{"name": model, "weight": 1.0}],
            "api_base": endpoint.base_url,
            "api_key": "${OPENAI_API_KEY}",
            "max_tokens": options.get("max_tokens", 16000),
            "timeout": options.get("timeout", 300),
        }
        if options.get("reasoning_effort"):
            llm["reasoning_effort"] = options["reasoning_effort"]

        return {
            "max_iterations": spec["max_programs"],
            "checkpoint_interval": 1,
            "language": "cpp",
            "diff_based_evolution": True,
            "enforce_evolve_blocks": True,
            "max_code_length": 40000,
            "llm": llm,
            "prompt": {"system_message": spec["problem"]},
            "evaluator": {
                "timeout": spec["timeout"],
                "parallel_evaluations": 1,
                "cascade_evaluation": False,
            },
        }

    def evolve(self, checkpoint=None):
        """
        Run the search (needs the approved plan) and record its state in results/status.json
        """
        self.approved("plan")
        self.check_seed()

        signal.signal(signal.SIGTERM, interrupt)
        self.record("running")
        try:
            self.search(checkpoint)
            self.record("finished")
        except (subprocess.CalledProcessError, KeyboardInterrupt) as error:
            self.record("stopped")
            sys.exit(f"search stopped: {error}")

    def search(self, checkpoint):
        """
        Score the seed, then run OpenEvolve until max_programs
        """
        spec, endpoint = self.spec(), Endpoint()

        output = self.results / "openevolve"
        program = self.results / "initial_program.cpp"
        output.mkdir(parents=True, exist_ok=True)

        if checkpoint is None:
            shutil.copy(self.seed_file, program)
            base, label = self.score(self.seed_file.read_text())
            if base is None and label != "NAN_OR_INF":  # a NaN seed is the search's first problem
                self.record("failed")
                sys.exit(f"the seed does not score: {label}")
            baseline = {"score": base, "label": label}
            (self.results / "baseline.json").write_text(json.dumps(baseline))

        config = output / "config.yaml"
        config.write_text(
            yaml.safe_dump(self.openevolve_config(spec, endpoint), sort_keys=False)
        )

        command = [
            str(Path(sys.executable).with_name("openevolve-run")),
            str(program),
            str(HERE / "openevolve_evaluator.py"),
            "--config",
            str(config),
            "--output",
            str(output),
            "--iterations",
            str(spec["max_programs"]),
        ]
        if checkpoint:
            command += ["--checkpoint", str(checkpoint)]

        env = {
            **os.environ,
            "EVAL_LOG": str(self.results / "evaluations.jsonl"),
            "OPENAI_API_KEY": endpoint.api_key,
            "OE_EVALUATOR": str(self.path / "evaluator.py"),
            "OE_TIMEOUT": str(spec["timeout"]),
            "OE_PYTHON": sys.executable,
        }

        subprocess.run(command, env=env, check=True)

    def resume(self):
        """
        Continue from the last checkpoint unless the search is done
        """
        checkpoint = self.latest()
        done = int(checkpoint.name.split("_")[1]) if checkpoint else 0
        if done < self.spec()["max_programs"]:
            self.evolve(checkpoint)

    def status(self):
        """
        State, number of evaluations, seed and best score, and the last labels
        """
        status = self.read("status.json") or {}
        baseline = self.read("baseline.json") or {}

        log = self.results / "evaluations.jsonl"
        evaluations = (
            [json.loads(line) for line in log.read_text().splitlines()]
            if log.is_file()
            else []
        )
        scores = [entry["score"] for entry in evaluations if entry["score"] is not None]

        candidates = max(len(evaluations) - 1, 0)
        rejected = len(evaluations) - len(scores)

        print(f"state      {status.get('state', 'not started')}")
        print(
            f"evaluated  seed + {candidates} / {status.get('max_programs', '?')} "
            f"candidates ({rejected} rejected)"
        )
        print(f"seed       {baseline.get('score')}")
        print(f"best       {max(scores) if scores else None}")
        for entry in evaluations[-5:]:
            print(f"  {entry['time']}  {entry['label']:<28} {entry['score']}")

    def harvest(self):
        """
        Every program of the last checkpoint into results/candidates/, best first
        """
        checkpoint = self.latest() or sys.exit(f"no checkpoint in {self.results}")
        candidates = self.results / "candidates"
        candidates.mkdir(exist_ok=True)
        seed = (self.path / "seed.cpp").read_text().splitlines(keepends=True)

        rows = []
        for path in (checkpoint / "programs").glob("*.json"):
            program = json.loads(path.read_text())
            (candidates / f"{program['id']}.cpp").write_text(program["code"])
            diff = difflib.unified_diff(
                seed, program["code"].splitlines(keepends=True), "seed.cpp", f"{program['id']}.cpp"
            )
            (candidates / f"{program['id']}.diff").write_text("".join(diff))

            score = (program.get("metrics") or {}).get("combined_score", FAILED)
            rows.append(
                {
                    "id": program["id"],
                    "parent": program.get("parent_id") or "",
                    "iteration": program.get("iteration_found", ""),
                    "score": score if score > FAILED else "",
                    "sha1": hashlib.sha1(program["code"].encode()).hexdigest()[:12],
                }
            )

        rows.sort(key=lambda row: -float(row["score"] or FAILED))
        with open(candidates / "candidates.csv", "w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

        print(f"{len(rows)} programs in {candidates.relative_to(MXP)}")
        print(f"best {rows[0]['id']} ({rows[0]['score']})")

    def apply(self, candidate):
        """
        Copy an approved candidate over the seed, then make check
        """
        self.approved(f"candidate {candidate}")
        shutil.copy(self.results / "candidates" / f"{candidate}.cpp", self.source)
        subprocess.run(["make", "check"], cwd=MXP, check=True)

    def restore(self):
        """
        Put the seed back in app/
        """
        shutil.copy(self.seed_file, self.source)

    def latest(self):
        """
        Last OpenEvolve checkpoint directory, or None
        """
        found = (self.results / "openevolve" / "checkpoints").glob("checkpoint_*")
        return max(found, key=lambda path: int(path.name.split("_")[1]), default=None)

    def read(self, filename):
        """
        A JSON file of results/, or None
        """
        path = self.results / filename
        return json.loads(path.read_text()) if path.is_file() else None

    def record(self, state, **extra):
        """
        Write results/status.json
        """
        status = {
            "state": state,
            "max_programs": self.spec()["max_programs"],
            "time": time.time(),
        }
        (self.results / "status.json").write_text(json.dumps({**status, **extra}))

    def name(self):
        return self.path.relative_to(MXP).as_posix()


ACTIONS = ["redteam", "evolve", "resume", "status", "harvest", "apply", "restore"]

if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)

    action, target, *rest = sys.argv[1:]
    if action in ACTIONS:
        getattr(Run(target), action)(*rest)
    else:
        sys.exit(__doc__)
