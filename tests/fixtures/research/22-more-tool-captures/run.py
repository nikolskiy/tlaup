#!/usr/bin/env python3
"""Driver for research question 22. Runs every case on one version and writes, per case,
<version>/<case>.out (stdout), <version>/<case>.err (stderr), a line in <version>/commands.txt and a
table in <version>/README.md.

usage: TLAUP_TMP=<scratch> python3 run.py v1.7.4|v1.8.0 [case-substring ...]

Needs: java on PATH, javac (for the Boom override classes), the two jars under $TLAUP_TMP/jars/<v>/.
Work folders and TLC state (-metadir) are created under $TLAUP_TMP/q22/, never under /tmp.
Paths in the written files are replaced: the scratch root by <tmp>, the repository by <repo>.
Each case runs in its own fresh copy of the spec folder, so files TLC writes next to a spec are listed per case.
"""
import os, re, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
RES = HERE.parent
TMP = Path(os.environ["TLAUP_TMP"])
Q = TMP / "q22"
VER = sys.argv[1]
FILTER = sys.argv[2:]
JAR = TMP / "jars" / VER / "tla2tools.jar"
OUT = HERE / VER
OUT.mkdir(exist_ok=True)
WORK = Q / "work" / VER
META = Q / "meta" / VER
for d in (WORK, META):
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
Q1 = RES / "01-tlc-output"
Q12 = RES / "12-sany-pcal-repl" / VER / "inputs"
Q15 = RES / "15-exit-codes" / "specs"
Q22 = HERE / "specs"
INP = OUT / "inputs"   # generated per version (stale PlusCal files)
SIDE = Path(VER)


def clean(b: bytes) -> str:
    s = b.decode("utf-8", "replace")
    return s.replace(str(TMP), "<tmp>").replace(str(REPO), "<repo>")


def compile_classes():
    cls = Q / "classes" / VER
    if cls.exists():
        return
    cls.mkdir(parents=True)
    src = [str(p) for p in (Q1 / "specs" / "java").rglob("*.java")]
    subprocess.run(["javac", "--release", "11", "-cp", str(JAR), "-d", str(cls)] + src, check=True)


def make_dir(group, name):
    d = WORK / name
    d.mkdir()
    def cp(src):
        for p in src.iterdir():
            if p.is_file():
                shutil.copy(p, d)
    if group == "q1":
        cp(Q1 / "specs")
        (d / "classes").symlink_to(Q / "classes")
    elif group == "q15":
        cp(Q15)
    elif group == "q12":
        cp(Q12)
    elif group == "q22":
        cp(Q22)
        if INP.exists():
            cp(INP)
    elif group.startswith("one:"):          # one input file of question 12, copied alone (PlusCal cases)
        shutil.copy(Q12 / group[4:], d)
    return d


def listing(d):
    out = set()
    for p in d.rglob("*"):
        if p.is_file() and "classes" not in p.relative_to(d).parts:
            out.add(str(p.relative_to(d)))
    return out


def run(case, group, args, stdin=None, timeout=120, kill_after=None, cp=None, meta=False, note="", jvm=()):
    """args: everything after `java -cp <cp>`. A literal <metadir> in args is the case's -metadir folder."""
    if FILTER and not any(f in case for f in FILTER):
        return
    d = make_dir(group, case)
    md = META / case
    before = listing(d)
    argv = [a.replace("<metadir>", str(md)) for a in args]
    cpath = (cp or "tla2tools.jar").replace("tla2tools.jar", str(JAR))
    cmd = ["java"] + list(jvm) + ["-cp", cpath] + argv
    shown = "java " + " ".join(jvm) + (" " if jvm else "") + "-cp " + (cp or "tla2tools.jar") + " " + " ".join(args)
    if stdin is not None:
        shown = "printf %s | " % repr(stdin) + shown
    fo, fe = OUT / (case + ".out"), OUT / (case + ".err")
    t0 = time.time()
    with open(fo, "wb") as o, open(fe, "wb") as e:
        p = subprocess.Popen(cmd, cwd=d, stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                             stdout=o, stderr=e)
        if stdin is not None:
            try:
                p.stdin.write(stdin.encode()); p.stdin.close()
            except BrokenPipeError:
                pass
        why = ""
        while p.poll() is None:
            time.sleep(0.2)
            el = time.time() - t0
            if kill_after and el > kill_after:
                p.terminate(); why = "SIGTERM sent at %ds" % kill_after; break
            if el > timeout:
                p.kill(); why = "killed at timeout %ds" % timeout; break
            if os.path.getsize(fo) + os.path.getsize(fe) > 300_000:
                p.kill(); why = "killed: output over 300 KB"; break
        try:
            p.wait(30)
        except subprocess.TimeoutExpired:
            p.kill(); p.wait()
    rc = p.returncode
    if rc < 0:
        rc = 128 - rc
    for f in (fo, fe):
        f.write_text(clean(f.read_bytes()))
    new = sorted(listing(d) - before)
    mdl = ""
    if md.exists():
        mdl = " ".join(sorted(str(x.relative_to(md)) for x in md.rglob("*") if x.is_file() and x.stat().st_size >= 0))[:300]
    line = "%s | %s | exit=%d%s" % (case, clean(shown.encode()), rc, (" (%s)" % why) if why else "")
    with open(OUT / "commands.txt", "a") as c:
        c.write(line + "\n")
    with open(OUT / "table.tsv", "a") as t:
        t.write("\t".join([case, clean(shown.encode()), str(rc) + (" " + why if why else ""),
                           str(fo.stat().st_size), str(fe.stat().st_size), " ".join(new), mdl, note]) + "\n")
    print(line, "| out=%d err=%d" % (fo.stat().st_size, fe.stat().st_size), flush=True)
    return d, md, rc


