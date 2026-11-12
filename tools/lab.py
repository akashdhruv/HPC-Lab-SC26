"""The tools of the agent systems (tools/README.md).

A tool is a public method of a level's class, run by a stub file of the same name:

    tools/<tool>               the root's tools: class Lab, below
    <system>/dev/bin/<tool>    a system's tools: class <System>(Lab) in <system>/dev/lab.py

A system inherits Lab's tools and may override them. Pure Python (>= 3.8, stdlib only; PyYAML for
config.yaml), so every tool behaves the same on Windows, macOS and Linux.
"""

import datetime
import getpass
import hashlib
import importlib.util
import inspect
import json
import os
import re
import shutil
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = os.name == "nt"
MIN_PYTHON = (3, 10)


# --- Levels: the root and the systems, as a class hierarchy ---------------------------------------


class Level:
    """
    The root or a system (a folder with dev/lab.py). Only two levels exist: the root and its
    direct system children. A system's class subclasses Lab.
    """

    image = None  # the level's docker image; a system sets it
    loaded = {}  # dev/lab.py -> its Level class

    def __init__(self, path):
        self.path = Path(path).resolve()
        self.name = self.path.name
        self.bin = stub_folder(self.path)

    def __repr__(self):
        return self.path.relative_to(ROOT).as_posix() or "."

    @classmethod
    def at(cls, folder):
        """
        The level of folder, as an instance of its class
        """
        return level_class(folder)(folder)

    @property
    def children(self):
        """
        The systems directly below the root (a system has none)
        """
        if self.path != ROOT:
            return []
        return [Level.at(p) for p in sorted(self.path.iterdir())
                if (p / "dev" / "lab.py").is_file()]

    def walk(self):
        """
        This level and every level below it
        """
        yield self
        for child in self.children:
            yield from child.walk()

    @property
    def docker(self):
        if not self.image:
            sys.exit(f"{self} has no image; run it from a system")
        return Container(self)

    def tool_names(self):
        """
        The public methods of this level's classes (Level itself defines none)
        """
        classes = type(self).__mro__[:type(self).__mro__.index(Level)]
        return {name for c in classes for name, value in vars(c).items()
                if inspect.isfunction(value) and not name.startswith("_")}

    @staticmethod
    def flag(args, *flags):
        """
        (flag, rest) if args starts with one of flags, else (None, args)
        """
        if args and args[0] in flags:
            return args[0], list(args[1:])
        return None, list(args)


def stub_folder(level):
    """
    Where a level's stubs are: tools/ for the root, dev/bin/ for a system
    """
    return ROOT / "tools" if level == ROOT else level / "dev" / "bin"


def find_level(path):
    """
    The level holding path: the system directly below the root that contains it, else the root
    """
    path = Path(path).resolve()
    if ROOT not in (path, *path.parents):
        sys.exit(f"{path} is outside {ROOT}")
    for folder in [path, *path.parents]:
        if folder != ROOT and folder.parent == ROOT and (folder / "dev" / "lab.py").is_file():
            return folder
    return ROOT


def level_class(folder):
    """
    The class of a level: Lab for the root, else the one Level subclass in its dev/lab.py
    """
    folder = Path(folder).resolve()
    if folder == ROOT:
        return Lab
    if folder.parent != ROOT or not (folder / "dev" / "lab.py").is_file():
        sys.exit(f"{folder}: not a system (expected dev/lab.py directly under the root)")
    file = folder / "dev" / "lab.py"
    if file not in Level.loaded:
        name = "level_" + re.sub(r"\W", "_", folder.relative_to(ROOT).as_posix())
        spec = importlib.util.spec_from_file_location(name, file)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        classes = [c for c in vars(module).values()
                   if isinstance(c, type) and issubclass(c, Level) and c.__module__ == name]
        if len(classes) != 1:
            sys.exit(f"{file}: define exactly one Level class")
        Level.loaded[file] = classes[0]
    return Level.loaded[file]


def parent(file):
    """
    The class a system's dev/lab.py inherits from:  class Translation(parent(__file__))
    """
    system = Path(file).resolve().parents[1]
    if system.parent != ROOT:
        sys.exit(f"{system}: systems must sit directly under the root")
    return Lab


