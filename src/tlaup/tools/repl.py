"""Running the REPL (design 21 S3, decisions D5, D29 and D60).

The REPL is interactive: nothing is read or parsed, the child inherits tlaup's terminal and stays in tlaup's process
group, so a Ctrl-C at the terminal reaches the REPL itself and tlaup's handler does nothing with it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tlaup.java.launcher import run_passthrough, signals_held

if TYPE_CHECKING:
    from tlaup.java.launcher import JavaInvocation, ProcessOutcome


def run_repl(java_inv: JavaInvocation) -> ProcessOutcome:
    """Runs the REPL on tlaup's own streams. `leave_interrupt` and `forward_interrupt=False` go together: a SIGINT is
    the REPL's own, neither forwarded nor counted; SIGTERM and SIGHUP are forwarded as for any run."""
    with signals_held(leave_interrupt=True) as signals:
        return run_passthrough(java_inv, signals=signals, forward_interrupt=False)