def tlc(case, spec, *flags, group="q22", tool=True, **kw):
    a = ["tlc2.TLC"] + (["-tool"] if tool else []) + list(flags) + ["-metadir", "<metadir>"] + ([spec] if spec else [])
    return run(case, group, a, **kw)


def sany(case, *args, group="q12", **kw):
    return run(case, group, ["tla2sany.SANY"] + list(args), **kw)


def pcal(case, src, *args, **kw):
    return run(case, "one:" + src, ["pcal.trans"] + list(args), **kw)


def prep_stale():
    """Translate Pcal.tla under three module names with this version's translator and edit the result, so that
    SANY and TLC see a stale algorithm, a stale translation, and both."""
    INP.mkdir(exist_ok=True)
    for f in INP.iterdir():
        f.unlink()
    src = (Q12 / "Pcal.tla").read_text()
    for name, edit in (("PcalStaleAlg", "alg"), ("PcalStaleTla", "tla"), ("PcalStaleBoth", "both")):
        t = Q / "prep" / VER / name
        shutil.rmtree(t, ignore_errors=True); t.mkdir(parents=True)
        (t / (name + ".tla")).write_text(src.replace("Pcal", name))
        subprocess.run(["java", "-cp", str(JAR), "pcal.trans", name], cwd=t, capture_output=True, check=True)
        txt = (t / (name + ".tla")).read_text()
        if edit in ("alg", "both"):
            assert "A: x := x + 1;" in txt
            txt = txt.replace("A: x := x + 1;", "A: x := x + 2;", 1)
        if edit in ("tla", "both"):
            m = re.search(r"^(A\(self\)|A) == .*$", txt, re.M)
            line = "A == /\\ pc = \"A\""
            assert line in txt, "translation line not found"
            txt = txt.replace(line, "A == /\\ pc = \"A\" /\\ TRUE", 1)
        (INP / (name + ".tla")).write_text(txt)
        (INP / (name + ".cfg")).write_text("SPECIFICATION Spec\nCHECK_DEADLOCK FALSE\n")


def q1_cases():
    cmds = (Q1 / VER.lstrip("v") / "commands.txt").read_text().splitlines()
    for ln in cmds:
        name, cmd, _ = [x.strip() for x in ln.split(" | ")]
        toks = cmd.split()
        assert toks[:2] == ["java", "-cp"]
        cp, args = toks[2], toks[3:]
        run("q01-" + name, "q1", args, cp=cp)


def q12_cases():
    skip = {"pcal-retranslate-and-lint", "repl-pty-session", "repl-history-file-contents", "sany-message-codes",
            "sany-d-interactive"}
    # union of the commands of both versions, so that a flag that exists on one build is tried on the other
    seen = {}
    for v in ("v1.8.0", "v1.7.4"):
        for f in sorted((RES / "12-sany-pcal-repl" / v / "outputs").glob("*.txt")):
            n = f.stem
            if n in skip or n in seen:
                continue
            first = f.read_text().splitlines()[0]
            seen[n] = first
    for n, first in sorted(seen.items()):
        stdin = None
        if n == "repl-stdin-eof":
            run("q12-" + n, "q12", ["tlc2.REPL"], stdin="1+1\n2*3\n{1,2,3} \\cup {4}\nx\nFoo(\n:q\n", timeout=60)
            continue
        if n == "repl-via-tlc-flag":
            run("q12-" + n, "q12", ["tlc2.TLC", "-repl"], stdin="1+1\nx\n", timeout=60)
            continue
        if n == "sany-d-scripted":
            run("q12-" + n, "q12", ["tla2sany.SANY", "-d", "Good.tla"], stdin="cst\nquit\n", timeout=60)
            continue
        m = re.match(r"^\$ java -cp tla2tools\.jar (.*)$", first)
        assert m and "|" not in first and "#" not in first, (n, first)
        args = m.group(1).split()
        if args[0] == "pcal.trans":
            fl = [a for a in args[1:] if a.endswith(".tla") or re.match(r"^[A-Z]\w+$", a)]
            srcfile = {"pcal-badopt": "Pcal.tla", "pcal-nofile": "Good.tla", "pcal-noext": "Pcal.tla",
                       "pcal-help": "Pcal.tla", "pcal-noargs": "Pcal.tla"}.get(n)
            if not srcfile:
                srcfile = [a for a in args[1:] if a.endswith(".tla")][0]
            run("q12-" + n, "one:" + srcfile, args)
        else:
            run("q12-" + n, "q12", args, timeout=60)


