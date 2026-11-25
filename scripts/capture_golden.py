"""Capture the golden files of ``tests/parse/golden/`` again with a given jar (design 01 T3, package 07).

    python scripts/capture_golden.py --jar PATH --build NAME [--from NAME] [--only CASE ...] [--out DIR] [--tmp DIR]

Runs every case of the ``tlc``, ``sany`` and ``pcal`` folders the jar's release line already has (the folder whose
``build.toml`` says ``line = "rolling"`` for a jar with a build time, otherwise ``line = "stable"``; ``--from``
names another) and writes ``<tool>/NAME/<case>.out``, a ``<case>.err`` when TLC wrote to stderr, ``cases.toml`` with
the exit codes it saw and ``build.toml`` from the jar's manifest. It refuses to write into a folder that already holds
``.out`` files and prints every case whose exit code differs from the folder it ran from.

How a case runs, from its table in ``cases.toml``:

- In a fresh temporary copy of its spec folder (``cwd`` if given, else the folder of ``spec``; an empty folder when
  there is no spec). A PlusCal case gets only its spec file, as research 12 ran it, and records ``files_before`` and
  ``files_after``.
- ``java [jvm_options] -cp [classpath...:]JAR MAIN [args]``. For TLC, ``-tool`` comes first (not for a ``plain``
  case), then ``args``, then ``-metadir`` with a fresh folder, then the spec's module name. With no ``spec``, a last
  argument of ``args`` that is neither an option nor an option's value goes there instead (a missing spec's name).
  ``<metadir>`` in ``args`` stands for that fresh folder, and then no ``-metadir`` is added. For SANY and PlusCal
  ``args`` are the whole argument list, file names included, since the recorded file arguments are not always last
  nor ``<spec>.tla``.
- ``java_sources`` are compiled first with ``javac --release 11 -cp JAR -d classes``; ``classpath`` entries are
  relative to the run folder. A case whose class path names a folder that does not exist (research 28's, whose spec
  was not kept) or whose spec file is missing is skipped with the reason printed.
- The new ``cases.toml`` keeps each table's keys except ``note``, ``stderr`` and ``source``, which may no longer be
  true; ``exit``, ``java``, ``captured`` and, for PlusCal, the files are what this run saw.
- ``stdin`` is written to standard input; ``stopped`` stops the run the same way (``SIGTERM after N s``, ``killed by
  the driver after N s``); ``recover_from`` passes, after ``args`` and in place of ``-metadir``, the newest checkpoint
  folder that case left, running it first.
- TLC's stdout and stderr are read apart; SANY's and PlusCal's through one pipe, as ``tlaup sany`` and ``tlaup pcal``
  read them (design 21 S1). The repository and temporary paths are replaced by ``<repo>`` and ``<tmp>``; volatile
  values (times, pids, seeds, rates) are left as captured. The jar is copied into the temporary folder first, so its
  path shows as ``<tmp>``.

A developer tool, not run in CI: it needs ``java`` and ``javac`` and uses only the standard library. Keep the
temporary folder on a real disk (``--tmp``) for the large cases.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
GOLDEN = REPO / "tests" / "parse" / "golden"
SPECS = GOLDEN / "specs"
TOOLS = {"tlc": "tlc2.TLC", "sany": "tla2sany.SANY", "pcal": "pcal.trans"}
ORDER = (
    "spec",
    "args",
    "exit",
    "java",
    "captured",
    "files_before",
    "files_after",
    "stderr",
    "plain",
    "stdin",
    "jvm_options",
    "classpath",
    "java_sources",
    "cwd",
    "stopped",
    "recover_from",
    "note",
    "source",
)
TIMEOUT = 900.0
STOPPED = re.compile(r"^(SIGTERM|killed by the driver) after (\d+) s$")


class SkipError(Exception):
    """A case that cannot run here; the message says why."""


@dataclass
class Case:
    tool: str
    name: str
    table: dict[str, Any]

    @property
    def plain(self) -> bool:
        return bool(self.table.get("plain"))


@dataclass
class Result:
    exit: int
    stdout: bytes
    stderr: bytes
    files_before: list[str] = field(default_factory=list)
    files_after: list[str] = field(default_factory=list)
    metadir: Path | None = None


def read_manifest(jar: Path) -> dict[str, str]:
    with zipfile.ZipFile(jar) as archive:
        text = archive.read("META-INF/MANIFEST.MF").decode("utf-8")
    entries: dict[str, str] = {}
    for line in text.replace("\r\n", "\n").replace("\n ", "").splitlines():
        key, sep, value = line.partition(":")
        if sep:
            entries[key.strip()] = value.strip()
    return entries


def build_identity(jar: Path) -> dict[str, str]:
    """``build.toml``'s keys for a jar: a build time makes it the rolling line (design 01 T9)."""
    manifest = read_manifest(jar)
    identity = {"line": "stable", "tag": manifest.get("X-Git-Tag", ""), "commit": manifest.get("X-Git-Revision", "")}
    stamp = manifest.get("Build-TimeStamp", "")
    if stamp:
        when = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        identity |= {"line": "rolling", "tag": "rolling", "calver": when.strftime("%Y.%m.%d.%H%M%S")}
    identity["sha256"] = hashlib.sha256(jar.read_bytes()).hexdigest()
    return identity