# --- Stubs: how a stub file runs its tool ---------------------------------------------------------


def main(stub):
    """
    Run the tool named after this stub. A stub runs on the deepest level between its own level and
    the working directory: ../tools/container from mxp-optimization/ runs as mxp-optimization.
    """
    stub, cwd = Path(stub).resolve(), Path.cwd().resolve()
    home = ROOT if stub.parent == ROOT / "tools" else stub.parents[2]
    level = Level.at(find_level(cwd) if home in (cwd, *cwd.parents) else home)

    name, args = stub.name, sys.argv[1:]
    if name not in level.tool_names():
        sys.exit(f"{name}: not a tool of {level} ({type(level).__name__})")
    tool = getattr(level, name)

    if args[:1] in (["-h"], ["--help"]):
        print(usage(stub, tool))
        sys.exit(0)
    try:
        inspect.signature(tool).bind(*args)
    except TypeError:
        sys.exit(usage(stub, tool).splitlines()[0])
    sys.exit(tool(*args) or 0)


def usage(stub, tool):
    """
    "usage: <stub> <arguments>", then the tool's docstring. The arguments come from its signature,
    or from the docstring's start for a tool that parses its own flags: "[-f] <name>: ..."
    """
    doc = inspect.getdoc(tool) or ""
    if doc.startswith(("[", "<")) and ": " in doc:
        arguments, doc = doc.split(": ", 1)
    else:
        arguments = " ".join(argument(p) for p in inspect.signature(tool).parameters.values())
    return f"usage: {Path(os.path.relpath(stub)).as_posix()} {arguments}\n{doc}"


def argument(parameter):
    if parameter.kind == parameter.VAR_POSITIONAL:
        return f"[{parameter.name} ...]"
    if parameter.default is not parameter.empty:
        return f"[{parameter.name}]"
    return f"<{parameter.name}>"


# --- The root's tools, inherited by every system --------------------------------------------------


class Lab(Level):
    """
    The root: setup, and the tools every system inherits
    """

    def approve(self, instance, item, *note):
        """
        Record a human approval in <instance>/approvals.toml. The scientist runs this; agents never do.
        Items: "plan", then "Group <k>" (translate), "result" (raptorize), "candidate <id>" (optimize).
        """
        print(Approvals(instance).add(item, " ".join(note)), end="")

    def container(self, *args):
        """
        [-d] <command ...>: run a command in this system's image, the tutorial mounted at /work and
        the system as workdir (-d: detached, as the container hpc-lab-<system>)
        """
        detach, command = self.flag(args, "-d")
        if not command:
            sys.exit(f"usage: container [-d] <command ...>   (image {self.docker.image})")
        return self.docker.run(command, detach=bool(detach))

    def check(self):
        """
        The system's check (exit 0: it works), which setup runs; here, every system's
        """
        return max([child.check() or 0 for child in self.children], default=0)

    def setup(self, *flags):
        """
        [--native]: one-time setup, safe to rerun: orchestrator links, .venv, pi; then (unless
        --native) the submodules, and the image and check of every system
        """
        need("git", "Git; on Windows Git for Windows, which also provides Git Bash")
        Venv().activate()
        print("CodeScribe ready in .venv (the loop uses it)")
        Orchestrators().link_all()
        if shutil.which("npm") and not shutil.which("pi"):
            run(shutil.which("npm"), "install", "-g", "@earendil-works/pi-coding-agent")
        if shutil.which("pi"):
            print("pi ready")
        if "<your key>" in (ROOT / "config.yaml").read_text():
            print("edit config.yaml: OPENAI_COMP_APIKEY")
        if "--native" in flags:
            return

        need("docker", "Docker Desktop, or Docker Engine on Linux")
        run("git", "submodule", "update", "--init", "--recursive")
        for level in self.walk():
            if level.image and level.docker.build():
                sys.exit(f"failed: docker build of {level}")
        if self.check():
            sys.exit(f"failed: check of {self}")
        print(f"{self}: images built, checks pass")


