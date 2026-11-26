"""A child Python process for the closed-pipe tests of ``test_run.py`` (package 37, D58).

The test starts it with its stdout on a pipe whose read end is already closed, which the test process's own stdout
under pytest's capture is not. It runs ``run_tlc`` (with a ``CollectingReporter``) or ``run_tlc_raw`` with the fake
``java`` the test scripted (``TLAUP_FAKE_JAVA`` is inherited) and prints the outcome's fields as JSON on stderr.

Its one argument is JSON: ``work`` (the working folder, where ``Spec.tla`` is), ``java`` (the fake's path), ``raw``
and ``keep``. Test code only: it adds no seam to the product.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # the repository root, for tests.* and tlaup

from tests.clock import FakeClock
from tests.unit.tlc.invocations import make_invocation
from tlaup.java.locate import JavaRuntime, JavaTool
from tlaup.paths import AppPaths
from tlaup.reporters.collecting import CollectingReporter
from tlaup.tlc.command import build_tlc_command
from tlaup.tlc.invocation import TlcRequest
from tlaup.tlc.run import run_tlc, run_tlc_raw


def main(argument: str) -> int:
    spec = json.loads(argument)
    work = Path(spec["work"])
    paths = AppPaths.from_env(os.environ)
    request = TlcRequest(spec="Spec.tla", raw=spec["raw"], keep=spec["keep"])
    java = JavaRuntime(JavaTool(Path(spec["java"]), "PATH"), "25.0.5", 25, ())
    inv = make_invocation(work, paths.runs, request=request, java=java)
    java_inv = build_tlc_command(inv)
    clock = FakeClock()
    if spec["raw"]:
        outcome = run_tlc_raw(inv, java_inv, paths=paths, now=clock.now, notice=lambda _line: None)
    else:
        outcome = run_tlc(inv, java_inv, CollectingReporter(), paths=paths, now=clock.now, notice=lambda _line: None)
    fields = {
        "exit_code": outcome.exit_code,
        "tool_exit_code": outcome.tool_exit_code,
        "stopped_by": outcome.stopped_by,
        "stopped_for_closed_pipe": outcome.stopped_for_closed_pipe,
        "run_folder_kept": None if outcome.run_folder_kept is None else str(outcome.run_folder_kept),
        "kept_reason": None if outcome.kept is None else outcome.kept.reason,
        "dropped_checkpoint": outcome.dropped_checkpoint,
        "status": None if outcome.result is None else outcome.result.status.value,
        "verdict": None if outcome.result is None else outcome.result.verdict.value,
    }
    sys.stderr.write(json.dumps(fields) + "\n")
    sys.stderr.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