def source_folder(tool: str, line: str, chosen: str | None) -> Path:
    if chosen:
        folder = GOLDEN / tool / chosen
        if not (folder / "cases.toml").is_file():
            sys.exit(f"{folder} has no cases.toml")
        return folder
    for build in sorted((GOLDEN / tool).glob("*/build.toml")):
        if tomllib.loads(build.read_text(encoding="utf-8")).get("line") == line:
            return build.parent
    sys.exit(f"no {tool} folder has line = {line!r}; name one with --from")


def load_cases(tool: str, folder: Path) -> list[Case]:
    data = tomllib.loads((folder / "cases.toml").read_text(encoding="utf-8"))
    plain = data.pop("plain", {})
    cases = [Case(tool, name, table) for name, table in data.items()]
    cases += [Case(tool, name, table) for name, table in plain.items()]
    return cases


def toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return "[" + ", ".join(toml_value(item) for item in value) + "]"


def write_cases(path: Path, tool: str, cases: list[tuple[Case, dict[str, Any]]]) -> None:
    lines = [f"# The {tool} golden cases of this build, captured by scripts/capture_golden.py.", ""]
    for case, table in sorted(cases, key=lambda pair: (pair[0].plain, pair[0].name)):
        lines.append(f"[{'plain.' if case.plain else ''}{case.name}]")
        lines += [f"{key} = {toml_value(table[key])}" for key in ORDER if key in table]
        lines.append("")
    path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")


def write_build(path: Path, identity: dict[str, str]) -> None:
    keys = ("line", "tag", "commit", "calver", "sha256")
    body = [f"{key} = {toml_value(identity[key])}" for key in keys if key in identity]
    path.write_text("# The jar this folder was captured with (design 01 T3).\n" + "\n".join(body) + "\n", "utf-8")


def java_version(java: str) -> str:
    shown = subprocess.run(
        [java, "-XshowSettings:properties", "-version"], capture_output=True, text=True, check=False
    ).stderr
    found = re.search(r"^\s*java\.version = (\S+)$", shown, re.MULTILINE)
    return found.group(1) if found else "unknown"


