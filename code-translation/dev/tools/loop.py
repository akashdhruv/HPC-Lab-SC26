"""code-translation's autonomous loop: author -> check -> review, on CodeScribe's library primitives.

    Loop(instance, workdir, "oaic-<model>").run(loops)

A Task is a loop.toml (the author's chat, a [tools] policy, a [check] command). A Loop is one run
of it, recorded in <instance>/runs/<run_id>/. The harness, not the agents, enforces the policy and
decides when to stop:

  - protected files: [tools].protect and loop.toml itself. write/edit refuse them; a change made
    through bash is reverted after every call and recorded as a violation.
  - rules: added and retired by the reviewer. `deny_bash` refuses matching author commands;
    `protect` locks a file while the rule is active ([tools].writable files can never be locked).
  - check: [check].command runs after every author session; its exit code is ground truth.
  - stop: the author reports COMPLETE and the check passes (the task decides when: a session settles
    one unit, so a clean review is progress, not the end); "stalled" after `stall` loops without
    progress (a change the review accepts, or that resolves items or fixes the check); else when
    the loop budget runs out.
"""

import fnmatch
import os
import re
import shlex
import subprocess
import tempfile
from dataclasses import dataclass, field
from importlib.metadata import version
from pathlib import Path

import toml
from codescribe import lib

MAX_ITEMS = 8  # open review items the author sees
MAX_RULES = 12  # binding rules kept; the oldest go first
CHECK_TAIL = 4000  # characters of check output kept
MAX_DIFF = 20000  # characters of workspace diff shown to the reviewer
GLOB = "*?["  # a pattern with one of these is a glob

REVIEW_BASH = {"ls", "stat", "pwd", "find", "grep", "head", "tail", "rg", "cat", "diff"}


# --- The loop -------------------------------------------------------------------------------------


