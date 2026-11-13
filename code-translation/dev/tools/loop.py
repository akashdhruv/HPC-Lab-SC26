"""code-translation's autonomous loop: author -> check -> review, on CodeScribe's library primitives.

    This harness is a thin wrapper around codescribe.lib.prompt_loop (the canonical
    author -> check -> review loop): Loop(instance, workdir, "oaic-<model>").run(loops)

A Task is a loop.toml (the author's chat, a [tools] policy, a [check] command). A Loop is one run
of it. The harness enforces protected files and the check command; the agents decide everything else.
"""

import os
import platform
import signal
import sys
from pathlib import Path

from codescribe import lib


def shims(bin, folder):
    if os.name != "nt":
        return None
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for stub in Path(bin).iterdir():
        if stub.is_file() and not stub.suffix:
            (folder / f"{stub.name}.cmd").write_bytes(f'@python "{stub.resolve()}" %*\r\n'.encode())
    return folder


class Loop:
    """
    One run of a Task, delegated to codescribe.lib.prompt_loop.
    """

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

    def run(self, loops=10):
        try:
            result = lib.prompt_loop(
                task_file=self.task_path,
                model=self.model_name,
                agent_loops=loops,
                agent_iterations=self.iterations,
                verbose=self.verbose,
                workdir=self.workdir,
                reason=self.reasoning,
            )
        except KeyboardInterrupt:
            self.stop_reason = "stopped"
            return self
        self.done = loops
        if isinstance(result, str) and ":" in result:
            self.stop_reason = result.split(":", 1)[0].strip()
        elif isinstance(result, str) and result:
            self.stop_reason = result.strip()
        return self
