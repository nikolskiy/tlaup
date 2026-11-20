import os
import pty
import signal
import subprocess
import sys
import time
from pathlib import Path

SRC = str(Path(__file__).parents[1] / "src")
ENV = {**os.environ, "PYTHONPATH": SRC}


def start(mode):
    return subprocess.Popen([sys.executable, "-m", "mypkg", mode], stdout=subprocess.PIPE, text=True, env=ENV)


def test_normal():
    assert subprocess.run([sys.executable, "-m", "mypkg", "normal"], env=ENV).returncode == 0


def test_sigint():
    p = start("sigint")
    assert p.stdout.readline().strip() == "ready"
    p.send_signal(signal.SIGINT)
    assert p.wait(10) == 130


def test_sigterm_handled():
    p = start("sigterm")
    assert p.stdout.readline().strip() == "ready"
    p.send_signal(signal.SIGTERM)
    assert p.wait(10) == 143


def test_sigterm_default():
    p = start("default_sigterm")
    assert p.stdout.readline().strip() == "ready"
    p.send_signal(signal.SIGTERM)
    assert p.wait(10) == -signal.SIGTERM


def test_hard_exit():
    assert subprocess.run([sys.executable, "-m", "mypkg", "hard"], env=ENV).returncode == 3


def test_fake():
    assert subprocess.run([sys.executable, "-m", "mypkg", "fake"], env=ENV).returncode == 0


def test_tty():
    m, s = pty.openpty()
    p = subprocess.Popen([sys.executable, "-m", "mypkg", "tty"], stdin=s, stdout=s, stderr=s, env=ENV)
    os.close(s)
    out = b""
    while True:
        try:
            b = os.read(m, 1024)
        except OSError:
            break
        if not b:
            break
        out += b
    os.close(m)
    assert p.wait(10) == 0
    assert b"tty" in out