class Loop:
    """
    One run of a Task: author -> check -> review, until the harness decides to stop
    """

    def __init__(self, instance, workdir, model, task="loop.toml", reasoning=False, iterations=30,
                 stall=2, verbose=True):
        self.instance = Path(instance).resolve()
        self.workdir = Path(workdir).resolve()
        self.task = Task(within(self.instance / task, self.workdir))
        self.model_name = model
        self.model = lib.set_neural_model(model, reasoning=reasoning)
        self.iterations = iterations  # tool calls per author session
        self.stall = stall  # loops without progress before stopping
        self.verbose = verbose

        # the record of this run
        self.id = lib.new_run_id()
        self.record = self.instance / "runs" / self.id
        self.review_file = self.record / "review.toml"
        (self.record / "metadata").mkdir(parents=True, exist_ok=True)
        agent_log = self.instance / "agent_log.md"
        if not agent_log.exists():
            agent_log.write_text("")

        # what the harness enforces
        self.workspace = Workspace(self.workdir)
        self.guard = Guard(self.workdir, [self.rel(self.task.path), *self.task.protect])
        self.rules = []  # binding rules from the reviewer

        # what happened so far
        self.sessions = []  # author sessions
        self.reviews = []  # review sessions
        self.items = []  # open review items
        self.next_item = 1
        self.blocker = ""
        self.problems = []  # the last review's rules the harness rejected
        self.history = []  # every rejected rule of the run
        self.scores = []
        self.phases = []  # metadata files, one per session
        self.done = 0
        self.stop_reason = "max_loops"

    def run(self, loops=10):
        try:
            self.iterate(loops)
        except KeyboardInterrupt:  # Ctrl-C or dev/bin/loop --stop
            self.stop_reason = "stopped"
        self.persist(loops)
        self.say(f"\n= {self.stop_reason} after {self.done}/{loops} loop(s)")
        return self

    def iterate(self, loops):
        for loop in range(1, loops + 1):
            self.task.chat = lib.load_chat_template(self.task.path)  # the human may edit it between loops
            session = self.author(loop, loops)
            self.done = loop

            if session.status() == "COMPLETE" and session.check and session.check.passed:
                self.items, self.blocker = [], ""
                self.stop_reason = "complete"
                return

            resolved = self.review(loop, session)
            self.score(session, resolved or 0)
            self.persist(loops)

            if self.stalled():  # a clean review is progress, not the end: only the author says COMPLETE
                self.stop_reason = "stalled"
                return

    # -- the two sessions of a loop

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
        if before:
            session.changed = before != after
        else:  # no git snapshot: trust the tool calls
            session.changed = bool(session.written or session.edited)

        if self.task.check:
            session.check = Check.run(self.task.check, self.workdir, self.task.timeout)
            self.say(f"  check `{session.check.command}`: {'PASS' if session.check.passed else 'FAIL'}")
        if session.violations:
            self.say("  protected files reverted: " + "; ".join(session.violations))
        self.sessions.append(session)
        return session

    def review(self, loop, session):
        """
        The number of review items resolved, or None if the reviewer wrote no review
        """
        self.say(f"\n> loop {loop} [review]")
        self.review_file.unlink(missing_ok=True)
        result = self.session(loop, "review", self.review_tools(), REVIEW_SYSTEM,
                              self.review_prompt(loop, session), max(6, self.iterations // 2))
        self.reviews.append(Session.of(loop, result))

        review = lib.read_toml(self.review_file)
        if not review:  # no review: the author's own next steps become the open items
            self.blocker = ""
            self.update_items(session.next_steps(), loop)
            return None
        self.review_file.replace(self.record / f"review_{loop:03d}.toml")
        return self.apply(review, loop)

    def session(self, loop, phase, tools, system, prompt, iterations):
        events = self.record / "events" / f"loop_{loop:03d}_{phase}.toml"
        agent = lib.Agent(self.model, tools=tools, max_iterations=iterations,
                          show_diagnostics=self.verbose, logging=lib.ToolLogToml(path=str(events)))
        timer = lib.Timer()
        result = agent.run(prompt, system=system, chat_history=self.task.chat)
        self.phases.append(lib.write_loop_phase_metadata(
            self.record / "metadata", run_id=self.id, loop_index=loop, phase=phase,
            model=self.model_name, task_file=str(self.task.path), workdir=str(self.workdir),
            stop_reason=result.stop_reason, final_text_present=bool(result.final_text),
            usage=result.usage, iterations=result.iterations, tool_results=result.tool_results,
            rejected_calls=result.rejected_calls, duration_s=timer.ms / 1000))
        return result

    def protected(self):
        return set(self.guard.paths()) | {self.task.path}

    def author_tools(self):
        tools = lib.make_tools(self.workdir, bash_allow=self.task.bash, protected_paths=self.protected())
        return [GuardedBash(t, self.rules, self.guard) if t.name == "bash" else t for t in tools]

    def review_tools(self):
        tools = lib.make_tools(self.workdir, protected_paths=self.protected())
        tools = [t for t in tools if t.name in ("read", "glob", "write")]
        bash = lib.BashTool(cwd=self.workdir, bounded=True, allowed_commands=REVIEW_BASH,
                            protected_paths=self.protected())
        return tools + [bash]

    # -- what the review changes: open items and rules

    def apply(self, review, loop):
        """
        Take a review's blocker, retired and new rules, and pending items; the number resolved
        """
        self.blocker = str(review.get("blocker") or "").strip()

        retire = review.get("retire") if isinstance(review.get("retire"), list) else []
        retire = {str(rule_id).strip() for rule_id in retire}
        self.rules[:] = [rule for rule in self.rules if rule.id not in retire]

        new, self.problems = self.parse_rules(review.get("rule"), source=f"review:{loop}")
        self.rules += new
        self.history += self.problems
        del self.rules[:max(0, len(self.rules) - MAX_RULES)]

        # a rule's protect lasts while the rule does; the task's protections last the whole run
        self.guard.patterns = self.guard.base + [rule.protect for rule in self.rules if rule.protect]
        return self.update_items(review.get("pending"), loop)

    def update_items(self, entries, loop):
        """
        The new open items (an entry reusing an open item's id keeps it open); the number of open
        items not restated, i.e. resolved
        """
        still_open = {item.id: item for item in self.items}
        items = []
        for entry in entries if isinstance(entries, list) else []:
            if isinstance(entry, str):
                entry = {"item": entry}
            if not isinstance(entry, dict):
                continue
            text = str(entry.get("item") or "").strip()
            if not text:
                continue
            prior = still_open.pop(str(entry.get("id") or "").strip(), None)
            if prior:
                items.append(Item(prior.id, text, prior.opened))
            else:
                items.append(Item(f"P{self.next_item}", text, loop))
                self.next_item += 1
        self.items = items[:MAX_ITEMS]
        return len(still_open)

    def parse_rules(self, entries, source):
        """
        (new rules, problems): the review's [[rule]] entries, with unsafe deny_bash/protect dropped
        """
        rules, problems = [], []
        known = {rule.text for rule in self.rules}
        number = max((int(rule.id[1:]) for rule in self.rules if rule.id[1:].isdigit()), default=0)
        for entry in entries if isinstance(entries, list) else []:
            if isinstance(entry, str):
                entry = {"text": entry}
            if not isinstance(entry, dict):
                continue
            text = str(entry.get("text") or "").strip()
            if not text or text in known:
                continue

            deny = str(entry.get("deny_bash") or "").strip()
            problem = bad_regex(deny)
            if problem:
                problems.append(problem)
                deny = ""

            protect = str(entry.get("protect") or "").strip()
            writable = self.locks_writable(protect) if protect else ""
            if writable:
                problems.append(f"rule protect {protect!r} targets author-writable {writable!r}; ignored")
                protect = ""

            number += 1
            rules.append(Rule(f"R{number}", text, deny, protect, source))
        return rules, problems

    def locks_writable(self, pattern):
        """
        The author-writable file a protect pattern would lock, or ""
        """
        pattern = os.path.normpath(pattern)
        hits = {pattern}
        if any(c in pattern for c in GLOB):
            hits |= {self.rel(p) for p in self.workdir.glob(pattern)}
        for writable in map(os.path.normpath, self.task.writable):
            if fnmatch.fnmatch(writable, pattern) or any(fnmatch.fnmatch(hit, writable) for hit in hits):
                return writable
        return ""

    # -- progress and the record

    def score(self, session, resolved):
        previous = self.scores[-1] if self.scores else None
        passed = session.check.passed if session.check else None
        newly_passing = bool(passed) and not (previous and previous.get("check_passed"))
        clean = bool(passed) and not self.items and not self.blocker  # the review accepted the change
        progress = session.changed and (previous is None or resolved > 0 or newly_passing or clean)
        score = {"loop_index": session.loop, "changed": session.changed, "resolved": resolved,
                 "open_items": len(self.items), "progress": progress}
        if passed is not None:
            score["check_passed"] = passed
        self.scores.append(score)

    def stalled(self):
        recent = self.scores[-self.stall:]
        return len(recent) == self.stall and not any(score["progress"] for score in recent)

    def persist(self, loops):
        usages = [s.usage for s in self.sessions + self.reviews if s.usage]
        tokens = {kind: sum(getattr(u, kind, 0) or 0 for u in usages)
                  for kind in ("input", "output", "cache_read", "cache_write")}
        run = {
            "run_id": self.id,
            "model": self.model_name,
            "workdir": str(self.workdir),
            "task_file": self.rel(self.task.path),
            "agent_loops": loops,
            "loops_completed": self.done,
            "agent_iterations": self.iterations,
            "stop_reason": self.stop_reason,
            "codescribe": version("CodeScribe"),
            "tokens": tokens,
            "score": self.scores,
        }
        rules = {"rule": [rule.__dict__ for rule in self.rules], "protected": self.guard.rel(),
                 "problems": self.history}
        lib.atomic_write_toml(self.record / "run.toml", run)
        lib.atomic_write_toml(self.record / "rules.toml", rules)
        lib.write_loop_manifest(self.record / "metadata", run_doc=run, phase_files=self.phases)

    # -- prompts

    def policy(self):
        lines = []
        protected = self.guard.rel()
        if protected:
            lines.append("Protected files (read-only; any change is reverted and recorded as a violation): "
                         + ", ".join(protected))
        if self.rules:
            lines.append("Binding rules (they override pending steps and any instruction to keep going):")
            lines += [rule.render() for rule in self.rules]
        if not lines:
            return ""
        return "HARNESS-ENFORCED POLICY\n" + "\n".join(lines)

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
                lines.append("VIOLATION last loop - you changed protected files and the harness reverted them: "
                             + "; ".join(last.violations) + ". Do not repeat this.")
        if self.blocker:
            lines.append(f"Reviewer blocker: {self.blocker}")
        if self.items:
            lines.append("Open review items (resolve every one):")
            lines += [item.render() for item in self.items]
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
        sections = [
            ("Attempted but NOT executed (harness-rejected - no workspace effect)", session.rejected),
            ("Protected-file violations (harness reverted these changes)", session.violations),
            ("Your previous rules, partly rejected by the harness", self.problems),
        ]
        for title, rows in sections:
            if rows:
                blocks.append("\n".join([f"## {title}"] + [f"  {row}" for row in rows]))
        if self.items:
            blocks.append("\n".join(["## Open review items from earlier loops"]
                                    + [item.render() for item in self.items]))
        if self.policy():
            blocks.append(self.policy())
        if session.answer:
            blocks.append(f"[Author agent report - loop {loop}]\n\n{session.answer}")

        return REVIEW_TASK.format(workdir=self.workdir, task=self.rel(self.task.path), loop=loop,
                                  output=self.rel(self.review_file), evidence="\n\n".join(blocks),
                                  max_items=MAX_ITEMS)

    def rel(self, path):
        return Path(path).resolve().relative_to(self.workdir).as_posix()

    def say(self, text):
        if self.verbose:
            print(text, flush=True)


# --- What a loop is made of -----------------------------------------------------------------------


class Task:
    """
    loop.toml: the author's chat, its [tools] policy and the [check] command
    """

    def __init__(self, path):
        self.path = Path(path).resolve()
        data = toml.loads(self.path.read_text())
        tools = data.get("tools", {})
        check = data.get("check", {})
        self.bash = set(tools.get("bash", []))  # commands the author may run
        self.protect = list(tools.get("protect", []))  # files it may not change
        self.writable = list(tools.get("writable", []))  # files no rule may lock
        self.check = check.get("command", "")
        self.timeout = int(check.get("timeout", 600))
        self.chat = lib.load_chat_template(self.path)


@dataclass
class Check:
    """
    The harness check after an author session: its exit code is ground truth
    """

    command: str
    passed: bool
    code: int
    tail: str

    @classmethod
    def run(cls, command, cwd, timeout):
        try:
            process = subprocess.run(shlex.split(command), cwd=cwd, capture_output=True, text=True,
                                     errors="replace", timeout=timeout)
        except subprocess.TimeoutExpired:
            return cls(command, False, -1, f"timed out after {timeout}s")
        except (OSError, ValueError) as error:
            return cls(command, False, -1, str(error))
        output = (process.stdout + process.stderr).strip()
        return cls(command, process.returncode == 0, process.returncode, output[-CHECK_TAIL:])

    def render(self, tail=False):
        verdict = "PASSED" if self.passed else f"FAILED (exit {self.code})"
        text = f"Harness check `{self.command}`: {verdict}"
        if self.tail and (tail or not self.passed):
            text += f"\n```text\n{self.tail}\n```"
        return text


@dataclass
class Session:
    """
    What one agent session did, from its RunResult and the workspace (no LLM involved)
    """

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
    check: Check = None
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
                first_line = output.splitlines()[0] if output else ""
                session.commands.append(f"{target}  ->  {first_line[:60]}")
        session.rejected = [f"{c.name}({describe(c.name, c.args)}): {c.reason}" for c in result.rejected_calls]
        return session

    def status(self):
        """
        COMPLETE or INCOMPLETE from the author's "STATUS:" line, else None
        """
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
        """
        The bullets under the author's "NEXT STEPS" line (at most 5)
        """
        steps, inside = [], False
        for line in self.answer.splitlines():
            line = line.strip()
            if line.upper().startswith("NEXT STEPS"):
                inside = True
            elif inside and line.startswith("#"):
                break
            elif inside:
                bullet = re.match(r"^(?:[-*]|\d+[.)])\s+(.*)", line)
                if bullet:
                    steps.append(bullet.group(1).strip())
        return steps[:5]


@dataclass
class Rule:
    """
    A binding rule from the reviewer; deny_bash and protect are enforced by the harness
    """

    id: str
    text: str
    deny_bash: str = ""
    protect: str = ""
    source: str = ""

    def render(self):
        deny = f" [bash matching /{self.deny_bash}/ is refused]" if self.deny_bash else ""
        return f"- {self.id} ({self.source}): {self.text}{deny}"


@dataclass
class Item:
    """
    An open review item
    """

    id: str
    text: str
    opened: int

    def render(self):
        return f"  - [{self.id}, open since loop {self.opened}] {self.text}"


class Guard:
    """
    Snapshots protected files and reverts any change to them (tamper repair, not a sandbox)
    """

    def __init__(self, root, patterns):
        self.root = root
        self.base = list(patterns)  # the task's: the whole run
        self.patterns = list(patterns)  # the task's and the active rules'
        self.saved = {}  # path -> bytes, or None if absent
        self.violations = []

    def paths(self):
        found = []
        for pattern in self.patterns:
            if any(c in pattern for c in GLOB):
                candidates = self.root.glob(pattern)
            else:
                candidates = [self.root / pattern]
            for path in candidates:
                try:
                    path = within(path, self.root)
                except ValueError:
                    continue
                if path.is_dir():
                    continue
                if path not in found:
                    found.append(path)
        return found

    def rel(self):
        return [path.relative_to(self.root).as_posix() for path in self.paths()]

    def snapshot(self):
        self.saved = {path: read_bytes(path) for path in self.paths()}
        self.violations = []

    def restore(self):
        """
        Undo every change to a snapshotted file; what was reverted
        """
        reverted = []
        for path, before in self.saved.items():
            after = read_bytes(path)
            if after == before:
                continue
            name = path.relative_to(self.root).as_posix()
            try:
                if before is None:
                    path.unlink()
                    reverted.append(f"{name} (created; removed)")
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(before)
                    change = "deleted" if after is None else "modified"
                    reverted.append(f"{name} ({change}; restored)")
            except OSError as error:
                reverted.append(f"{name} (changed; restore FAILED: {error})")
        self.violations += reverted
        return reverted


class GuardedBash(lib.AgentTool):
    """
    The author's bash: refuses commands a rule denies, reverts protected files after each call
    """

    def __init__(self, inner, rules, guard):
        super().__init__(name=inner.name, description=inner.description,
                         parameters=inner.parameters, enabled=inner.enabled)
        self.inner, self.rules, self.guard = inner, rules, guard

    def run(self, args):
        command = str(args.get("command") or "")
        for rule in self.rules:
            if rule.deny_bash and re.search(rule.deny_bash, command):
                return f"Error: command refused by rule {rule.id}: {rule.text}"
        output = self.inner.run(args)
        reverted = self.guard.restore()
        if not reverted:
            return output
        return ("Error: this command changed protected file(s); the harness reverted them and "
                "recorded a violation: " + "; ".join(reverted) + "\n\n" + output)


class Workspace:
    """
    Git snapshots of the workdir (untracked files included) on a throwaway index
    """

    def __init__(self, root):
        self.root = root

    def git(self, *args, env=None):
        return subprocess.run(["git", *args], cwd=self.root, env=env, capture_output=True,
                              text=True, errors="replace", check=True).stdout

    def tree(self):
        """
        The id of a git tree of the workdir as it is now, or "" without git
        """
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


# --- Small helpers --------------------------------------------------------------------------------


def shims(bin, folder):
    """
    On Windows, where the author's bash runs commands through cmd.exe: a <tool>.cmd in folder for
    each extensionless stub in bin, so `oracle` resolves; the folder to put first on PATH, else None
    """
    if os.name != "nt":
        return None
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for stub in Path(bin).iterdir():
        if stub.is_file() and not stub.suffix:
            (folder / f"{stub.name}.cmd").write_bytes(f'@python "{stub.resolve()}" %*\r\n'.encode())
    return folder


def within(path, root):
    """
    path, resolved; ValueError if it is outside root
    """
    path = Path(path).resolve()
    path.relative_to(Path(root).resolve())
    return path


def read_bytes(path):
    try:
        return path.read_bytes() if path.is_file() else None
    except OSError:
        return None


def describe(tool, args):
    """
    A short label for a tool call: the command of a bash call, the path of a file call
    """
    args = args if isinstance(args, dict) else {}
    if tool == "bash":
        return (args.get("command") or "").replace("\n", " ").strip()[:80]
    if tool in ("read", "write", "edit"):
        return str(args.get("path", ""))
    return ""


def bad_regex(pattern):
    """
    Why a deny_bash pattern cannot be used, or ""
    """
    if not pattern:
        return ""
    try:
        if re.search(pattern, ""):
            return f"deny_bash {pattern!r} matches every command; ignored"
    except re.error as error:
        return f"deny_bash {pattern!r} is not a valid regex ({error}); ignored"
    return ""


def unique(values):
    return list(dict.fromkeys(values))


# --- Prompts --------------------------------------------------------------------------------------


AUTHOR_SYSTEM = """You are an autonomous coding agent specializing in test-driven development and repair.

Core rules:
- NEVER fabricate command results, test output, or file contents - always call a tool.
- Determine project state by reading files and running commands; never assume or infer.
- Only access files and paths within the working directory, with relative paths in bash.

Efficiency rules:
- Batch all independent reads and globs into the first turn.
- Once you know the changes needed, implement them without further exploration.
- Do not re-read files you have already read unless they changed.
- Run the closest check after each meaningful change.
- When the checks pass and no items remain, stop - do not invent further work.

Tools: glob to discover, read for content, bash to run commands, edit for targeted changes,
write only for new files or full rewrites.
"""

REVIEW_SYSTEM = """You are a code reviewer verifying another agent's work against a task specification.

- Judge from the harness evidence (diff, check output) and the files, never from the author's claims.
- NEVER fabricate file contents or results - read the file when the diff is not enough.
- Report only concrete defects or missing work between the code and the specification.
- Be decisive: when the specification is met, say so and raise nothing.
- Only access files within the working directory.
"""

AUTHOR_TASK = """{context}

Working directory: {workdir}
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
- `STATUS: COMPLETE` if everything is implemented and all checks pass, else `STATUS: INCOMPLETE`.
- The PLAN you followed, naming the review item ids you resolved.
- The exact output of the checks you ran.
- Only if INCOMPLETE: the line `NEXT STEPS:` and 3-5 concrete bullets for the next loop.
"""

REVIEW_TASK = """Working directory: {workdir}
Task file: {task} (read-only; its specification is the conversation above)
Review output: {output} (write here)

PHASE: REVIEW

{evidence}

Your job:
1. Judge the work against the specification using the diff, the harness check and the files.
   Claims relying on an 'Attempted but NOT executed' call did not happen.
2. Write your assessment to the review output file as TOML:

   ```toml
   loop = {loop}
   summary = "One paragraph describing what actually happened."
   blocker = "Main current blocker, or empty string if none."
   retire = []  # optional ids of earlier rules that no longer apply

   [[pending]]
   id = "P1"    # reuse an open item's id to keep it open; omit for a new item
   item = "Concrete defect or missing work"

   # Optional: binding rules for the author, enforced from the next loop on.
   [[rule]]
   text = "What the author must or must not do, and why"
   deny_bash = ""   # optional regex; matching author bash commands are refused
   protect = ""     # optional path the author may NOT change at all
   ```

   Open items you do not restate are treated as resolved.
3. Add a [[rule]] only for a harmful or repeated deviation. Prefer deny_bash/protect: the harness
   enforces those, not plain text. Never protect a file the task requires the author to change.
   If a rule blocked required work, retire it.

Rules:
- A failing check, a protected-file violation or a binding-rule breach is a blocker.
- If the check passes (or none is configured) and the specification is met: blocker = "" and no pending items.
- Pending items are concrete defects or missing work, never 'continue working', and never an
  action a stop condition or binding rule forbids. At most {max_items}.

After writing the review output file, reply with <final_answer> as plain text; do not call more tools.
"""
