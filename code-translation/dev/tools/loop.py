"""code-translation's autonomous loop: author -> check -> review, on CodeScribe's Agent.

Stops at the end of a group or when the transformation is complete — never on a clean
review alone, which would quit mid-group.
"""

import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any

from codescribe import lib


def shims(bin, folder):
    """Windows .cmd shims (no-op on POSIX)."""
    if os.name != "nt":
        return None
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for stub in Path(bin).iterdir():
        if stub.is_file() and not stub.suffix:
            (folder / f"{stub.name}.cmd").write_bytes(
                f'@python "{stub.resolve()}" %*\r\n'.encode()
            )
    return folder


def expand(workdir, patterns):
    """The patterns' paths under workdir: globs expanded, resolved, confined to workdir"""
    paths = []
    for pat in patterns:
        cands = list(workdir.glob(pat)) if any(c in pat for c in "*?[") else [workdir / pat]
        for p in cands:
            try:
                p = p.resolve()
                p.relative_to(workdir.resolve())
            except (ValueError, OSError):
                continue
            if p not in paths:
                paths.append(p)
    return paths


class ProtectedFileGuard:
    def __init__(self, workdir: Path, patterns: list[str]):
        self.workdir = workdir
        self.patterns = list(patterns)
        self.saved: dict[Path, bytes | None] = {}
        self.violations: list[str] = []

    def _resolve(self) -> list[Path]:
        return [p for p in expand(self.workdir, self.patterns) if not p.is_dir()]

    def snapshot(self) -> None:
        self.saved = {p: (p.read_bytes() if p.is_file() else None) for p in self._resolve()}
        self.violations = []

    def restore(self) -> list[str]:
        reverted: list[str] = []
        for path, before in self.saved.items():
            after = path.read_bytes() if path.is_file() else None
            if after == before:
                continue
            rel = str(path.relative_to(self.workdir))
            try:
                if before is None:
                    path.unlink(missing_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(before)
                reverted.append(f"{rel} (restored)")
            except OSError as exc:
                reverted.append(f"{rel} (restore FAILED: {exc})")
        self.violations.extend(reverted)
        return reverted


class Loop:
    def __init__(self, instance, workdir, model, task="loop.toml", reasoning=False,
                 iterations=30, verbose=True):
        self.instance = Path(instance).resolve()
        self.workdir = Path(workdir).resolve()
        self.task_path = (self.instance / task).resolve()
        self.model_name = model
        self.reasoning = reasoning
        self.iterations = iterations
        self.verbose = verbose

        self.record = self.workdir / ".codescribe" / "loop"
        self.done = 0
        self.stop_reason = "max_loops"

        self.chat_history, self.meta = lib.load_chat_template(self.task_path, return_meta=True)
        tools_cfg = self.meta.get("tools") or {}
        self.bash_allow = set(tools_cfg.get("bash") or [])
        self.memory = tools_cfg.get("memory")
        self.check_cfg = self.meta.get("check")
        self.writable = list(tools_cfg.get("writable") or [])
        self.protect_patterns = [self.task_path.relative_to(self.workdir).as_posix()] + \
            list(tools_cfg.get("protect") or [])

        self.model = lib.set_neural_model(self.model_name, reasoning=self.reasoning)
        self.guard = ProtectedFileGuard(self.workdir, self.protect_patterns)

        self.loop_summaries: list[dict[str, Any]] = []
        self.items: list[str] = []
        self.blocker: str = ""
        self.author_next_steps: list[str] = []

    def _protected_paths(self) -> set:
        return {self.task_path.resolve(), *expand(self.workdir, self.protect_patterns)}

    def make_author_tools(self):
        return lib.make_tools(
            self.workdir,
            bash_allow=self.bash_allow,
            protected_paths=self._protected_paths(),
            memory=self.memory,
        )

    def make_review_tools(self):
        tools = lib.make_readonly_tools(
            self.workdir,
            bash_allow={"ls", "stat", "pwd", "find", "grep", "head", "tail",
                        "which", "env", "rg", "git"},
            protected_paths=self._protected_paths(),
            memory=self.memory,
        )
        tools.append(lib.WriteTool(root=self.workdir, protected_paths=self._protected_paths()))
        return tools

    def run_check(self):
        if not self.check_cfg:
            return None
        cmd = self.check_cfg["command"]
        timeout = self.check_cfg.get("timeout", 300)
        try:
            proc = subprocess.run(shlex.split(cmd), cwd=self.workdir,
                                  capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return False, f"timed out after {timeout}s"
        except (OSError, ValueError) as exc:
            return False, str(exc)
        out = (proc.stdout + proc.stderr).strip()
        return proc.returncode == 0, out[-4000:]

    def _vprint(self, msg):
        if self.verbose:
            print(msg, flush=True)

    def _system_prompt(self):
        return (
            "You are an autonomous coding agent specializing in test-driven development and repair.\n\n"
            "Core rules:\n"
            "- NEVER fabricate command results, test output, or file contents - always call a tool.\n"
            "- Determine project state by reading files and running commands; never assume.\n"
            "- Only access files within the working directory.\n"
            "- In bash, only use relative paths or paths under the working directory.\n"
        )

    def _review_system_prompt(self):
        return (
            "You are a code reviewer verifying another agent's work against a task specification.\n\n"
            "Core rules:\n"
            "- Judge from the harness evidence (diff, check output) and the files.\n"
            "- NEVER fabricate file contents or results.\n"
            "- Report only concrete defects or missing work.\n"
            "- Be decisive: when the spec is met, say so and raise nothing.\n"
        )

    def _author_task(self, loop_idx, loops):
        lines = [f"Loop {loop_idx} of {loops}."]
        if self.loop_summaries:
            last = self.loop_summaries[-1]
            if last.get("check") is not None:
                passed, tail = last["check"]
                lines.append(f"Harness check: {'PASSED' if passed else 'FAILED'}")
                if tail and not passed:
                    lines.append(f"```text\n{tail}\n```")
            if last.get("errors"):
                lines.append("Last loop errors: " + "; ".join(last["errors"][:5]))
            if last.get("violations"):
                lines.append("VIOLATION last loop (reverted): " + "; ".join(last["violations"]))
        if self.blocker:
            lines.append(f"Reviewer blocker: {self.blocker}")
        if self.items:
            lines.append("Open review items (resolve every one):")
            for it in self.items:
                lines.append(f"  - {it}")
        elif loop_idx > 1:
            lines.append("No open review items - determine the next action from the task.")
        context = "\n".join(lines)

        return (
            f"{context}\n\n"
            f"Working directory: {self.workdir}\n"
            f"Task file: {self.task_path.relative_to(self.workdir)} (read-only)\n\n"
            "PHASE: AUTHOR\n\n"
            "Goal: complete the task. Implement remaining items, verify, stop when done.\n"
            "The harness runs its own check after you finish; your report cannot override it.\n\n"
            "Protocol: read plan first, then spec. Write a short PLAN, execute autonomously,\n"
            "run checks after each change. Stop on hard blockers.\n\n"
            "Finish with <final_answer> including:\n"
            "- STATUS: COMPLETE if all done and checks pass, else STATUS: INCOMPLETE\n"
            "- The PLAN followed\n"
            "- Exact check output\n"
            "- If INCOMPLETE: NEXT STEPS: (bulleted, 3-5 items)\n"
        )

    def _review_task(self, loop_idx, author_answer, check_result):
        evidence = []
        if check_result is not None:
            passed, tail = check_result
            evidence.append(f"Harness check: {'PASSED' if passed else 'FAILED'}\n```text\n{tail}\n```")
        if author_answer:
            evidence.append(f"[Author report]\n\n{author_answer}")
        if self.items:
            evidence.append("Open review items from earlier loops:\n" + "\n".join(f"  - {i}" for i in self.items))
        evidence_txt = "\n\n".join(evidence)

        return (
            f"Working directory: {self.workdir}\n"
            f"Task file: {self.task_path.relative_to(self.workdir)} (read-only)\n\n"
            "PHASE: REVIEW\n\n"
            f"{evidence_txt}\n\n"
            "Your job: judge the work against the spec using the check output. "
            "Report concrete defects or missing work. If check passes and spec is met, "
            "say so and raise nothing.\n\n"
            "Finish with <final_answer> listing:\n"
            "- A one-paragraph summary of what happened\n"
            "- blocker: main blocker, or empty\n"
            "- pending: list of concrete open items (empty if none)\n"
        )

    def _parse_author(self, text):
        status = None
        for line in (text or "").splitlines():
            s = line.strip().upper()
            if s.startswith("STATUS:"):
                v = s[len("STATUS:"):].strip()
                if v.startswith("COMPLETE"):
                    status = "COMPLETE"
                elif v.startswith("INCOMPLETE"):
                    status = "INCOMPLETE"
        steps = []
        in_sec = False
        for line in (text or "").splitlines():
            st = line.strip()
            if st.upper().startswith("NEXT STEPS"):
                in_sec = True
                continue
            if in_sec:
                if not st:
                    continue
                if st.startswith("#"):
                    break
                if st.startswith("-") or st.startswith("*"):
                    steps.append(st.lstrip("-* ").strip())
                else:
                    m = re.match(r"\d+[.)] ", st)
                    if m:
                        steps.append(st[m.end():].strip())
        return status, steps[:5]

    def _parse_review(self, text):
        blocker = ""
        pending = []
        in_pending = False
        for line in (text or "").splitlines():
            st = line.strip()
            lowl = st.lower()
            if lowl.startswith("blocker:"):
                blocker = st[len("blocker:"):].strip().strip('"').strip()
                in_pending = False
                continue
            if lowl.startswith("pending"):
                in_pending = True
                continue
            if in_pending:
                if not st:
                    continue
                if st.startswith("#") or lowl.startswith("blocker") or lowl.startswith("next"):
                    in_pending = False
                    continue
                if st.startswith("-") or st.startswith("*"):
                    pending.append(st.lstrip("-* ").strip())
        return blocker, pending[:8]

    def _groups_done(self):
        """(leading groups fully verified, total groups) from the plan's '- Group k: ...'
        lines and the 'verified' lines of agent_log.md."""
        def lines(name):
            p = self.instance / name
            return p.read_text().splitlines() if p.is_file() else []

        groups = []
        for ln in lines("current_plan.md"):
            if ln.startswith("- Group"):
                units = [u.lower() for u in re.findall(r"\b([A-Za-z_]\w*)\.F90\b", ln)]
                if units:
                    groups.append(units)
        verified = set()
        for ln in lines("agent_log.md"):
            parts = [p.strip() for p in ln.lstrip("-").split("|")] if ln.startswith("-") else []
            if len(parts) >= 3 and parts[0] and parts[2].lower() == "verified":
                verified.add(parts[0].lower().removesuffix(".f90"))
        done = 0
        for units in groups:
            if not all(u in verified for u in units):
                break
            done += 1
        return done, len(groups)

    def _tally(self, tool_results):
        """(errors, files_written, files_edited, files_read, commands) over the author's tool results"""
        errors, files_written, files_edited, files_read, commands = [], [], [], [], []
        for tr in tool_results:
            args = tr.args if isinstance(tr.args, dict) else {}
            ap = ""
            if tr.name in ("read", "write", "edit"):
                ap = str(args.get("path", ""))
            elif tr.name == "bash":
                ap = (args.get("command") or "")[:80]
            if not tr.ok:
                errors.append(f"{tr.name}({ap}): {(tr.output_preview or '')[:80]}")
            elif tr.name == "write":
                files_written.append(ap)
            elif tr.name == "edit":
                files_edited.append(ap)
            elif tr.name == "read":
                files_read.append(ap)
            elif tr.name == "bash":
                first = (tr.output_preview or "").splitlines()[0][:60] if tr.output_preview else ""
                commands.append(f"{ap}  →  {first}")
        return errors, files_written, files_edited, files_read, commands

    def _stop_now(self, stop, loop_idx):
        self.stop_reason, self.done = stop, loop_idx
        self._vprint(f"■ {stop}, check passed (loop {loop_idx})")

    def run(self, loops=10):
        try:
            self.record.mkdir(parents=True, exist_ok=True)
            (self.record / "metadata").mkdir(parents=True, exist_ok=True)
            start_done, total = self._groups_done()

            for loop_idx in range(1, loops + 1):
                self._vprint(f"\n▶  loop {loop_idx} [author]")

                self.guard.snapshot()

                author_task = self._author_task(loop_idx, loops)
                author_agent = lib.Agent(
                    self.model,
                    tools=self.make_author_tools(),
                    max_iterations=self.iterations,
                    show_diagnostics=self.verbose,
                )
                author_result = author_agent.run(
                    author_task, system=self._system_prompt(), chat_history=self.chat_history
                )
                author_answer = author_result.final_text or ""

                reverted = self.guard.restore()
                if reverted and self.verbose:
                    print("  ⚠ protected files reverted: " + "; ".join(reverted))

                check_result = self.run_check()
                if self.verbose and check_result is not None:
                    passed, _ = check_result
                    print(f"  check: {'PASS' if passed else 'FAIL'}")

                errors, files_written, files_edited, files_read, commands = \
                    self._tally(author_result.tool_results)

                status, next_steps = self._parse_author(author_answer)
                self.loop_summaries.append({
                    "loop_index": loop_idx,
                    "files_written": files_written,
                    "files_edited": files_edited,
                    "files_read": files_read,
                    "commands": commands,
                    "errors": errors,
                    "violations": reverted,
                    "check": check_result,
                    "author_answer": author_answer,
                })
                self.author_next_steps = next_steps

                check_ok = check_result is None or check_result[0]
                # Stop only when a group completed during this run (or all did) and the
                # check passed; a clean review alone must not end the loop mid-group.
                stop = None
                if check_ok:
                    done, _ = self._groups_done()
                    if total and done == total:
                        stop = "complete"
                    elif done > start_done:
                        stop = f"group {done} complete"
                if status == "COMPLETE" and stop:
                    self.items, self.blocker = [], ""
                    self._stop_now(stop, loop_idx)
                    break

                self._vprint(f"\n▶  loop {loop_idx} [review]")
                review_task = self._review_task(loop_idx, author_answer, check_result)
                review_agent = lib.Agent(
                    self.model,
                    tools=self.make_review_tools(),
                    max_iterations=max(6, self.iterations // 2),
                    show_diagnostics=self.verbose,
                )
                review_result = review_agent.run(
                    review_task, system=self._review_system_prompt(), chat_history=self.chat_history
                )
                review_answer = review_result.final_text or ""

                blocker, pending = self._parse_review(review_answer)
                self.blocker = blocker
                self.items = pending

                if stop:
                    self._stop_now(stop, loop_idx)
                    break

            if self.done == 0:
                self.done = min(loops, len(self.loop_summaries))

            self._vprint(f"\n■ {self.stop_reason}: {self.done}/{loops} loop(s)")
        except KeyboardInterrupt:
            self.stop_reason = "stopped"
        return self
