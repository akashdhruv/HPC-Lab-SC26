"""The lab's autonomous loop: author -> check -> review, on CodeScribe's library primitives.

A Task is a loop.toml (chat, [tools] policy, [check]); a Loop is one run of it, recorded in
<instance>/runs/<run_id>/. The harness, not the agents, enforces the policy and decides the stop:

  - protected files: [tools].protect + loop.toml; write/edit refuse them, and any change made
    through bash is reverted after every call and recorded as a violation;
  - rules: added/retired by the reviewer; `deny_bash` refuses author commands, `protect` locks a
    file while the rule is active ([tools].writable files can never be locked);
  - check: [check].command after every author session; its exit code is ground truth;
  - stop: author COMPLETE + check passes, or a clean review + check passes; stalled after
    `stall` loops without progress; else after the loop budget.

    Loop(instance, workdir, "oaic-<model>").run(loops)
"""

import fnmatch
import os
import re
import shlex
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from importlib.metadata import version

import toml
from codescribe import lib

MAX_ITEMS, MAX_RULES, CHECK_TAIL, MAX_DIFF = 8, 12, 4000, 20000
GLOB = "*?["


def within(path, root):
    path = Path(path).resolve()
    path.relative_to(Path(root).resolve())
    return path


class Task:
    """
    loop.toml: the author's chat, its [tools] policy and the [check] command
    """

    def __init__(self, path):
        self.path = Path(path).resolve()
        data = toml.loads(self.path.read_text())
        tools, check = data.get("tools", {}), data.get("check", {})
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
        try:
            p = subprocess.run(shlex.split(command), cwd=cwd, capture_output=True, text=True,
                               errors="replace", timeout=timeout)
        except subprocess.TimeoutExpired:
            return cls(command, False, -1, f"timed out after {timeout}s")
        except (OSError, ValueError) as e:
            return cls(command, False, -1, str(e))
        out = (p.stdout + p.stderr).strip()
        return cls(command, p.returncode == 0, p.returncode, out[-CHECK_TAIL:])

    def render(self, tail=False):
        verdict = "PASSED" if self.passed else f"FAILED (exit {self.code})"
        line = f"Harness check `{self.command}`: {verdict}"
        return line + (f"\n```text\n{self.tail}\n```" if self.tail and (tail or not self.passed) else "")


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
            d = self.git("diff", "--relative", before, after)
        except (OSError, subprocess.CalledProcessError):
            return ""
        return d if len(d) <= MAX_DIFF else d[:MAX_DIFF] + "\n[diff truncated; read the files]\n"


class Guard:
    """
    Snapshot protected files and revert any change to them (tamper repair, not a sandbox)
    """

    def __init__(self, root, patterns):
        self.root, self.base = root, list(patterns)
        self.patterns, self.saved, self.violations = list(patterns), {}, []

    def paths(self):
        found = []
        for pat in self.patterns:
            for p in (self.root.glob(pat) if any(c in pat for c in GLOB) else [self.root / pat]):
                try:
                    p = within(p, self.root)
                except ValueError:
                    continue
                if p not in found:
                    found.append(p)
        return found

    def rel(self):
        return [p.relative_to(self.root).as_posix() for p in self.paths()]

    @staticmethod
    def read(p):
        try:
            return p.read_bytes() if p.is_file() else None
        except OSError:
            return None

    def snapshot(self):
        self.saved, self.violations = {p: self.read(p) for p in self.paths()}, []

    def restore(self):
        reverted = []
        for p, before in self.saved.items():
            after = self.read(p)
            if after == before:
                continue
            rel = p.relative_to(self.root).as_posix()
            try:
                if before is None:
                    p.unlink()
                    reverted.append(f"{rel} (created; removed)")
                else:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_bytes(before)
                    reverted.append(f"{rel} ({'deleted' if after is None else 'modified'}; restored)")
            except OSError as e:
                reverted.append(f"{rel} (changed; restore FAILED: {e})")
        self.violations += reverted
        return reverted


