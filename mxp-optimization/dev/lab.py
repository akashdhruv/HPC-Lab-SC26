"""mxp-optimization's tools: mixed precision with RAPTOR and OpenEvolve (dev/README.md)."""

import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from lab import Approvals, Job, parent


class Mxp(parent(__file__)):
    image = "hpc-lab-mxp"

    def check(self):
        """
        The app's tests in the container (make check)
        """
        return self.docker.run(["make", "check"])

    def new(self, stage, experiment, source="app/src/advect.cpp"):
        """
        Make the next instance of a stage (raptorize|optimize), experiments/<E>/<n>-<stage>, from its
        skill's templates/; prints R. optimize also gets seed.cpp from `source` (relative to app/,
        default app/src/advect.cpp) and records it in experiment.yaml.
        """
        templates = self.path / ".agents" / "skills" / stage / "templates"
        if not templates.is_dir():
            sys.exit(f"unknown stage: {stage}")

        folder = self.path / "experiments" / experiment
        folder.mkdir(parents=True, exist_ok=True)
        number = len([p for p in folder.iterdir() if p.is_dir()]) + 1
        run = folder / f"{number}-{stage}"
        (run / "results").mkdir(parents=True)
        (run / "patches").mkdir()

        name = run.relative_to(self.path).as_posix()
        for template in templates.iterdir():
            text = template.read_text().replace("<R>", name).replace("<date>", str(datetime.date.today()))
            (run / template.name).write_text(text)
        if stage == "optimize":
            source_path = self.path / source
            if not source_path.is_file():
                sys.exit(f"source not found: {source}")
            shutil.copy(source_path, run / "seed.cpp")
            experiment_file = run / "experiment.yaml"
            text = experiment_file.read_text()
            text = text.replace("source: app/src/advect.cpp", f"source: {source}")
            obj = Path(source).stem + ".o"
            text = text.replace("object: advect.o", f"object: {obj}")
            experiment_file.write_text(text)
        print(name)

    def evolve(self, *args):
        """
        [--status|--stop|--resume] <R>: the OpenEvolve search of an approved optimize run, in the
        detached container hpc-lab-mxp-optimization; it outlives the session, one at a time.
        --status: running or not, scores, the tail of <R>/results/evolve.log; --stop: stop it, the
        search records its state; --resume: continue from the last checkpoint.
        """
        flag, args = self.flag(args, "--status", "--stop", "--resume")
        if len(args) != 1:
            sys.exit("usage: dev/bin/evolve [--status|--stop|--resume] <R>")
        search = Search(self, args[0])

        if flag == "--status":
            search.status()
        elif flag == "--stop":
            search.stop()
        elif flag == "--resume":
            search.start("resume")
        else:
            search.start("evolve")

    def patch(self, out):
        """
        Save app/'s changes since HEAD as one patch, untracked files included (raptorize
        checkpoints: <R>/patches/<k>-<name>.patch). Natively with git; the real index is untouched.
        """
        with tempfile.TemporaryDirectory() as tmp:
            env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "index")}  # a throwaway index

            def git(*args):
                return subprocess.run(["git", *args], cwd=self.path, env=env, check=True,
                                      capture_output=True).stdout

            git("read-tree", "HEAD")
            git("add", "-A", "app")
            diff = git("diff", "--cached", "--binary", "HEAD", "--", "app")
        Path(out).write_bytes(diff)
        print(f"saved {out}")

    def animate(self, run, id=None):
        """
        Run fp64, the seed and a candidate (default: the applied app/src/advect.cpp) in the run's mode,
        in the container, and write <R>/results/animation.mp4
        """
        command = ["python3", ".agents/skills/optimize/scripts/animate.py", Path(run).as_posix().rstrip("/")]
        if id:
            command.append(id)
        return self.docker.run(command)


class Search:
    """
    The OpenEvolve search of one optimize run R, in the system's detached container
    """

    def __init__(self, system, run):
        self.run = Path(run).as_posix().rstrip("/")
        self.results = Path(self.run) / "results"
        self.docker = system.docker

    def start(self, action):
        Approvals(self.run).require("plan")
        if self.docker.running():
            sys.exit(f"a search is already running in {self.docker.name}; dev/bin/evolve --status <R>")
        if self.docker.run(["dev/tools/search.sh", self.run, action], detach=True) == 0:
            print(f"search started in {self.docker.name}; dev/bin/evolve --status {self.run}")

    def stop(self):
        if not self.docker.running():
            sys.exit("no search running")
        self.docker.stop()
        print(f"search stopped; dev/bin/evolve --resume {self.run} continues it")

    def status(self):
        running = self.docker.running()
        print(f"container  {self.docker.name} {'running' if running else 'not running'}")
        state = self.results / "status.json"
        if not running and state.is_file() and json.loads(state.read_text()).get("state") == "running":
            print(f"           the search was killed; dev/bin/evolve --resume {self.run} continues it")
        sys.stdout.flush()
        self.docker.run(["make", "status", f"EXP={self.run}"])
        print(f"== {self.results.as_posix()}/evolve.log")
        print(Job(self.results, "evolve").tail() or "empty")
