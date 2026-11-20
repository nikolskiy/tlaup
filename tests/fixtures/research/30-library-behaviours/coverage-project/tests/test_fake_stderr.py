import os, subprocess, sys
from pathlib import Path

SRC = str(Path(__file__).parents[1] / "src")

def run(env):
    fake = Path(__file__).parent / "fakes" / "java.py"
    return subprocess.run([sys.executable, str(fake)], capture_output=True, text=True, env=env).stderr

def test_fake_stderr_not_importable():
    e = run(dict(os.environ))
    print("FAKE STDERR (mypkg not importable):", repr(e[:300]))
    assert e == ""

def test_fake_stderr_importable():
    e = run({**os.environ, "PYTHONPATH": SRC})
    print("FAKE STDERR (mypkg importable):", repr(e[:300]))
    assert e == ""

def test_fake_stderr_importable_python_I():
    fake = Path(__file__).parent / "fakes" / "java.py"
    e = subprocess.run([sys.executable, "-I", str(fake)], capture_output=True, text=True, env={**os.environ, "PYTHONPATH": SRC}).stderr
    print("FAKE STDERR (-I):", repr(e[:300]))
    assert e == ""