class Capture:
    def __init__(self, jar: Path, identity: dict[str, str], tmp: Path, java: str, javac: str) -> None:
        self.identity = identity
        self.java_version = java_version(java)
        self.today = dt.datetime.now(dt.UTC).date().isoformat()
        self.tmp = tmp
        self.jar = tmp / "tla2tools.jar"
        shutil.copyfile(jar, self.jar)
        self.java = java
        self.javac = javac
        self.metadirs: dict[str, Path] = {}

    def clean(self, data: bytes) -> bytes:
        pairs = sorted(((str(self.tmp), "<tmp>"), (str(REPO), "<repo>")), key=lambda pair: -len(pair[0]))
        for path, mark in pairs:
            data = data.replace(path.encode(), mark.encode())
        return data

    def prepare(self, case: Case) -> tuple[Path, str | None]:
        """The run folder and the spec's argument (its module name relative to the folder)."""
        table = case.table
        run = self.tmp / case.tool / (("plain-" if case.plain else "") + case.name) / "run"
        spec = SPECS / (table["spec"] + ".tla") if "spec" in table else None
        if spec is not None and not spec.is_file():
            reason = f"no spec file {spec.relative_to(REPO)}"
            raise SkipError(reason)
        if case.tool == "pcal":
            run.mkdir(parents=True)
            if spec is not None:
                shutil.copy(spec, run)
            return run, None
        source = SPECS / table["cwd"] if "cwd" in table else (spec.parent if spec is not None else None)
        if source is None:
            run.mkdir(parents=True)
            return run, None
        shutil.copytree(source, run)
        return run, (spec.relative_to(source).with_suffix("").as_posix() if spec is not None else None)

    def compile(self, case: Case, run: Path) -> None:
        sources = case.table.get("java_sources", [])
        if sources:
            done = subprocess.run(
                [self.javac, "--release", "11", "-cp", str(self.jar), "-d", str(run / "classes"), *sources],
                cwd=run,
                capture_output=True,
                check=False,
            )
            if done.returncode != 0:
                reason = "javac failed: " + done.stderr.decode(errors="replace").strip()
                raise SkipError(reason)
        for entry in case.table.get("classpath", []):
            if not (run / entry).exists():
                reason = f"class path entry {entry} does not exist (no spec or sources kept)"
                raise SkipError(reason)

    def command(self, case: Case, run: Path, spec_arg: str | None) -> tuple[list[str], Path | None]:
        table = case.table
        classpath = [str(run / entry) for entry in table.get("classpath", [])] + [str(self.jar)]
        argv = [self.java, *table.get("jvm_options", []), "-cp", ":".join(classpath), TOOLS[case.tool]]
        if case.tool != "tlc":
            return argv + list(table.get("args", [])), None
        metadir = run.parent / "meta"
        args = [arg.replace("<metadir>", str(metadir)) for arg in table.get("args", [])]
        trailing: list[str] = []
        if (
            "spec" not in table
            and args
            and not args[-1].startswith("-")
            and not (args[-2:-1] or [""])[0].startswith("-")
        ):
            args, trailing = args[:-1], args[-1:]  # a spec name that does not exist: keep it last, as recorded
        argv += ([] if case.plain else ["-tool"]) + args
        if "recover_from" in table:
            folder = self.metadirs.get(table["recover_from"])
            checkpoints = sorted(p for p in folder.iterdir() if p.is_dir()) if folder and folder.is_dir() else []
            if not checkpoints:
                reason = f"{table['recover_from']} left no checkpoint folder"
                raise SkipError(reason)
            argv.append(str(checkpoints[-1]))
        elif not any("<metadir>" in arg for arg in table.get("args", [])):
            argv += ["-metadir", str(metadir)]
        if spec_arg is not None:
            argv.append(spec_arg)
        return argv + trailing, metadir

    def run(self, case: Case) -> Result:
        run, spec_arg = self.prepare(case)
        self.compile(case, run)
        argv, metadir = self.command(case, run, spec_arg)
        before = sorted(p.name for p in run.iterdir() if p.name != "classes")
        stdin = case.table.get("stdin")
        out, err = run.parent / "stdout", run.parent / "stderr"
        limit, signal = TIMEOUT, "kill"
        stopped = STOPPED.match(case.table.get("stopped", ""))
        if stopped:
            limit = float(stopped.group(2))
            signal = "term" if stopped.group(1) == "SIGTERM" else "kill"
        with out.open("wb") as stdout, err.open("wb") as stderr:
            process = subprocess.Popen(
                argv,
                cwd=run,
                stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr if case.tool == "tlc" else subprocess.STDOUT,
            )
            if stdin is not None and process.stdin is not None:
                try:
                    process.stdin.write(stdin.encode("utf-8"))
                    process.stdin.close()
                except BrokenPipeError:
                    pass
            try:
                process.wait(timeout=limit)
            except subprocess.TimeoutExpired:
                if not stopped:
                    print(f"  {case.tool}/{case.name}: still running after {limit:.0f} s, killed")
                (process.terminate if signal == "term" else process.kill)()
                process.wait()
        code = process.returncode if process.returncode >= 0 else 128 - process.returncode
        if metadir is not None:
            self.metadirs[case.name] = metadir
        after = sorted(p.name for p in run.iterdir() if p.name != "classes")
        return Result(code, self.clean(out.read_bytes()), self.clean(err.read_bytes()), before, after, metadir)


