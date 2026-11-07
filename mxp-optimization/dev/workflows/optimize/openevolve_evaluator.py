"""evaluate(program_path) for OpenEvolve: scores a candidate with the run's evaluator.py.

run.py sets OE_EVALUATOR, OE_TIMEOUT and OE_PYTHON. Standard library only.
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

FAILED = -1e12


def evaluate(program_path):
    from openevolve.evaluation_result import EvaluationResult

    with tempfile.TemporaryDirectory() as work:
        shutil.copy(program_path, Path(work) / "initial_program.py")
        output = Path(work) / "result.json"
        command = [
            os.environ.get("OE_PYTHON", "python3"),
            os.environ["OE_EVALUATOR"],
            "--program-dir",
            work,
            "--output-file",
            str(output),
        ]
        try:
            done = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=int(os.environ.get("OE_TIMEOUT", "600")),
                check=False,
            )
            result = json.loads(output.read_text()) if output.is_file() else {}
            tail = (done.stdout + done.stderr)[-2000:]
        except subprocess.TimeoutExpired:
            result, tail = {}, "evaluator timed out"

    insights = result.get("insights") or [{"label": "EVALUATOR_ERROR", "text": tail}]
    scores = {item["metric"]: item["score"] for item in result.get("scores") or []}
    primary = next(iter(scores.values()), None)
    metrics = {
        name: float(value) for name, value in scores.items() if value is not None
    }
    metrics["combined_score"] = FAILED if primary is None else float(primary)
    feedback = "\n".join(f"{item['label']}: {item['text']}" for item in insights)
    return EvaluationResult(
        metrics=metrics, artifacts={"label": insights[0]["label"], "feedback": feedback}
    )
