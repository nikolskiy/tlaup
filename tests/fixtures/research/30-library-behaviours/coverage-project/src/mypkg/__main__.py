import os
import signal
import subprocess
import sys
import time


def normal():
    print("normal ran")


def on_sigint():
    try:
        print("ready", flush=True)
        time.sleep(30)
    except KeyboardInterrupt:
        sys.exit(130)


def on_sigterm():
    def handler(signum, frame):
        raise SystemExit(143)

    signal.signal(signal.SIGTERM, handler)
    print("ready", flush=True)
    time.sleep(30)


def default_sigterm():
    print("ready", flush=True)
    time.sleep(30)


def hard_exit():
    print("hard", flush=True)
    os._exit(3)


def calls_fake():
    here = os.path.dirname(__file__)
    fake = os.path.join(here, "..", "..", "tests", "fakes", "java.py")
    subprocess.run([sys.executable, fake], check=True)
    print("fake done")


def on_tty():
    print("tty" if os.isatty(1) else "notty", flush=True)


if __name__ == "__main__":
    {"normal": normal, "sigint": on_sigint, "sigterm": on_sigterm, "default_sigterm": default_sigterm,
     "hard": hard_exit, "fake": calls_fake, "tty": on_tty}[sys.argv[1]]()