def need(command, hint):
    if not shutil.which(command):
        sys.exit(f"missing: {command} ({hint})")


def run(*args):
    if subprocess.call(list(args), cwd=ROOT):
        sys.exit(f"failed: {' '.join(map(str, args))}")


# --- Helpers the tools use ------------------------------------------------------------------------


class Container:
    """
    A system's docker image, with the tutorial mounted at /work and the system as workdir
    """

    def __init__(self, level):
        self.level, self.image = level, level.image
        self.workdir = "/work/" + level.path.relative_to(ROOT).as_posix()
        self.name = f"hpc-lab-{level.name}"  # the detached container: one at a time per system

    def command(self, args, detach=False):
        options = ["--rm", "--init", "-w", self.workdir,
                   "--mount", f"type=bind,source={ROOT},target=/work"]
        if hasattr(os, "getuid"):
            options += ["--user", f"{os.getuid()}:{os.getgid()}"]
        if os.environ.get("MAX_PROGRAMS"):
            options += ["-e", f"MAX_PROGRAMS={os.environ['MAX_PROGRAMS']}"]
        if detach:
            options += ["-d", "--name", self.name]
        return ["docker", "run", *options, self.image, *args]

    def run(self, args, detach=False):
        return subprocess.call(self.command(args, detach))

    def build(self):
        return subprocess.call(["docker", "build", "-t", self.image, str(self.level.path)])

    def running(self):
        out = subprocess.run(["docker", "ps", "-q", "-f", f"name=^{self.name}$"],
                             capture_output=True, text=True)
        return bool(out.stdout.strip())

    def stop(self):
        """
        SIGTERM to the detached container, SIGKILL after 30 s
        """
        return subprocess.call(["docker", "stop", "-t", "30", self.name], stdout=subprocess.DEVNULL)


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
        if not self.path.is_file():
            return False
        line = re.compile(r"^item\s*=\s*" + re.escape(json.dumps(item)) + r"\s*$", re.M)
        return bool(line.search(self.path.read_text()))

    def require(self, item):
        if self.has(item):
            return
        rel = lambda path: Path(os.path.relpath(path)).as_posix()
        sys.exit(f"not approved: '{item}' in {rel(self.path)}\n"
                 f"the scientist approves with: {rel(ROOT / 'tools' / 'approve')} "
                 f"{rel(self.instance)} \"{item}\"")

    def add(self, item, note=""):
        entry = "\n".join([
            "",
            "[[approved]]",
            f"item = {json.dumps(item)}",
            f"by = {json.dumps(getpass.getuser())}",
            f"date = \"{datetime.date.today()}\"",
            f"note = {json.dumps(note)}",
            "",
        ])
        with open(self.path, "a", newline="\n") as stream:
            stream.write(entry)
        return entry


class Config:
    """
    config.yaml: the model endpoint of the harnesses (CodeScribe loop, OpenEvolve)
    """

    def __init__(self, path=ROOT / "config.yaml"):
        import yaml  # from .venv; the stubs themselves need only the stdlib

        if not path.is_file():
            sys.exit(f"{path} missing")
        self.path = path
        self.data = yaml.safe_load(path.read_text()) or {}

    def get(self, key, default=""):
        """
        A dotted key ("agent.model"), with ${VARIABLES} expanded
        """
        value = self.data
        for part in key.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        if value in (None, ""):
            return default
        return os.path.expandvars(str(value))

    @property
    def model(self):
        return self.get("agent.loop_model") or self.get("agent.model")

    def claude_settings(self):
        """
        Claude Code settings for the claude: endpoint of config.yaml; {} unless claude.enabled
        """
        if self.get("claude.enabled").lower() != "true":
            return {}
        model = self.get("claude.model")
        env = {
            "ANTHROPIC_BASE_URL": self.get("claude.base_url") or sys.exit(f"set claude.base_url in {self.path}"),
            "ANTHROPIC_DEFAULT_OPUS_MODEL": self.get("claude.opus_model", model),
            "ANTHROPIC_DEFAULT_SONNET_MODEL": self.get("claude.sonnet_model", model),
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": self.get("claude.haiku_model", model),
            "CLAUDE_CODE_MAX_OUTPUT_TOKENS": self.get("claude.max_output_tokens"),
        }
        if self.get("claude.api_key"):
            env["ANTHROPIC_AUTH_TOKEN"] = self.get("claude.api_key")
        settings = {"env": {k: v for k, v in env.items() if v}, "model": model}
        if self.get("claude.api_key_helper"):
            settings["apiKeyHelper"] = self.get("claude.api_key_helper")
        return settings

    def export(self, env):
        """
        The endpoint as the OPENAI_COMP_* variables CodeScribe reads
        """
        for key in ["OPENAI_COMP_BASEURL", "OPENAI_COMP_APIKEY", "OPENAI_COMP_PROVIDER"]:
            env[key] = self.get(key) or sys.exit(f"set {key} in {self.path}")
        env["CODESCRIBE_MAX_TOKENS"] = self.get("agent.max_tokens", "16384")
        return env


