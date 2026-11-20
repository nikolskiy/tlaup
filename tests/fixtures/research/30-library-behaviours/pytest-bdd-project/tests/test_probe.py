import inspect

import pytest
import pytest_bdd
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features")

try:
    from importlib.metadata import version
    V = version("pytest-bdd")
except Exception:
    V = "?"
MAJOR = int(V.split(".")[0])


@pytest.fixture
def ctx():
    return {"runs": [], "files": {}}


if MAJOR >= 8:
    @given(parsers.parse('a file "{name}" containing:'))
    def a_file(ctx, name, docstring):
        ctx["files"][name] = docstring
else:
    @given(parsers.parse('a file "{name}" containing:\n{text}'))
    def a_file(ctx, name, text):
        ctx["files"][name] = text.strip('"\n ')


@given(parsers.parse('java replays "{case}" with exit code {code:d}'))
def java_replays(ctx, case, code):
    ctx["java"] = (case, code)


@when(parsers.parse('I run "{cmd}"'))
def i_run(ctx, cmd):
    ctx["runs"].append(cmd)


@then(parsers.parse('the runs were "{runs}"'))
def runs_were(ctx, runs):
    assert ctx["runs"] == runs.split(",")
    assert ctx["java"] == ("tlc/x", 12)


@then(parsers.parse('the file "{name}" holds {n:d} lines'))
def file_lines(ctx, name, n):
    text = ctx["files"][name]
    print("DOCSTRING:", repr(text))
    assert len(text.splitlines()) == n
