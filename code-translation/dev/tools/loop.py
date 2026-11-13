"""code-translation's autonomous loop: author -> check -> review, on CodeScribe's library primitives.

    Loop(instance, workdir, "oaic-<model>").run(loops)

A Task is a loop.toml (the author's chat, a [tools] policy, a [check] command). A Loop is one run
of it, recorded in <instance>/runs/<run_id>/. The harness enforces protected files and the check
command; the agents decide everything else.

  - protected files: [tools].protect and loop.toml itself. write/edit refuse them; a change made
    through bash is reverted after every call and recorded as a violation.
  - check: [check].command runs after every author session; its exit code is ground truth.
  - stop: the author reports COMPLETE and the check passes; or the review finds no pending items
    and no blocker; else when the loop budget runs out.
"""

import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from importlib.metadata import version
from pathlib import Path

import toml
from codescribe import lib

CHECK_TAIL = 4000
MAX_DIFF = 20000

REVIEW_BASH = {"ls", "stat", "pwd", "find", "grep", "head", "tail", "rg", "cat", "diff"}


class Loop:
    """
    One run of a Task: author -> check -> review, until the harness decides to stop.
    """

    def __init__(self, instance, workdir, model, task="loop.toml", reasoning=False,
                 iterations=30, verbose=True):
        self.instance = Path(instance).resolve()
        self.workdir = Path(workdir).resolve()
        self.task = Task(within(self.instance / task, self.workdir))
        self.model_name = model
        self.model = lib.set_neural_model(model, reasoning=reasoning)
        self.iterations = iterations
        self.verbose = verbose

        self.id = lib.new_run_id()
        self.record = self.instance / "runs" / self.id
        (self.record / "metadata").mkdir(parents=True, exist_ok=True)
        agent_log = self.instance / "agent_log.md"
        if not agent_log.exists():
            agent_log.write_text("")

        self.workspace = Workspace(self.workdir)
        self.guard = Guard(self.workdir, [self.rel(self.task.path), *self.task.protect])
        self.rules = []

        self.sessions = []
        self.reviews = []
        self.pending = []  # open review items
        self.blocker = ""
        self.scores = []
        self.phases = []
        self.done = 0
        self.stop_reason = "max_loops"

    def run(self, loops=10):
        try:
            self.iterate(loops)
        except KeyboardInterrupt:
            self.stop_reason = "stopped"
        self.persist(loops)
        self.say(f"\n= {self.stop_reason} after {self.done}/{loops} loop(s)")
        return self

    def iterate(self, loops):
        for loop in range(1, loops + 1):
            self.task.chat = lib.load_chat_template(self.task.path)
            session = self.author(loop, loops)
            self.done = loop

            if session.status() == "COMPLETE" and session.check and session.check.passed:
                self.pending, self.blocker = [], ""
                self.stop_reason = "complete"
                return

            if self.review(loop, session):
                self.stop_reason = "complete"
                return

            self.persist(loops)

            if not session.changed and not session.violations:
                self.stop_reason = "stalled"
                return

    def author(self, loop, loops):
        self.say(f"\n> loop {loop} [author]")
        self.guard.snapshot()
        before = self.workspace.tree()
        result = self.session(loop, "author", self.author_tools(), AUTHOR_SYSTEM,
                              self.author_prompt(loop, loops), self.iterations)
        self.guard.restore()
        after = self.workspace.tree()

        session = Session.of(loop, result)
        session.violations = list(self.guard.violations)
        session.diff = self.workspace.diff(before, after)
        session.changed = (before != after) if before else bool(session.written or session.edited)

        if self.task.check:
            session.check = Check.run(self.task.check, self.workdir, self.task.timeout)
            self.say(f"  check `{session.check.command}`: {'PASS' if session.check.passed else 'FAIL'}")
        if session.violations:
            self.say("  protected files reverted: " + "; ".join(session.violations))
        self.sessions.append(session)
        return session

    def review(self, loop, session):
        """
        Run the review; return True if it reports the task complete.
        """
        self.say(f"\n> loop {loop} [review]")
        (self.record / "review.toml").unlink(missing_ok=True)
        result = self.session(loop, "review", self.review_tools(), REVIEW_SYSTEM,
                              self.review_prompt(loop, session), max(6, self.iterations // 2))
        self.reviews.append(Session.of(loop, result))

        review = lib.read_toml(self.record / "review.toml")
        if review:
            (self.record / "review.toml").replace(self.record / f"review_{loop:03d}.toml")
        pending = review.get("pending") if isinstance(review, dict) else None
        self.pending = [str(x.get("item") if isinstance(x, dict) else x).strip()
                        for x in (pending or []) if str(x).strip()]
        self.blocker = str((review or {}).get("blocker") or "").strip()
        if not self.pending and not self.blocker:
            self.pending, self.blocker = [], ""
            return True
        if not review:  # no review written: carry the author's next steps
            self.pending = session.next_steps()
        return False

    def session(self, loop, phase, tools, system, prompt, iterations):
        events = self.record / "events" / f"loop_{loop:03d}_{phase}.toml"
        events.parent.mkdir(parents=True, exist_ok=True)
        agent = lib.Agent(self.model, tools=tools, max_iterations=iterations,
                          show_diagnostics=self.verbose,
                          logging=lib.ToolLogToml(path=str(events)))
        timer = lib.Timer()
        result = agent.run(prompt, system=system, chat_history=self.task.chat)
        self.phases.append(lib.write_loop_phase_metadata(
            self.record / "metadata", run_id=self.id, loop_index=loop, phase=phase,
            model=self.model_name, task_file=str(self.task.path), workdir=str(self.workdir),
            stop_reason=result.stop_reason, final_text_present=bool(result.final_text),
            usage=result.usage, iterations=result.iterations, tool_results=result.tool_results,
            rejected_calls=result.rejected_calls, duration_s=timer.ms / 1000))
        return result

    def author_tools(self):
        return lib.make_tools(self.workdir, bash_allow=self.task.bash,
                              protected_paths=self.protected())

    def review_tools(self):
        tools = [t for t in lib.make_tools(self.workdir, protected_paths=self.protected())
                 if t.name in ("read", "glob", "write")]
        tools.append(lib.BashTool(cwd=self.workdir, bounded=True, allowed_commands=REVIEW_BASH,
                                  protected_paths=self.protected()))
        return tools

    def protected(self):
        return {self.task.path, *self.guard.paths()}

    def persist(self, loops):
        usages = [s.usage for s in self.sessions + self.reviews if s.usage]
        tokens = {k: sum(getattr(u, k, 0) or 0 for u in usages)
                  for k in ("input", "output", "cache_read", "cache_write")}
        run = {"run_id": self.id, "model": self.model_name, "workdir": str(self.workdir),
               "task_file": self.rel(self.task.path), "agent_loops": loops,
               "loops_completed": self.done, "agent_iterations": self.iterations,
               "stop_reason": self.stop_reason, "codescribe": version("CodeScribe"),
               "tokens": tokens, "score": []}
        lib.atomic_write_toml(self.record / "run.toml", run)
        lib.atomic_write_toml(self.record / "rules.toml", {"protected": self.guard.rel()})
        lib.write_loop_manifest(self.record / "metadata", run_doc=run, phase_files=self.phases)

    def policy(self):
        protected = self.guard.rel()
        if not protected:
            return ""
        return ("HARNESS-ENFORCED POLICY\nProtected files (read-only; any change is reverted): "
                + ", ".join(protected))

    def author_prompt(self, loop, loops):
        lines = [f"Loop {loop} of {loops}."]
        created = unique(f for s in self.sessions for f in s.written)
        edited = unique(f for s in self.sessions for f in s.edited)
        if created:
            lines.append("Files created across all prior loops: " + ", ".join(created))
        if edited:
            lines.append("Files edited across all prior loops: " + ", ".join(edited))
        if self.sessions:
            last = self.sessions[-1]
            if last.check:
                lines.append(last.check.render())
            if last.errors:
                lines.append("Last loop errors: " + "; ".join(last.errors[:5]))
            if last.violations:
                lines.append("VIOLATION last loop - you changed protected files and the harness "
                             "reverted them: " + "; ".join(last.violations) + ". Do not repeat.")
        if self.blocker:
            lines.append(f"Reviewer blocker: {self.blocker}")
        if self.pending:
            lines.append("Open review items (resolve every one):")
            lines += [f"  - {item}" for item in self.pending]
        elif loop > 1:
            lines.append("No open review items - determine the next action from the task.")
        context = "\n".join(lines)
        if self.policy():
            context += "\n\n" + self.policy()
        allowed = ", ".join(sorted(set(lib.BashTool._DEFAULT_ALLOWED) | self.task.bash))
        check = f"   The harness check is `{self.task.check}`.\n" if self.task.check else ""
        return AUTHOR_TASK.format(context=context, workdir=self.workdir, task=self.rel(self.task.path),
                                  allowed=allowed, check=check)

    def review_prompt(self, loop, session):
        facts = [f"## Verified actions from loop {loop} (harness-computed)"]
        for label, files in [("Files read", session.read), ("Files written", session.written),
                             ("Files edited", session.edited)]:
            if files:
                facts.append(f"{label}: " + ", ".join(files))
        for label, rows in [("Commands run", session.commands), ("Errors", session.errors)]:
            if rows:
                facts.append(f"{label}:")
                facts += [f"  {row}" for row in rows]
        if len(facts) == 1:
            facts.append("  (no verified actions)")
        blocks = ["\n".join(facts)]
        if session.check:
            blocks.append("## " + session.check.render(tail=True))
        if session.diff:
            blocks.append(f"## Workspace diff from loop {loop}\n```diff\n{session.diff}```")
        elif not session.changed:
            blocks.append("## Workspace diff: the author changed nothing.")
        if session.violations:
            blocks.append("## Protected-file violations (harness reverted these)\n  " +
                          "\n  ".join(session.violations))
        if session.rejected:
            blocks.append("## Attempted but NOT executed (harness-rejected)\n  " +
                          "\n  ".join(session.rejected))
        if self.pending:
            blocks.append("## Open review items from earlier loops\n" +
                          "\n".join(f"  - {item}" for item in self.pending))
        if self.policy():
            blocks.append(self.policy())
        if session.answer:
            blocks.append(f"[Author agent report - loop {loop}]\n\n{session.answer}")
        return REVIEW_TASK.format(workdir=self.workdir, task=self.rel(self.task.path), loop=loop,
                                  output=self.rel(self.record / "review.toml"),
                                  evidence="\n\n".join(blocks))

    def rel(self, path):
        return Path(path).resolve().relative_to(self.workdir).as_posix()

    def say(self, text):
        if self.verbose:
            print(text, flush=True)


class Task:
    def __init__(self, path):
        self.path = Path(path).resolve()
        data = toml.loads(self.path.read_text())
        tools = data.get("tools", {})
        check = data.get("check", {})
        self.bash = set(tools.get("bash", []))
        self.protect = list(tools.get("protect", []))
        self.writable = list(tools.get("writable", []))
        self.check = check.get("command", "")
        self.timeout = int(check.get("timeout", 600))
        self.chat = lib.load_chat_template(self.path)


@dataclass
class Check:
    command: str
    passed: bool
    code: int
    tail: str

    @classmethod
    def run(cls, command, cwd, timeout):
        result = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True,
                                timeout=timeout, errors="replace")
        tail = (result.stdout + result.stderr)[-CHECK_TAIL:]
        return cls(command, result.returncode == 0, result.returncode, tail)

    def render(self, tail=False):
        status = "PASS" if self.passed else "FAIL"
        text = f"Check `{self.command}`: {status} (exit {self.code})"
        if tail and self.tail:
            text += "\n" + self.tail
        return text


@dataclass
class Session:
    loop: int
    answer: str = ""
    written: list = field(default_factory=list)
    edited: list = field(default_factory=list)
    read: list = field(default_factory=list)
    commands: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    rejected: list = field(default_factory=list)
    violations: list = field(default_factory=list)
    changed: bool = False
    diff: str = ""
    check: object = None
    usage: object = None

    @classmethod
    def of(cls, loop, result):
        session = cls(loop, answer=result.final_text or "", usage=result.usage)
        for call in result.tool_results:
            target = describe(call.name, call.args)
            output = (call.output_preview or "").strip()
            if not call.ok:
                session.errors.append(f"{call.name}({target}): {output[:80] or 'unknown error'}")
            elif call.name == "write":
                session.written.append(target)
            elif call.name == "edit":
                session.edited.append(target)
            elif call.name == "read":
                session.read.append(target)
            elif call.name == "bash":
                first = output.splitlines()[0] if output else ""
                session.commands.append(f"{target}  ->  {first[:60]}")
        session.rejected = [f"{c.name}({describe(c.name, c.args)}): {c.reason}"
                            for c in result.rejected_calls]
        return session

    def status(self):
        for line in self.answer.splitlines():
            line = line.strip().upper()
            if not line.startswith("STATUS:"):
                continue
            value = line[len("STATUS:"):].strip()
            if value.startswith("COMPLETE"):
                return "COMPLETE"
            if value.startswith("INCOMPLETE"):
                return "INCOMPLETE"
            return None
        return None

    def next_steps(self):
        steps, inside = [], False
        for line in self.answer.splitlines():
            line = line.strip()
            if line.upper().startswith("NEXT STEPS"):
                inside = True
            elif inside and line.startswith("#"):
                break
            elif inside and line.startswith("-"):
                steps.append(line.lstrip("- ").strip())
        return steps[:5]


class Guard:
    def __init__(self, root, patterns):
        self.root = Path(root).resolve()
        self.base = list(patterns)
        self.patterns = list(patterns)
        self.saved = {}
        self.violations = []

    def paths(self):
        result = []
        for pattern in self.patterns:
            p = Path(pattern)
            if any(c in pattern for c in "*?["):
                result.extend(self.root.glob(pattern))
            else:
                candidate = self.root / pattern
                if candidate.exists():
                    result.append(candidate)
        return [p for p in result if p.is_file()]

    def rel(self):
        return [p.relative_to(self.root).as_posix() for p in self.paths()]

    def snapshot(self):
        self.saved = {p: p.read_bytes() for p in self.paths() if p.is_file()}
        self.violations = []

    def restore(self):
        for path, content in self.saved.items():
            if path.is_file() and path.read_bytes() != content:
                path.write_bytes(content)
                self.violations.append(path.relative_to(self.root).as_posix())
        for path in self.paths():
            if path not in self.saved and path.is_file():
                path.unlink()
                self.violations.append(path.relative_to(self.root).as_posix() + " (new file reverted)")
        self.saved = {}


class Workspace:
    def __init__(self, root):
        self.root = Path(root).resolve()

    def git(self, *args, env=None):
        return subprocess.run(["git", *args], cwd=self.root, env=env, capture_output=True,
                              text=True, errors="replace", check=True).stdout

    def tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
            try:
                self.git("add", "-A", "--", ".", env=env)
                return self.git("write-tree", env=env).strip()
            except (OSError, subprocess.CalledProcessError):
                return ""

    def diff(self, before, after):
        if not before or not after or before == after:
            return ""
        try:
            diff = self.git("diff", "--relative", before, after)
        except (OSError, subprocess.CalledProcessError):
            return ""
        if len(diff) > MAX_DIFF:
            diff = diff[:MAX_DIFF] + "\n[diff truncated; read the files]\n"
        return diff


def shims(bin, folder):
    if os.name != "nt":
        return None
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for stub in Path(bin).iterdir():
        if stub.is_file() and not stub.suffix:
            (folder / f"{stub.name}.cmd").write_bytes(f'@python "{stub.resolve()}" %*\r\n'.encode())
    return folder


def within(path, root):
    path = Path(path).resolve()
    path.relative_to(Path(root).resolve())
    return path


def read_bytes(path):
    try:
        return Path(path).read_bytes() if Path(path).is_file() else None
    except OSError:
        return None


def describe(tool, args):
    args = args if isinstance(args, dict) else {}
    if tool == "bash":
        return (args.get("command") or "").replace("\n", " ").strip()[:80]
    if tool in ("read", "write", "edit"):
        return str(args.get("path", ""))
    return ""


def unique(values):
    return list(dict.fromkeys(values))


AUTHOR_TASK = """Working directory: {workdir}
Task file: {task} (read-only)
Allowed bash commands (no pipes, redirects or shell metacharacters): {allowed}

PHASE: AUTHOR

Goal: do as much of the task as this session allows, verify it, and stop only when it is done
or you are genuinely blocked. The harness runs its own check after you finish; your report
cannot override it.

Protocol:
1. The specification is the conversation above and prior work is summarised: do NOT re-read
   the task file or re-glob the workspace to orient yourself.
2. Write a short PLAN (3-7 bullets).
3. Execute it autonomously; do not ask for confirmation.
4. Before each set of tool calls, state in one or two sentences what you do and why.
5. Inspect files before editing them; run the closest check after each meaningful change.
{check}6. A stop condition in the task file or a binding rule (e.g. waiting for human approval) is a
   hard blocker: stop, report STATUS: INCOMPLETE and name it in NEXT STEPS. Never work around it.

Finish with <final_answer> containing, in order:
- `STATUS: COMPLETE` only if the task file's completion criteria are met (every unit in the
  current scope verified) and all checks pass; otherwise `STATUS: INCOMPLETE`. A single settled
  unit or a passing review fix is not completion.
- The PLAN you followed, naming the review item ids you resolved.
- The exact output of the checks you ran.
- Only if INCOMPLETE: the line `NEXT STEPS:` and 3-5 concrete bullets for the next loop.
"""

REVIEW_TASK = """Working directory: {workdir}
Task file: {task} (read-only; its specification is the conversation above)
Review output: {output} (write here)

PHASE: REVIEW

Evidence from loop {loop}:
{evidence}

Write your review to {output} as TOML with:
  blocker = "..."   (empty if none)
  pending = [{{item = "..."}}, ...]   (open items to resolve; empty if done)

Approve completed work; raise only concrete, actionable items. Do not restate the spec.
"""