def ordered(cases: list[Case], only: set[str]) -> list[Case]:
    """The chosen cases, each ``recover_from`` case before the one that needs it."""
    by_name = {case.name: case for case in cases if not case.plain}
    chosen = [case for case in cases if not only or case.name in only]
    for case in list(chosen):
        needed = by_name.get(case.table.get("recover_from", ""))
        if needed is not None and needed not in chosen:
            chosen.append(needed)
    return sorted(chosen, key=lambda case: ("recover_from" in case.table, case.plain, case.name))


def capture_tool(capture: Capture, tool: str, folder: Path, target: Path, only: set[str]) -> list[str]:
    """Run one tool's cases into ``target``; return the cases whose exit code differs from ``folder``'s."""
    written: list[tuple[Case, dict[str, Any]]] = []
    differ: list[str] = []
    for case in ordered(load_cases(tool, folder), only):
        label = f"{tool}/{'plain/' if case.plain else ''}{case.name}"
        try:
            result = capture.run(case)
        except SkipError as skipped:
            print(f"skipped {label}: {skipped}")
            continue
        where = target / "plain" if case.plain else target
        where.mkdir(parents=True, exist_ok=True)
        (where / f"{case.name}.out").write_bytes(result.stdout)
        table = {key: value for key, value in case.table.items() if key not in ("stderr", "source", "note")}
        table |= {"exit": result.exit, "java": capture.java_version, "captured": capture.today}
        table["source"] = f"scripts/capture_golden.py, from {tool}/{folder.name}/{case.name}"
        if result.stderr:
            (where / f"{case.name}.err").write_bytes(result.stderr)
            table["stderr"] = f"{case.name}.err"
        if tool == "pcal":
            table |= {"files_before": result.files_before, "files_after": result.files_after}
        written.append((case, table))
        was = case.table.get("exit")
        changed = was is not None and was != result.exit
        print(f"{label}: exit {result.exit}" + (f" (was {was})" if changed else ""))
        if changed:
            differ.append(f"{label}: {was} -> {result.exit}")
    if written:
        write_cases(target / "cases.toml", tool, written)
        write_build(target / "build.toml", capture.identity)
    return differ


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--jar", type=Path, required=True, help="the tla2tools.jar to capture with")
    parser.add_argument("--build", required=True, help="the new folder's name: the tag, or the CalVer of a rolling jar")
    parser.add_argument("--from", dest="source", help="the folder to take the cases from (default: the jar's line)")
    parser.add_argument("--only", nargs="+", default=[], metavar="CASE", help="run only these cases")
    parser.add_argument("--out", type=Path, default=GOLDEN, help="where the tool folders go (default: the golden one)")
    parser.add_argument("--tmp", type=Path, help="the folder to make the temporary folder in")
    options = parser.parse_args(argv)

    if ":" in options.build or "/" in options.build:
        parser.error("--build must be a plain folder name (no ':' or '/')")
    java, javac = shutil.which("java"), shutil.which("javac")
    if not java or not javac:
        parser.error("java and javac must be on PATH")
    jar = options.jar.resolve()
    identity = build_identity(jar)
    plan = {tool: source_folder(tool, identity["line"], options.source) for tool in TOOLS}
    for tool in TOOLS:
        target = options.out / tool / options.build
        if target.is_dir() and any(target.rglob("*.out")):
            parser.error(f"{target} already holds .out files")

    tmp = Path(tempfile.mkdtemp(prefix="capture-", dir=options.tmp)).resolve()
    differ: list[str] = []
    try:
        capture = Capture(jar, identity, tmp, java, javac)
        for tool, folder in plan.items():
            differ += capture_tool(capture, tool, folder, options.out / tool / options.build, set(options.only))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if differ:
        print("Exit codes that differ from the folder the cases came from:")
        for line in differ:
            print("  " + line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