class Job:
    """
    A harness run on the host, detached from the session that starts it: <folder>/<name>.pid and
    <name>.log, so a later session can probe it, follow its log or stop it
    """

    def __init__(self, folder, name):
        self.folder = Path(folder)
        self.pidfile = self.folder / f"{name}.pid"
        self.log = self.folder / f"{name}.log"

    @property
    def pid(self):
        """
        The pid of the running job, or None
        """
        text = self.pidfile.read_text().strip() if self.pidfile.is_file() else ""
        return int(text) if text.isdigit() and alive(int(text)) else None

    def state(self):
        return f"running (pid {self.pid})" if self.pid else "not running"

    def start(self, command, cwd):
        if self.pid:
            sys.exit(f"already {self.state()}; stop it first")
        self.folder.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}
        with open(self.log, "a") as log:
            process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT, **detached())
        self.pidfile.write_text(str(process.pid))
        return process.pid

    def stop(self):
        """
        SIGTERM (TerminateProcess on Windows): the harness records its state and exits
        """
        pid = self.pid or sys.exit("not running")
        os.kill(pid, signal.SIGTERM)
        return pid

    def tail(self, n=6):
        if not self.log.is_file():
            return ""
        return "\n".join(self.log.read_text().splitlines()[-n:])


def alive(pid):
    if WINDOWS:  # os.kill(pid, 0) would terminate it
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
        return str(pid) in out.stdout.split()
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    return True


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


class Venv:
    """
    The tutorial's .venv: made, and synced to tools/requirements.txt, on first use by any tool
    """

    def __init__(self):
        self.path = ROOT / ".venv"
        self.bin = self.path / ("Scripts" if WINDOWS else "bin")
        self.python = self.bin / ("python.exe" if WINDOWS else "python")
        self.requirements = ROOT / "tools" / "requirements.txt"
        self.stamp = self.path / "requirements.sha256"

    def ensure(self):
        want = hashlib.sha256(self.requirements.read_bytes()).hexdigest()
        if self.python.is_file() and self.stamp.is_file() and self.stamp.read_text() == want:
            return self
        print(f"setting up {self.path.name} ...", file=sys.stderr)
        # check if uv is available
        uv = shutil.which("uv")
        if not self.python.is_file():
            if uv:
                call(uv, "venv", "--quiet", "--seed", "--clear", "--python", ">=%d.%d" % MIN_PYTHON,
                     self.path)
            else:
                call(*base_python(), "-m", "venv", self.path)
        if uv:
            call(uv, "pip", "install", "--quiet", "--python", self.python, "-r", self.requirements)
        else:
            if not has_pip(self.python):
                call(self.python, "-m", "ensurepip", "--upgrade")
            call(self.python, "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
                 "-r", self.requirements)
        self.stamp.write_text(want)
        return self

    def activate(self):
        """
        Rerun this script in .venv, as `activate` would: VIRTUAL_ENV set, the venv's bin first on
        PATH (so a child `python` is the venv's)
        """
        self.ensure()
        os.environ.pop("PYTHONHOME", None)
        os.environ["VIRTUAL_ENV"] = str(self.path)
        if os.environ["PATH"].split(os.pathsep)[0] != str(self.bin):
            os.environ["PATH"] = os.pathsep.join([str(self.bin), os.environ["PATH"]])
        if Path(sys.prefix).resolve() != self.path.resolve():
            sys.exit(subprocess.call([str(self.python), *sys.argv]))


