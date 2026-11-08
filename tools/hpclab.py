"""Host-side helpers shared by the agent systems: config.yaml, approvals, docker.

Pure Python (>= 3.8, stdlib only, except PyYAML for config.yaml), so every entry point in
tools/ and <system>/dev/bin/ behaves the same on Windows, macOS and Linux, under any
orchestrator. Each entry point is an extensionless script (sh/python polyglot, for POSIX shells
and Git Bash) with a one-line .cmd twin (for cmd.exe and PowerShell).
"""

import datetime
import getpass
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = os.name == "nt"


class Venv:
    """
    The tutorial's .venv: made, and synced to tools/requirements.txt, on first use by any entry point
    """

    def __init__(self):
        self.path = ROOT / ".venv"
        self.bin = self.path / ("Scripts" if WINDOWS else "bin")
        self.python = self.bin / ("python.exe" if WINDOWS else "python")
        self.requirements = ROOT / "tools" / "requirements.txt"
        self.stamp = self.path / "requirements.sha256"

    @staticmethod
    def base_python():
        """
        A python >= 3.10 to make the venv from (the entry points themselves run on any python 3)
        """
        names = [sys.executable] + [f"python3.{m}" for m in range(14, 9, -1)] + ["python3", "python", "py"]
        for name in names:
            path = shutil.which(name) or (name if Path(name).is_file() else None)
            probe = [path, "-3"] if name == "py" else [path]
            if path and subprocess.call([*probe, "-c", "import sys; sys.exit(sys.version_info < (3, 10))"],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
                return probe
        sys.exit("missing: python >= 3.10")

    @staticmethod
    def run(*args):
        if subprocess.call([str(a) for a in args], stdout=sys.stderr):
            sys.exit(f"failed: {' '.join(map(str, args))}")

    def ensure(self):
        want = hashlib.sha256(self.requirements.read_bytes()).hexdigest()
        if self.python.is_file() and self.stamp.is_file() and self.stamp.read_text() == want:
            return self
        print(f"setting up {self.path.name} ...", file=sys.stderr)
        if not self.python.is_file():
            self.run(*self.base_python(), "-m", "venv", self.path)
        if subprocess.call([str(self.python), "-m", "pip", "--version"], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL):
            self.run(self.python, "-m", "ensurepip", "--upgrade")
        self.run(self.python, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "-r", self.requirements)
        self.stamp.write_text(want)
        return self

    def activate(self):
        """
        Run this script in .venv, as `activate` would: VIRTUAL_ENV and the venv's bin first on PATH
        (so child `python` is the venv's), then rerun under the venv's python
        """
        self.ensure()
        os.environ.pop("PYTHONHOME", None)
        os.environ["VIRTUAL_ENV"] = str(self.path)
        if os.environ["PATH"].split(os.pathsep)[0] != str(self.bin):
            os.environ["PATH"] = os.pathsep.join([str(self.bin), os.environ["PATH"]])
        if Path(sys.prefix).resolve() != self.path.resolve():
            sys.exit(subprocess.call([str(self.python), sys.argv[0], *sys.argv[1:]]))


def detached():
    """
    Popen options that let a background process outlive the shell that started it
    """
    if WINDOWS:
        return {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def windows_tools():
    """
    On Windows, Git for Windows' usr/bin (ls, grep, sed, cat, diff ...) for commands run by cmd.exe
    """
    git = shutil.which("git")
    if not WINDOWS or not git:
        return []
    usr = Path(git).resolve().parents[1] / "usr" / "bin"
    return [str(usr)] if usr.is_dir() else []


class Config:
    """
    config.yaml: the model endpoint of the harnesses (CodeScribe loop, OpenEvolve)
    """

    def __init__(self, path=ROOT / "config.yaml"):
        import yaml

        if not path.is_file():
            sys.exit(f"{path} missing")
        self.path = path
        self.data = yaml.safe_load(path.read_text()) or {}

    def get(self, key, default=""):
        value = self.data
        for part in key.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        return os.path.expandvars(str(value)) if value not in (None, "") else default

    @property
    def model(self):
        return self.get("agent.loop_model") or self.get("agent.model")

    def export(self, env):
        """
        The endpoint as the OPENAI_COMP_* variables CodeScribe reads
        """
        for key in ["OPENAI_COMP_BASEURL", "OPENAI_COMP_APIKEY", "OPENAI_COMP_PROVIDER"]:
            env[key] = self.get(key) or sys.exit(f"set {key} in {self.path}")
        env["CODESCRIBE_MAX_TOKENS"] = self.get("agent.max_tokens", "16384")
        return env


class Approvals:
    """
    approvals.toml of an instance: written only by the scientist, read by every act step
    """

    def __init__(self, instance):
        self.instance = Path(instance)
        self.path = self.instance / "approvals.toml"
        if not self.instance.is_dir():
            sys.exit(f"no {self.instance}")

    def has(self, item):
        pattern = re.compile(r"^item\s*=\s*" + re.escape(json.dumps(item)) + r"\s*$", re.M)
        return self.path.is_file() and bool(pattern.search(self.path.read_text()))

    def require(self, item):
        if not self.has(item):
            rel = lambda path: Path(os.path.relpath(path)).as_posix()
            sys.exit(
                f"not approved: '{item}' in {rel(self.path)}\n"
                f"the scientist approves with: {rel(ROOT / 'tools' / 'approve')} {rel(self.instance)} \"{item}\""
            )

    def add(self, item, note=""):
        entry = (
            f"\n[[approved]]\nitem = {json.dumps(item)}\nby = {json.dumps(getpass.getuser())}\n"
            f"date = \"{datetime.date.today()}\"\nnote = {json.dumps(note)}\n"
        )
        with open(self.path, "a", newline="\n") as stream:
            stream.write(entry)
        return entry


class Container:
    """
    A system's docker image, with the tutorial mounted at /work and the system as workdir
    """

    IMAGES = {"code-translation": "hpc-lab-translate", "mxp-optimization": "hpc-lab-mxp"}

    def __init__(self, system):
        self.system, self.image = system, self.IMAGES[system]

    @classmethod
    def of(cls, path):
        """
        The Container of the agent system that holds path
        """
        path = Path(path).resolve()
        for system in cls.IMAGES:
            if ROOT / system in (path, *path.parents):
                return cls(system)
        sys.exit(f"{path} is in no agent system ({', '.join(cls.IMAGES)})")

    def build(self):
        return subprocess.call(["docker", "build", "-t", self.image, str(ROOT / self.system)])

    def command(self, args, detach=False):
        options = ["--rm", "--init", "-w", f"/work/{self.system}"]
        options += ["--mount", f"type=bind,source={ROOT},target=/work"]
        if hasattr(os, "getuid"):
            options += ["--user", f"{os.getuid()}:{os.getgid()}"]
        if os.environ.get("MAX_PROGRAMS"):
            options += ["-e", f"MAX_PROGRAMS={os.environ['MAX_PROGRAMS']}"]
        if detach:
            options += ["-d", "--name", f"hpc-lab-{self.system}"]
        return ["docker", "run", *options, self.image, *args]

    def run(self, args, detach=False):
        return subprocess.call(self.command(args, detach))

    def main(self, argv):
        """
        <command ...> or -d <command ...> (detached, as the container hpc-lab-<system>)
        """
        detach = bool(argv) and argv[0] == "-d"
        args = argv[1:] if detach else argv
        if not args:
            sys.exit(f"usage: container [-d] <command ...>   (image {self.image})")
        sys.exit(self.run(args, detach))