def new_cases():
    # -difftrace
    tlc("difftrace-violation", "Diff", "-difftrace")
    tlc("difftrace-violation-nodiff", "Diff", note="same spec without -difftrace, for comparison")
    tlc("difftrace-q1-violation", "Violation", "-difftrace", group="q1")
    tlc("difftrace-liveness", "DiffLive", "-difftrace")
    tlc("difftrace-liveness-nodiff", "DiffLive")
    tlc("difftrace-liveness-q1-back-to-state", "LiveBack", "-difftrace", group="q1")
    tlc("difftrace-liveness-q1-stuttering", "LiveStutter", "-difftrace", group="q1")
    tlc("difftrace-deadlock", "Deadlock", "-difftrace", group="q1")
    tlc("difftrace-workers-4", "Diff", "-difftrace", "-workers", "4")
    # simulation and generate
    tlc("simulate-violation", "Violation", "-simulate", "num=5", "-depth", "20", "-seed", "7", group="q1")
    tlc("simulate-violation-diff", "Diff", "-simulate", "num=5", "-depth", "20", "-seed", "7", "-difftrace")
    tlc("simulate-deadlock", "Deadlock", "-simulate", "num=3", "-depth", "20", "-seed", "7", group="q1")
    tlc("simulate-liveness", "LiveBack", "-simulate", "num=3", "-depth", "20", "-seed", "7", group="q1")
    tlc("generate-violation", "Violation", "-generate", group="q1")
    tlc("generate-violation-num", "Violation", "-generate", "num=3", group="q1")
    tlc("generate-success", "Success", "-generate", group="q1")
    tlc("generate-success-num", "Success", "-generate", "num=3", group="q1")
    tlc("generate-deadlock", "Deadlock", "-generate", group="q1")
    tlc("generateSpecTE-violation", "Violation", "-generateSpecTE", group="q1")
    tlc("noGenerateSpecTE-violation", "Violation", "-noGenerateSpecTE", group="q1")
    # dfid
    tlc("dfid-success", "Success", "-dfid", "5", group="q1")
    tlc("dfid-violation", "Violation", "-dfid", "2", group="q1")
    tlc("dfid-deadlock", "Deadlock", "-dfid", "2", group="q1")
    tlc("dfid-violation-deep", "Violation", "-dfid", "10", group="q1")
    tlc("dfid-success-deep", "Success", "-dfid", "20", group="q1")
    # ALIAS and action shapes
    tlc("alias-violation", "Alias")
    tlc("alias-violation-difftrace", "Alias", "-difftrace")
    tlc("params-violation", "Params")
    tlc("params-violation-difftrace", "Params", "-difftrace")
    tlc("params-step-violation", "Params", "-config", "ParamsX.cfg")
    tlc("params-step-violation-difftrace", "Params", "-config", "ParamsX.cfg", "-difftrace")
    tlc("params-instance-exists-violation", "Params", "-config", "ParamsQ.cfg")
    tlc("params-instance-exists-violation-difftrace", "Params", "-config", "ParamsQ.cfg", "-difftrace")
    # deadlock with -deadlock
    tlc("deadlock-flag", "Deadlock", "-deadlock", group="q1")
    tlc("deadlock-flag-multierror", "MultiError", "-deadlock", "-continue", group="q1")
    # -tool for errors that question 15 captured in plain mode
    for c in ("Assum", "Eval", "NextEval", "Act", "BadCfg", "CfgSyn", "Live", "Asrt"):
        tlc("tool-" + c.lower(), c, group="q15")
    tlc("tool-nocfg", "NoCfg", group="q15")
    tlc("tool-nospecfile", "NoSuchFile", group="q15")
    tlc("tool-cfg-missing", "Ok", "-config", "nope.cfg", group="q15")
    tlc("tool-workers-bad", "Ok", "-workers", "abc", group="q15")
    tlc("tool-missing-module", "MissMod")
    tlc("tool-name-mismatch", "Mismatch")
    tlc("tool-oom", "Oom", group="q15", jvm=["-Xmx64m"], timeout=120)
    tlc("plain-violation-files", "Violation", tool=False, group="q1", note="no -tool: does TLC write a trace-exploration spec next to the spec?")
    tlc("tool-noargs", None, group="q15")
    tlc("tool-help", None, "-help", group="q15")
    # warnings
    tlc("warn4802-tool", "Warn4802")
    tlc("warn4802-plain", "Warn4802", tool=False)
    tlc("warnstutter-tool", "WarnStutter")
    tlc("stale-alg-tool", "PcalStaleAlg")
    tlc("stale-tla-tool", "PcalStaleTla")
    tlc("stale-both-tool", "PcalStaleBoth")
    tlc("stale-alg-plain", "PcalStaleAlg", tool=False)
    # SANY alone
    sany("sany-help", "-help", group="q22")
    sany("sany-h", "-h", group="q22")
    sany("sany-stale-alg", "PcalStaleAlg.tla", group="q22")
    sany("sany-stale-tla", "PcalStaleTla.tla", group="q22")
    sany("sany-stale-both", "PcalStaleBoth.tla", group="q22")
    sany("sany-stale-two-files", "PcalStaleAlg.tla", "PcalStaleTla.tla", group="q22")
    sany("sany-missing-module-ext", "MissMod.tla", group="q22")
    sany("sany-name-mismatch-ext", "Mismatch.tla", group="q22")
    sany("sany-warn4802", "Warn4802.tla", group="q22")
    sany("sany-grouped-ls", "-ls", "Good.tla")
    sany("sany-separate-l-s", "-l", "-s", "Good.tla")
    sany("sany-grouped-ls-semerr", "-ls", "SemErr.tla")
    sany("sany-s-semerr", "-s", "SemErr.tla")
    sany("sany-grouped-dl", "-dl", "Good.tla", stdin="quit\n", timeout=30)
    sany("sany-separate-d-l", "-d", "-l", "Good.tla", stdin="quit\n", timeout=30)
    sany("sany-grouped-lerror-codes", "-l", "-error-codes", "LevelErr.tla")
    sany("sany-grouped-unknown", "-xy", "Good.tla")
    sany("sany-levelerr-174", "LevelErr.tla")
    sany("sany-level-174", "Level.tla")
    sany("sany-levelerr-errorcodes-174", "-error-codes", "LevelErr.tla")
    sany("sany-nofile-no-sep", "Nope.tla")
    # checkpoint and recover (slow: the first interval is 1 minute)
    r = tlc("checkpoint-run", "Slow", "-checkpoint", "1", kill_after=80, timeout=200,
            note="TLC stopped by SIGTERM about 80 s after the start, after the first checkpoint")
    if r:
        d, md, rc = r
        ids = sorted(p.name for p in md.iterdir() if p.is_dir())
        if ids:
            full = str(md / ids[-1])
            if FILTER and not any(f in "checkpoint-recover" for f in FILTER) and not any(f in "checkpoint" for f in FILTER):
                return
            run("checkpoint-recover", "q22", ["tlc2.TLC", "-tool", "-recover", full, "Slow"], timeout=400,
                note="-recover with the folder the first run left behind (path shown with <tmp>)")
        else:
            print("no checkpoint folder left", flush=True)
    run("checkpoint-recover-missing", "q22", ["tlc2.TLC", "-tool", "-recover", "<metadir>/nope", "Slow"], timeout=60)


