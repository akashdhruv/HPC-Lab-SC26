"""code-translation's tools: Fortran -> C++ with its own loop, dev/tools/loop.py (dev/README.md)."""

import os
import platform
import signal
import sys

from lab import Approvals, Config, Job, Venv, parent, tail, windows_tools


class Translation(parent(__file__)):
    image = "hpc-lab-translate"

    def oracle(self, *args):
        """
        Clean build, one run, compare with the golden output, in the container (exit 0: correct)
        """
        return self.docker.run(["app/tests/check.sh", *args])

    def check(self):
        """
        The oracle
        """
        return self.oracle()

    def readiness(self, *args):
        """
        [--json]: which Fortran units can be translated now, computed in the container
        """
        return self.docker.run(["python3", "dev/tools/index.py", *args])

    def build(self, *args):
        """
        Build app/ in the container (make -C app [args])
        """
        return self.docker.run(["make", "-C", "app", *args])

    def loop(self, *args):
        """
        [-f|--stop] <name> [loops]: run a transformation with the author -> check -> review loop
        (dev/tools/loop.py, on CodeScribe in .venv, model from config.yaml), detached from this
        session; -f in the foreground, --stop stops it after recording the run.
        It refuses an unapproved plan or a second copy. Log: transformations/<name>/runs/loop.log;
        each run's record: runs/<run_id>/; follow it with dev/bin/status <name>.
        """
        Venv().activate()
        flag, args = self.flag(args, "-f", "--stop")
        if not args:
            sys.exit(f"usage: dev/bin/loop [-f|--stop] <name> [loops]   "
                     f"(transformations: {', '.join(self.transformations)})")
        transformation = Transformation(self, args[0])
        loops = int(args[1]) if len(args) > 1 else 10

        if flag == "--stop":
            transformation.stop()
        elif flag == "-f":
            transformation.run(loops)
        else:
            transformation.start(loops)

    def status(self, name=None):
        """
        Approvals, groups, agent log and the loop (running or not, its log, its last runs) of a
        transformation (default: the first); from any session, while the loop runs or after
        """
        if not self.transformations:
            sys.exit("no transformation in transformations/")
        Transformation(self, name or self.transformations[0]).status()

    @property
    def transformations(self):
        return sorted(p.name for p in (self.path / "transformations").iterdir() if p.is_dir())


class Transformation:
    """
    transformations/<name>: spec, plan, loop.toml, approvals, and the runs of its loop
    """

    def __init__(self, system, name):
        self.system, self.name = system, name
        self.path = system.path / "transformations" / name
        if not self.path.is_dir():
            sys.exit(f"no transformation {name}; have: {', '.join(system.transformations) or 'none'}")
        self.runs = self.path / "runs"
        self.job = Job(self.runs, "loop")

    def start(self, loops):
        """
        The loop, detached: this same tool with -f, as a background job
        """
        Approvals(self.path).require("plan")
        command = [sys.executable, str(self.system.bin / "loop"), "-f", self.name, str(loops)]
        pid = self.job.start(command, cwd=self.system.path)
        print(f"loop started (pid {pid}), log: {self.relative(self.job.log)}; "
              f"follow it with dev/bin/status {self.name}")

    def stop(self):
        print(f"loop stopping (pid {self.job.stop()}); dev/bin/status {self.name} shows its record")

    def run(self, loops):
        """
        The loop, in the foreground
        """
        sys.path.insert(0, str(self.system.path / "dev" / "tools"))
        from loop import Loop, shims

        Approvals(self.path).require("plan")
        if self.job.pid not in (None, os.getpid()):
            sys.exit(f"loop already {self.job.state()}")
        self.runs.mkdir(exist_ok=True)
        self.job.pidfile.write_text(str(os.getpid()))
        signal.signal(signal.SIGTERM, interrupt)  # dev/bin/loop --stop: end like Ctrl-C, recorded

        config = Config()
        config.export(os.environ)
        # The author's commands (oracle, readiness, build) from dev/bin; on Windows through .cmd shims
        shim_folder = shims(self.system.bin, self.runs / "bin")
        path = [str(self.system.bin), *windows_tools(), os.environ["PATH"]]
        if shim_folder:
            path.insert(0, str(shim_folder))
        os.environ["PATH"] = os.pathsep.join(path)

        print(f"[loop] {self.name}: {loops} loop(s) with {config.model} on {platform.system()}", flush=True)
        reasoning = str(config.loop("reasoning")).lower() == "true"
        run = Loop(self.path, self.system.path, "oaic-" + config.model, reasoning=reasoning).run(loops)

        host = {"os": platform.platform(), "python": platform.python_version()}
        (run.record / "host.toml").write_text("".join(f'{k} = "{v}"\n' for k, v in host.items()))
        print(f"[loop] {run.stop_reason}, record: {self.relative(run.record)}")

    def status(self):
        print("== approved")
        print("\n".join(lines_starting(self.path / "approvals.toml", "item")) or "nothing")
        print("== groups")
        print("\n".join(lines_starting(self.path / "current_plan.md", "- Group")))
        print("== agent log")
        print(tail(self.path / "agent_log.md") or "empty")
        print(f"== loop: {self.job.state()}")
        print(self.job.tail() or "not run")
        keep = ("run_id", "model", "loops_completed", "stop_reason")
        for record in sorted(self.runs.glob("*/run.toml"), key=lambda p: p.stat().st_mtime)[-3:]:
            fields = [line for line in record.read_text().splitlines() if line.split()[0] in keep]
            print("  " + "  ".join(fields))

    def relative(self, path):
        return path.relative_to(self.system.path).as_posix()


def interrupt(*_):
    raise KeyboardInterrupt


def lines_starting(path, prefix):
    if not path.is_file():
        return []
    return [line for line in path.read_text().splitlines() if line.startswith(prefix)]