def base_python():
    """
    A python >= MIN_PYTHON to make the venv from (the stubs themselves run on any python 3)
    """
    names = [sys.executable, *(f"python3.{minor}" for minor in range(14, MIN_PYTHON[1] - 1, -1)),
             "python3", "python", "py"]
    for name in names:
        path = shutil.which(name) or (name if Path(name).is_file() else None)
        if not path:
            continue
        python = [path, "-3"] if name == "py" else [path]
        recent = [*python, "-c", f"import sys; sys.exit(sys.version_info < {MIN_PYTHON})"]
        if subprocess.call(recent, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
            return python
    sys.exit("missing: python >= %d.%d" % MIN_PYTHON)


def has_pip(python):
    quiet = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    return subprocess.call([str(python), "-m", "pip", "--version"], **quiet) == 0


def call(*args):
    if subprocess.call([str(a) for a in args], stdout=sys.stderr):
        sys.exit(f"failed: {' '.join(map(str, args))}")


class Orchestrators:
    """
    Codex and OpenCode read AGENTS.md and .agents/skills; Claude Code and pi read their own folder
    of the directory they start in, so link it (untracked) to .agents, in the root and each system
    """

    LINKS = {
        ".claude/settings.json": ".agents/adapters/claude/settings.json",
        ".pi/settings.json": ".agents/adapters/pi/settings.json",
        ".pi/extensions/hpclab": ".agents/adapters/pi/hpclab",
    }

    def link_all(self):
        for folder in [ROOT, *sorted(p.parent for p in ROOT.glob("*/AGENTS.md"))]:
            links = {path: ROOT / target for path, target in self.LINKS.items()}
            if (folder / ".agents" / "skills").is_dir():
                links[".claude/skills"] = folder / ".agents" / "skills"
            for path, target in links.items():
                link(folder / path, target)
            self.claude_endpoint(folder / ".claude" / "settings.local.json")
        print("Claude Code and pi linked to .agents")

    def claude_endpoint(self, path):
        """
        The config.yaml claude: endpoint merged into settings.local.json (the user's other keys stay)
        """
        keys = ["env", "model", "apiKeyHelper"]
        settings = json.loads(path.read_text()) if path.is_file() else {}
        settings = {k: v for k, v in settings.items() if k not in keys}
        settings.update(Config().claude_settings())
        if settings:
            path.write_text(json.dumps(settings, indent=2) + "\n")
        elif path.is_file():
            path.unlink()


def link(path, target):
    """
    A relative symlink; on Windows without symlink rights, a junction (folder) or a copy (file)
    """
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        path.rmdir()  # a junction; refuses a real folder with content
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(os.path.relpath(target, path.parent), path, target_is_directory=target.is_dir())
    except OSError:
        if target.is_dir():
            import _winapi
            _winapi.CreateJunction(str(target), str(path))
        else:
            shutil.copyfile(target, path)


# --- Orchestrator PATH (config.yaml: orchestrator.dev_bin_on_path) --------------------------------


def stub_folders(start):
    """
    The stub folders from start's level up to the root, deepest first, relative to the root
    """
    start = Path(start).resolve()
    if ROOT not in (start, *start.parents):
        return []
    folders, level = [], find_level(start)
    while True:
        folders.append(stub_folder(level).relative_to(ROOT).as_posix())
        if level == ROOT:
            return folders
        level = find_level(level.parent)


if __name__ == "__main__" and sys.argv[1:2] == ["bins"]:  # the Claude Code hook: .agents/adapters/claude
    if str(Config().get("orchestrator.dev_bin_on_path")).lower() == "true":
        print("\n".join(stub_folders(sys.argv[2] if len(sys.argv) > 2 else ".")))