def write_readme():
    rows = [l.rstrip("\n").split("\t") for l in (OUT / "table.tsv").read_text().splitlines()]
    with open(OUT / "README.md", "w") as f:
        f.write("# Captures for research question 22, %s\n\n" % VER)
        f.write("Generated by `../run.py`. One case = `<case>.out` (stdout), `<case>.err` (stderr), one line in `commands.txt`.\n")
        f.write("Paths: `<tmp>` is the scratch root, `<repo>` the repository. `<metadir>` stands for a fresh -metadir folder of the case.\n")
        f.write("Files are the bytes TLC wrote, with those two path replacements only.\n\n")
        f.write("| Case | Command | Exit | stdout bytes | stderr bytes | New files next to the spec | Note |\n|---|---|---|---|---|---|---|\n")
        for r in rows:
            r += [""] * (8 - len(r))
            f.write("| `%s` | `%s` | %s | %s | %s | %s | %s |\n" % (r[0], r[1].replace("|", "\\|"), r[2], r[3], r[4], r[5].replace("|", "\\|"), r[7]))


if __name__ == "__main__":
    for f in ("commands.txt", "table.tsv"):
        if not FILTER and (OUT / f).exists():
            (OUT / f).unlink()
    compile_classes()
    prep_stale()
    q1_cases()
    q12_cases()
    new_cases()
    write_readme()
