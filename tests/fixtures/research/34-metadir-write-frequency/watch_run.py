#!/usr/bin/env python3
"""Run TLC with a -metadir and log every write under that folder.

Every second the script stats every entry under the metadir (the folder
itself, TLC's timestamped folder and every file in it) and logs what changed:
new entries, removed entries, and size or mtime changes. It also records, at
each poll, the age of the newest mtime under the folder ("staleness"), which
is what a sweep that counts from the last write would see.

Usage:
  watch_run.py NAME JAR SPECDIR SPEC SECONDS [--java-opt OPT]... -- TLC-ARGS...

The run folder is runs/NAME next to this script; the spec files are copied in,
TLC runs there with -metadir runs/NAME/md. After SECONDS the TLC process is
sent SIGTERM by its pid (if it is still running). Output: runs/NAME/tlc.out,
runs/NAME/events.log, runs/NAME/summary.json.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def snapshot(root: Path) -> dict:
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        for name in [None] + dirnames + filenames:
            p = Path(dirpath) if name is None else Path(dirpath) / name
            try:
                st = os.lstat(p)
            except FileNotFoundError:
                continue
            rel = str(p.relative_to(root)) or "."
            kind = "d" if os.path.isdir(p) else "f"
            out[rel] = (kind, st.st_size, st.st_mtime_ns)
    return out


def main() -> None:
    argv = sys.argv[1:]
    sep = argv.index("--")
    head, tlc_args = argv[:sep], argv[sep + 1 :]
    name, jar, specdir, spec, seconds = head[:5]
    java_opts = []
    rest = head[5:]
    while rest:
        if rest[0] == "--java-opt":
            java_opts.append(rest[1])
            rest = rest[2:]
        else:
            raise SystemExit(f"unknown option {rest[0]}")
    seconds = float(seconds)
    rundir = HERE / "runs" / name
    if rundir.exists():
        shutil.rmtree(rundir)
    rundir.mkdir(parents=True)
    for f in Path(specdir).glob(spec + ".*"):
        shutil.copy(f, rundir)
    md = rundir / "md"
    md.mkdir()
    java = os.environ.get("JAVA", "java")
    cmd = [java, "-XX:+UseParallelGC", *java_opts, "-cp", jar, "tlc2.TLC",
           *tlc_args, "-metadir", str(md), spec + ".tla"]
    jver = subprocess.run([java, "-version"], capture_output=True, text=True).stderr.splitlines()[0]
    out = open(rundir / "tlc.out", "w")
    log = open(rundir / "events.log", "w")
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=rundir, stdout=out, stderr=subprocess.STDOUT)
    prev = {}
    max_stale = 0.0
    max_stale_at = None
    newest_seen = 0
    write_times = []  # distinct values of the newest mtime, in seconds since start
    polls = 0
    killed = False
    while True:
        now = time.time()
        alive = proc.poll() is None
        if alive and not killed and now - t0 >= seconds:
            os.kill(proc.pid, signal.SIGTERM)
            killed = True
        snap = snapshot(md)
        polls += 1
        rel_t = now - t0
        for k in sorted(set(prev) | set(snap)):
            a, b = prev.get(k), snap.get(k)
            if a is None:
                log.write(f"{rel_t:9.1f} NEW  {b[0]} {k} size={b[1]}\n")
            elif b is None:
                log.write(f"{rel_t:9.1f} GONE {a[0]} {k}\n")
            elif a != b:
                what = []
                if a[1] != b[1]:
                    what.append(f"size {a[1]}->{b[1]}")
                if a[2] != b[2]:
                    what.append("mtime")
                log.write(f"{rel_t:9.1f} CHG  {b[0]} {k} {' '.join(what)}\n")
        prev = snap
        if snap:
            newest = max(v[2] for v in snap.values())
            if newest != newest_seen:
                newest_seen = newest
                write_times.append(round(newest / 1e9 - t0, 3))
            stale = now - newest / 1e9
            # Only while TLC runs, and not in the first seconds before TLC made its folder.
            if alive and rel_t > 5 and stale > max_stale:
                max_stale, max_stale_at = stale, rel_t
        log.flush()
        if not alive:
            break
        time.sleep(1.0)
    gaps = [b - a for a, b in zip(write_times, write_times[1:])]
    summary = {
        "name": name,
        "jar": jar.replace(str(HERE.parent), "<tmp>"),
        "java": jver,
        "tlc_args": tlc_args,
        "java_opts": java_opts,
        "duration_s": round(time.time() - t0, 1),
        "stopped_by_sigterm": killed,
        "exit_code": proc.returncode,
        "polls": polls,
        "distinct_newest_mtimes": len(write_times),
        "max_staleness_while_running_s": round(max_stale, 1),
        "max_staleness_at_s": None if max_stale_at is None else round(max_stale_at, 1),
        "max_gap_between_newest_mtimes_s": round(max(gaps), 1) if gaps else None,
        "files_at_end": len([k for k, v in prev.items() if v[0] == "f"]),
        "bytes_at_end": sum(v[1] for v in prev.values() if v[0] == "f"),
    }
    (rundir / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