@dataclass
class Rule:
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
    id: str
    text: str
    opened: int

    def render(self):
        return f"  - [{self.id}, open since loop {self.opened}] {self.text}"


class GuardedBash(lib.AgentTool):
    """
    The author's bash: refuses commands denied by a rule, reverts protected files after each call
    """

    def __init__(self, inner, rules, guard):
        super().__init__(name=inner.name, description=inner.description,
                         parameters=inner.parameters, enabled=inner.enabled)
        self.inner, self.rules, self.guard = inner, rules, guard

    def run(self, args):
        command = str(args.get("command") or "")
        for r in self.rules:
            if r.deny_bash and re.search(r.deny_bash, command):
                return f"Error: command refused by rule {r.id}: {r.text}"
        out = self.inner.run(args)
        reverted = self.guard.restore()
        if reverted:
            return ("Error: this command changed protected file(s); the harness reverted them and "
                    "recorded a violation: " + "; ".join(reverted) + "\n\n" + out)
        return out


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

    @staticmethod
    def label(name, args):
        args = args if isinstance(args, dict) else {}
        if name == "bash":
            return (args.get("command") or "").replace("\n", " ").strip()[:80]
        return str(args.get("path", "")) if name in ("read", "write", "edit") else ""

    @classmethod
    def of(cls, loop, result):
        s = cls(loop, answer=result.final_text or "", usage=result.usage)
        for t in result.tool_results:
            ap, preview = cls.label(t.name, t.args), (t.output_preview or "").strip()
            if not t.ok:
                s.errors.append(f"{t.name}({ap}): {preview[:80] or 'unknown error'}")
            elif t.name in ("write", "edit", "read"):
                getattr(s, {"write": "written", "edit": "edited", "read": "read"}[t.name]).append(ap)
            elif t.name == "bash":
                s.commands.append(f"{ap}  ->  {(preview.splitlines() or [''])[0][:60]}")
        s.rejected = [f"{c.name}({cls.label(c.name, c.args)}): {c.reason}" for c in result.rejected_calls]
        return s

    def status(self):
        for line in self.answer.splitlines():
            s = line.strip().upper()
            if s.startswith("STATUS:"):
                v = s[7:].strip()
                return "COMPLETE" if v.startswith("COMPLETE") else "INCOMPLETE" if v.startswith("INCOMPLETE") else None
        return None

    def next_steps(self):
        items, on = [], False
        for line in self.answer.splitlines():
            s = line.strip()
            if s.upper().startswith("NEXT STEPS"):
                on = True
            elif on and s.startswith("#"):
                break
            elif on and (m := re.match(r"^(?:[-*]|\d+[.)])\s+(.*)", s)):
                items.append(m.group(1).strip())
        return items[:5]


