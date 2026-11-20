"""Question 30: Rich's handling of a closed pipe (14 F10, 02 X1 rule 8), as real processes.

Run with the Rich version under test installed, for example
    uv run --no-project --with rich==13.9.4 python q30/rich_pipe_probe.py
Typer cases run only when typer is importable (add --with typer==0.29.1).
POSIX only for the `| head -1` cases (they use /bin/sh); the closed-before-start cases run everywhere.
Exits 0 whatever the outcome.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap

OS = {"linux": "linux", "darwin": "macos", "win32": "windows"}.get(sys.platform, sys.platform)
try:
    import rich

    from importlib.metadata import version

    RICH = version("rich")
except Exception:  # noqa: BLE001
    RICH = "?"
try:
    from importlib.metadata import version as _v

    TYPER = _v("typer")
except Exception:  # noqa: BLE001
    TYPER = None

PRELUDE = textwrap.dedent(
    """
    import os, sys
    def null1():
        try:
            a, b = os.fstat(1), os.stat(os.devnull)
            return (a.st_dev, a.st_ino) == (b.st_dev, b.st_ino) or (hasattr(a, 'st_rdev') and a.st_rdev == b.st_rdev and a.st_rdev != 0)
        except OSError:
            return None
    def note(msg):
        try:
            with open(os.environ['Q30_NOTE'], 'a') as f:
                f.write(msg + '\\n')
        except OSError:
            pass
    """
)

CHILD_PLAIN = PRELUDE + textwrap.dedent(
    """
    from rich.console import Console
    c = Console(stderr=(sys.argv[1] == 'stderr'))
    try:
        for i in range(int(sys.argv[2])):
            c.print(f'line {i}')
    except SystemExit as e:
        note(f'SystemExit({e.code}) fd1-null={null1()}')
        raise
    except BaseException as e:
        note(f'{e.__class__.__name__} fd1-null={null1()}')
        raise
    note(f'no-exception fd1-null={null1()}')
    """
)

CHILD_SUBCLASS = PRELUDE + textwrap.dedent(
    """
    from rich.console import Console
    class C(Console):
        def on_broken_pipe(self):
            raise BrokenPipeError
    c = C(stderr=(sys.argv[1] == 'stderr'))
    try:
        for i in range(int(sys.argv[2])):
            c.print(f'line {i}')
    except BrokenPipeError:
        note(f'BrokenPipeError-reached-caller fd1-null={null1()}')
        devnull = os.open(os.devnull, os.O_WRONLY); os.dup2(devnull, 1); os.dup2(devnull, 2)
        sys.exit(141)
    note('no-exception')
    """
)

CHILD_TYPER = PRELUDE + textwrap.dedent(
    """
    import typer
    app = typer.Typer(add_completion=False)
    @app.command()
    def hello(name: str = typer.Argument('x', help='a name ' * 30)):
        '''Say hello. ''' + 'More words. ' * 40
    @app.command()
    def bye(): pass
    try:
        app(prog_name='probe')
    except SystemExit as e:
        note(f'SystemExit({e.code}) fd1-null={null1()}')
        raise
    except BaseException as e:
        note(f'{e.__class__.__name__}: {e} fd1-null={null1()}')
        raise
    """
)


def run_closed(code: str, args: list[str], stream: str) -> tuple[int, str]:
    """Start the child with `stream` on a pipe whose reader was closed before the child started."""
    with tempfile.TemporaryDirectory() as d:
        note = os.path.join(d, "note")
        r, w = os.pipe()
        os.close(r)
        kw = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if stream in ("stdout", "both"):
            kw["stdout"] = w
        if stream in ("stderr", "both"):
            kw["stderr"] = w
        if stream == "stderr-only-stdout-open":
            kw["stderr"] = w
            kw["stdout"] = subprocess.PIPE
        p = subprocess.Popen([sys.executable, "-c", code, *args], env={**os.environ, "Q30_NOTE": note}, **kw)
        os.close(w)
        try:
            if p.stdout:
                p.stdout.read()
            rc = p.wait(30)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
            rc = -999
        n = open(note).read().strip() if os.path.exists(note) else "(no note)"
        return rc, n


def run_head(code: str, args: list[str], redirect: str = "") -> tuple[int, str]:
    """`python -c code args | head -1` through /bin/sh; returns the child's own exit code."""
    with tempfile.TemporaryDirectory() as d:
        note = os.path.join(d, "note")
        script = os.path.join(d, "child.py")
        with open(script, "w") as f:
            f.write(code)
        q = " ".join(f"'{a}'" for a in args)
        # The child's own exit status: run it in a subshell that records it.
        cmd = f"( '{sys.executable}' '{script}' {q} {redirect}; echo $? > '{d}/rc' ) | head -1 > /dev/null"
        subprocess.run(["/bin/sh", "-c", cmd], env={**os.environ, "Q30_NOTE": note}, timeout=60,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        rc = int(open(f"{d}/rc").read().strip()) if os.path.exists(f"{d}/rc") else -999
        n = open(note).read().strip() if os.path.exists(note) else "(no note)"
        return rc, n


def res(name: str, outcome: str, detail: str) -> None:
    t = f", typer {TYPER}" if TYPER and name.startswith("typer") else ""
    print(f"RESULT q30 rich-{name} {OS} : {outcome} (rich {RICH}{t}, Python {sys.version.split()[0]}) - {detail}", flush=True)


def main() -> None:
    expect_default = "SystemExit(1) fd1-null=True"
    rc, n = run_closed(CHILD_PLAIN, ["stdout", "3"], "stdout")
    res("plain-closed-stdout", "PASS" if (rc, n) == (1, expect_default) else "DIFFERENT",
        f"3 lines into a pipe closed before start: exit {rc}; {n}")
    rc, n = run_closed(CHILD_PLAIN, ["stderr", "3"], "stderr-only-stdout-open")
    res("plain-closed-stderr", "INFO", f"stderr console, stderr on a closed pipe, stdout open: exit {rc}; {n}")
    rc, n = run_closed(CHILD_SUBCLASS, ["stdout", "3"], "stdout")
    res("subclass-closed-stdout", "PASS" if rc == 141 and n.startswith("BrokenPipeError-reached-caller") else "DIFFERENT",
        f"on_broken_pipe raising BrokenPipeError: exit {rc}; {n}")
    rc, n = run_closed(CHILD_SUBCLASS, ["stderr", "3"], "stderr-only-stdout-open")
    res("subclass-closed-stderr", "PASS" if rc == 141 and n.startswith("BrokenPipeError-reached-caller") else "DIFFERENT",
        f"stderr console subclass, stderr closed: exit {rc}; {n}")
    if sys.platform != "win32":
        rc, n = run_head(CHILD_PLAIN, ["stdout", "200000"])
        res("plain-head", "PASS" if (rc, n) == (1, expect_default) else "DIFFERENT",
            f"200000 lines | head -1: exit {rc}; {n}")
        rc, n = run_head(CHILD_SUBCLASS, ["stdout", "200000"])
        res("subclass-head", "PASS" if rc == 141 else "DIFFERENT", f"subclass, 200000 lines | head -1: exit {rc}; {n}")
    if TYPER:
        rc, n = run_closed(CHILD_TYPER, ["--help"], "stdout")
        res("typer-help-closed", "PASS" if (rc, n) == (1, expect_default) else "DIFFERENT",
            f"--help with stdout closed before start: exit {rc}; {n}")
        rc, n = run_closed(CHILD_TYPER, ["--nosuch"], "stderr-only-stdout-open")
        res("typer-usage-closed-stderr", "INFO", f"unknown option, stderr closed: exit {rc}; {n}")
        if sys.platform != "win32":
            rc, n = run_head(CHILD_TYPER, ["--help"])
            res("typer-help-head", "INFO", f"--help | head -1 (racy: help may be written before head exits): exit {rc}; {n}")


if __name__ == "__main__":
    main()
    sys.exit(0)