class Loop:
    """
    One run of a Task: author -> check -> review until the harness decides to stop
    """

    def __init__(self, instance, workdir, model, task="loop.toml", reasoning=False, iterations=30,
                 stall=2, verbose=True):
        self.instance, self.workdir = Path(instance).resolve(), Path(workdir).resolve()
        self.task = Task(within(self.instance / task, self.workdir))
        self.model_name, self.model = model, lib.set_neural_model(model, reasoning=reasoning)
        self.iterations, self.stall, self.verbose = iterations, stall, verbose
        self.id = lib.new_run_id()
        self.record = self.instance / "runs" / self.id
        self.review_file = self.record / "review.toml"
        self.workspace = Workspace(self.workdir)
        self.guard = Guard(self.workdir, [self.rel(self.task.path), *self.task.protect])
        self.sessions, self.reviews, self.items, self.rules, self.scores, self.phases = [], [], [], [], [], []
        self.blocker, self.problems, self.history, self.next_item, self.stop_reason = "", [], [], 1, "max_loops"
        (self.record / "metadata").mkdir(parents=True, exist_ok=True)

    def rel(self, p):
        return Path(p).resolve().relative_to(self.workdir).as_posix()

    def say(self, text):
        if self.verbose:
            print(text, flush=True)

    # -- sessions

    def protected(self):
        return set(self.guard.paths()) | {self.task.path}

    def author_tools(self):
        tools = lib.make_tools(self.workdir, bash_allow=self.task.bash, protected_paths=self.protected())
        return [GuardedBash(t, self.rules, self.guard) if t.name == "bash" else t for t in tools]

    def review_tools(self):
        allow = {"ls", "stat", "pwd", "find", "grep", "head", "tail", "rg", "cat", "diff"}
        tools = [t for t in lib.make_tools(self.workdir, protected_paths=self.protected())
                 if t.name in ("read", "glob", "write")]
        return tools + [lib.BashTool(cwd=self.workdir, bounded=True, allowed_commands=allow,
                                     protected_paths=self.protected())]

    def session(self, loop, phase, tools, system, prompt, iterations):
        agent = lib.Agent(self.model, tools=tools, max_iterations=iterations, show_diagnostics=self.verbose,
                          logging=lib.ToolLogToml(path=str(self.record / "events" / f"loop_{loop:03d}_{phase}.toml")))
        timer = lib.Timer()
        result = agent.run(prompt, system=system, chat_history=self.task.chat)
        self.phases.append(lib.write_loop_phase_metadata(
            self.record / "metadata", run_id=self.id, loop_index=loop, phase=phase, model=self.model_name,
            task_file=str(self.task.path), workdir=str(self.workdir), stop_reason=result.stop_reason,
            final_text_present=bool(result.final_text), usage=result.usage, iterations=result.iterations,
            tool_results=result.tool_results, rejected_calls=result.rejected_calls, duration_s=timer.ms / 1000))
        return result

    def author(self, loop, loops):
        self.say(f"\n> loop {loop} [author]")
        self.guard.snapshot()
        before = self.workspace.tree()
        result = self.session(loop, "author", self.author_tools(), AUTHOR_SYSTEM,
                              self.author_prompt(loop, loops), self.iterations)
        self.guard.restore()
        after = self.workspace.tree()
        s = Session.of(loop, result)
        s.violations, s.diff = list(self.guard.violations), self.workspace.diff(before, after)
        s.changed = before != after if before else bool(s.written or s.edited)
        if self.task.check:
            s.check = Check.run(self.task.check, self.workdir, self.task.timeout)
            self.say(f"  check `{s.check.command}`: {'PASS' if s.check.passed else 'FAIL'}")
        if s.violations:
            self.say("  protected files reverted: " + "; ".join(s.violations))
        self.sessions.append(s)
        return s

    def review(self, loop, s):
        self.say(f"\n> loop {loop} [review]")
        self.review_file.unlink(missing_ok=True)
        result = self.session(loop, "review", self.review_tools(), REVIEW_SYSTEM,
                              self.review_prompt(loop, s), max(6, self.iterations // 2))
        self.reviews.append(Session.of(loop, result))
        data = lib.read_toml(self.review_file)
        if data:
            self.review_file.replace(self.record / f"review_{loop:03d}.toml")
            return self.apply(data, loop)
        self.blocker = ""
        self.update_items(s.next_steps(), loop)
        return None

    # -- review state

    def update_items(self, raw, loop):
        open_ = {i.id: i for i in self.items}
        items = []
        for e in raw if isinstance(raw, list) else []:
            e = {"item": e} if isinstance(e, str) else e
            text = str(e.get("item") or "").strip() if isinstance(e, dict) else ""
            if not text:
                continue
            prior = open_.pop(str(e.get("id") or "").strip(), None)
            if prior:
                items.append(Item(prior.id, text, prior.opened))
            else:
                items.append(Item(f"P{self.next_item}", text, loop))
                self.next_item += 1
        self.items = items[:MAX_ITEMS]
        return len(open_)

    def parse_rules(self, raw, source):
        rules, problems = [], []
        n = max((int(r.id[1:]) for r in self.rules if r.id[1:].isdigit()), default=0)
        for e in raw if isinstance(raw, list) else []:
            e = {"text": e} if isinstance(e, str) else e
            text = str(e.get("text") or "").strip() if isinstance(e, dict) else ""
            if not text or text in {r.text for r in self.rules}:
                continue
            deny, protect = str(e.get("deny_bash") or "").strip(), str(e.get("protect") or "").strip()
            try:
                if deny and re.search(deny, ""):
                    problems.append(f"deny_bash {deny!r} matches every command; ignored")
                    deny = ""
            except re.error as err:
                problems.append(f"deny_bash {deny!r} is not a valid regex ({err}); ignored")
                deny = ""
            if protect and (hit := self.locks_writable(protect)):
                problems.append(f"rule protect {protect!r} targets author-writable {hit!r}; ignored")
                protect = ""
            n += 1
            rules.append(Rule(f"R{n}", text, deny, protect, source))
        return rules, problems

    def locks_writable(self, pattern):
        pattern = os.path.normpath(pattern)
        hits = {pattern} | ({self.rel(p) for p in self.workdir.glob(pattern)} if any(c in pattern for c in GLOB) else set())
        for w in map(os.path.normpath, self.task.writable):
            if fnmatch.fnmatch(w, pattern) or any(fnmatch.fnmatch(h, w) for h in hits):
                return w
        return ""

    def apply(self, data, loop):
        self.blocker = str(data.get("blocker") or "").strip()
        retire = data.get("retire") if isinstance(data.get("retire"), list) else []
        retire = {str(x).strip() for x in retire}
        self.rules[:] = [r for r in self.rules if r.id not in retire]
        new, self.problems = self.parse_rules(data.get("rule"), f"review:{loop}")
        self.rules += new
        self.history += self.problems
        del self.rules[: max(0, len(self.rules) - MAX_RULES)]
        # a rule's protect lasts while the rule does; the task's protections last the whole run
        self.guard.patterns = self.guard.base + [r.protect for r in self.rules if r.protect]
        return self.update_items(data.get("pending"), loop)

    # -- convergence

    def score(self, s, resolved):
        prev = self.scores[-1] if self.scores else None
        passed = s.check.passed if s.check else None
        fixed = bool(passed) and not (prev and prev.get("check_passed"))
        score = {"loop_index": s.loop, "changed": s.changed, "resolved": resolved,
                 "open_items": len(self.items),
                 "progress": s.changed and (prev is None or resolved > 0 or fixed)}
        if passed is not None:
            score["check_passed"] = passed
        self.scores.append(score)

    def stalled(self):
        recent = self.scores[-self.stall:]
        return len(recent) == self.stall and not any(s["progress"] for s in recent)

    def persist(self, loops, done):
        usage = [s.usage for s in self.sessions + self.reviews if s.usage]
        total = lambda k: sum(getattr(u, k, 0) or 0 for u in usage)
        doc = {"run_id": self.id, "model": self.model_name, "workdir": str(self.workdir),
               "task_file": self.rel(self.task.path), "agent_loops": loops, "loops_completed": done,
               "agent_iterations": self.iterations, "stop_reason": self.stop_reason,
               "codescribe": version("CodeScribe"),
               "tokens": {k: total(k) for k in ("input", "output", "cache_read", "cache_write")},
               "score": self.scores}
        lib.atomic_write_toml(self.record / "run.toml", doc)
        lib.atomic_write_toml(self.record / "rules.toml", {
            "rule": [r.__dict__ for r in self.rules], "protected": self.guard.rel(), "problems": self.history})
        lib.write_loop_manifest(self.record / "metadata", run_doc=doc, phase_files=self.phases)

    def run(self, loops=10):
        done = 0
        for loop in range(1, loops + 1):
            self.task.chat = lib.load_chat_template(self.task.path)
            s = self.author(loop, loops)
            done = loop
            if s.status() == "COMPLETE" and s.check and s.check.passed:
                self.items, self.blocker, self.stop_reason = [], "", "complete"
                break
            resolved = self.review(loop, s)
            self.score(s, resolved or 0)
            self.persist(loops, done)
            if resolved is not None and (not s.check or s.check.passed) and not self.items and not self.blocker:
                self.stop_reason = "complete"
                break
            if self.stalled():
                self.stop_reason = "stalled"
                break
        self.persist(loops, done)
        self.say(f"\n= {self.stop_reason} after {done}/{loops} loop(s)")
        return self

    # -- prompts

    def policy(self):
        lines, protected = [], self.guard.rel()
        if protected:
            lines.append("Protected files (read-only; any change is reverted and recorded as a violation): "
                         + ", ".join(protected))
        if self.rules:
            lines.append("Binding rules (they override pending steps and any instruction to keep going):")
            lines += [r.render() for r in self.rules]
        return "HARNESS-ENFORCED POLICY\n" + "\n".join(lines) if lines else ""

    def author_prompt(self, loop, loops):
        lines = [f"Loop {loop} of {loops}."]
        for label, attr in (("created", "written"), ("edited", "edited")):
            files = list(dict.fromkeys(f for s in self.sessions for f in getattr(s, attr)))
            if files:
                lines.append(f"Files {label} across all prior loops: " + ", ".join(files))
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
            lines += ["Open review items (resolve every one):"] + [i.render() for i in self.items]
        elif loop > 1:
            lines.append("No open review items - determine the next action from the task.")
        context = "\n".join(lines) + (f"\n\n{self.policy()}" if self.policy() else "")
        allowed = ", ".join(sorted(set(lib.BashTool._DEFAULT_ALLOWED) | self.task.bash))
        check = f"   The harness check is `{self.task.check}`.\n" if self.task.check else ""
        return AUTHOR_TASK.format(context=context, workdir=self.workdir, task=self.rel(self.task.path),
                                  allowed=allowed, check=check)

    def review_prompt(self, loop, s):
        facts = [f"## Verified actions from loop {loop} (harness-computed)"]
        for label, files in (("Files read", s.read), ("Files written", s.written), ("Files edited", s.edited)):
            if files:
                facts.append(f"{label}: " + ", ".join(files))
        for label, rows in (("Commands run", s.commands), ("Errors", s.errors)):
            if rows:
                facts += [f"{label}:"] + [f"  {r}" for r in rows]
        if len(facts) == 1:
            facts.append("  (no verified actions)")
        blocks = ["\n".join(facts)]
        if s.check:
            blocks.append("## " + s.check.render(tail=True))
        if s.diff:
            blocks.append(f"## Workspace diff from loop {loop}\n```diff\n{s.diff}```")
        elif not s.changed:
            blocks.append("## Workspace diff: the author changed nothing.")
        for title, rows in (("Attempted but NOT executed (harness-rejected - no workspace effect)", s.rejected),
                            ("Protected-file violations (harness reverted these changes)", s.violations),
                            ("Your previous rules, partly rejected by the harness", self.problems)):
            if rows:
                blocks.append("\n".join([f"## {title}"] + [f"  {r}" for r in rows]))
        if self.items:
            blocks.append("\n".join(["## Open review items from earlier loops"] + [i.render() for i in self.items]))
        if self.policy():
            blocks.append(self.policy())
        if s.answer:
            blocks.append(f"[Author agent report - loop {loop}]\n\n{s.answer}")
        return REVIEW_TASK.format(workdir=self.workdir, task=self.rel(self.task.path), loop=loop,
                                  output=self.rel(self.review_file), evidence="\n\n".join(blocks),
                                  max_items=MAX_ITEMS)


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
