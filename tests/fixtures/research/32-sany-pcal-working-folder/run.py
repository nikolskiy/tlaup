#!/usr/bin/env python3
"""Question 32: does standalone SANY / pcal.trans behave the same when started in another folder
with the spec as an absolute (or ../relative) path as when started in the spec's folder with the bare name?

usage: run.py JAR JAVA OUTDIR
Each (scenario, mode) runs in a fresh tree.  Modes:
  A  cwd = <w>/spec   arg = Name.tla                (the way research 12 ran)
  B  cwd = <w>/other  arg = <w>/spec/Name.tla       (decision D34: absolute path)
  C  cwd = <w>/other  arg = ../spec/Name.tla        (relative path with a folder)
"""
import hashlib, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

JAR, JAVA, OUT = sys.argv[1], sys.argv[2], Path(sys.argv[3])

def mod(name, body="", extends="Naturals"):
    return f"---- MODULE {name} ----\nEXTENDS {extends}\n{body}\n====\n"

HELPER1 = mod("Helper", "H == 1")
HELPER2 = mod("Helper", "H == 2")
MAIN = mod("Main", "Op == H", "Naturals, Helper")
MAIN_PARSE = mod("Main", "x == \n", "Naturals, Helper")
MAIN_SEM = mod("Main", "Op == H + undefinedThing", "Naturals, Helper")
HELPER_PARSE = mod("Helper", "H == \n")
HELPER_SEM = mod("Helper", "H == nope")
MAIN_ALONE_BAD = mod("Main", "Op == nope2")
MAIN_MISSING = mod("Main", "Op == 1", "Naturals, NoSuchModule")

SANY = [  # name, spec file (spec/), other/ files, lib/ files, use_lib, target module file
    ("s01-helper-beside-spec", {"Main.tla": MAIN, "Helper.tla": HELPER1}, {}, {}, False),
    ("s02-helper-in-cwd-only", {"Main.tla": MAIN}, {"Helper.tla": HELPER2}, {}, False),
    ("s03-helper-beside-spec-and-cwd", {"Main.tla": MAIN, "Helper.tla": HELPER1}, {"Helper.tla": HELPER2}, {}, False),
    ("s04-helper-in-lib-only", {"Main.tla": MAIN}, {}, {"Helper.tla": HELPER1}, True),
    ("s05-helper-in-lib-and-beside-spec", {"Main.tla": MAIN, "Helper.tla": HELPER1}, {}, {"Helper.tla": HELPER2}, True),
    ("s06-helper-in-lib-and-cwd", {"Main.tla": MAIN}, {"Helper.tla": HELPER1}, {"Helper.tla": HELPER2}, True),
    ("s07-helper-nowhere", {"Main.tla": MAIN}, {}, {}, False),
    ("s08-missing-module", {"Main.tla": MAIN_MISSING}, {}, {}, False),
    ("s09-parse-error-in-spec", {"Main.tla": MAIN_PARSE, "Helper.tla": HELPER1}, {}, {}, False),
    ("s10-semantic-error-in-spec", {"Main.tla": MAIN_SEM, "Helper.tla": HELPER1}, {}, {}, False),
    ("s11-parse-error-in-helper", {"Main.tla": MAIN, "Helper.tla": HELPER_PARSE}, {}, {}, False),
    ("s12-semantic-error-in-helper", {"Main.tla": MAIN, "Helper.tla": HELPER_SEM}, {}, {}, False),
    ("s13-spec-copy-in-cwd-shadows", {"Main.tla": MAIN, "Helper.tla": HELPER1}, {"Main.tla": MAIN_ALONE_BAD}, {}, False),
    ("s14-no-such-input-file", {"Helper.tla": HELPER1}, {}, {}, False),
    ("s15-helper-in-lib-lib-given-relative", {"Main.tla": MAIN}, {}, {"Helper.tla": HELPER1}, "rel"),
    ("s16-specdir-on-TLA-Library", {"Main.tla": MAIN, "Helper.tla": HELPER1}, {}, {}, "specdir"),
    ("s17-specdir-on-classpath", {"Main.tla": MAIN, "Helper.tla": HELPER1}, {}, {}, "cp"),
    ("s18-specdir-on-TLA-Library-and-cwd-copy", {"Main.tla": MAIN, "Helper.tla": HELPER1}, {"Helper.tla": HELPER2}, {}, "specdir"),
    ("s19-specdir-on-classpath-and-cwd-copy", {"Main.tla": MAIN, "Helper.tla": HELPER1}, {"Helper.tla": HELPER2}, {}, "cp"),
]

PC = "---- MODULE Pc ----\nEXTENDS Naturals\n(*--algorithm Pc\nvariable x = 0;\nbegin\n  A: x := x + 1;\n  B: x := x + 1;\nend algorithm; *)\n====\n"
PC_ERR = "---- MODULE Pc ----\nEXTENDS Naturals\n(*--algorithm Pc\nvariable x = 0;\nbegin\n  A: x := x + ;\nend algorithm; *)\n====\n"
PC_NOLABEL = "---- MODULE Pc ----\nEXTENDS Naturals\n(*--algorithm Pc\nvariable x = 0;\nbegin\n  x := x + 1;\n  x := x + 1;\nend algorithm; *)\n====\n"
PC_DONE = None  # translated copy, filled in lazily
PC_REAL_ERR = "---- MODULE Pc ----\nEXTENDS Naturals\n(*--algorithm Pc\nvariable x = 0;\nbegin\n  A: goto Zzz;\nend algorithm; *)\n====\n"
PCFG = "SPECIFICATION Spec\n\\* user line\nCONSTANT N = 3\n"

PCAL = [  # name, spec/ files, other/ files, extra args, spec argument style
    ("p01-plain", {"Pc.tla": PC}, {}, [], "ext"),
    ("p02-existing-cfg-beside-spec", {"Pc.tla": PC, "Pc.cfg": PCFG}, {}, [], "ext"),
    ("p03-existing-cfg-in-cwd", {"Pc.tla": PC}, {"Pc.cfg": PCFG}, [], "ext"),
    ("p04-nocfg", {"Pc.tla": PC}, {}, ["-nocfg"], "ext"),
    ("p05-algorithm-error", {"Pc.tla": PC_ERR}, {}, [], "ext"),
    ("p05b-real-translator-error", {"Pc.tla": PC_REAL_ERR}, {}, [], "ext"),
    ("p06-existing-old-beside-spec", {"Pc.tla": PC, "Pc.old": "previous .old\n"}, {}, [], "ext"),
    ("p07-name-without-extension", {"Pc.tla": PC}, {}, [], "noext"),
    ("p08-writeAST", {"Pc.tla": PC}, {}, ["-writeAST"], "ext"),
    ("p09-labels-added", {"Pc.tla": PC_NOLABEL}, {}, [], "ext"),
    ("p10-no-such-file", {}, {}, [], "ext"),
    ("p11-spec-copy-in-cwd", {"Pc.tla": PC}, {"Pc.tla": PC_ERR}, [], "ext"),
    ("p12-translate-twice", {"Pc.tla": PC}, {}, [], "twice"),
    ("p13-unchanged-cwd-other-cfg-name", {"Pc.tla": PC, "Pc.cfg": PCFG}, {"Pc.cfg": "FROM-CWD\n"}, [], "ext"),
]

def norm(text, w):
    text = text.replace(str(w), "<w>")
    text = text.replace(JAR, "<jar>")
    text = re.sub(r"/tlc-\d+", "/tlc-<n>", text)
    text = re.sub(r"(Java|java)(\.version)?[ =:]+\S+", r"\1 <v>", text) if False else text
    return text

def snapshot(w):
    out = {}
    for p in sorted(Path(w).rglob("*")):
        if p.is_file():
            out[str(p.relative_to(w))] = p.read_bytes()
    return out

def place(w, spec, other, lib):
    for d, files in (("spec", spec), ("other", other), ("lib", lib)):
        (w / d).mkdir(parents=True, exist_ok=True)
        for n, c in files.items():
            (w / d / n).write_text(c)

def run(cmd, cwd, w):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)
    return r.returncode, norm(r.stdout, w), norm(r.stderr, w)

def one(kind, name, spec, other, lib, extra, style, mode, base):
    w = Path(tempfile.mkdtemp(prefix="q32w", dir=base))
    place(w, spec, other, lib)
    before = snapshot(w)
    stem = "Main" if kind == "sany" else "Pc"
    if kind == "sany" and name.startswith("s14"):
        stem = "Nope"
    ext = "" if style == "noext" else ".tla"
    cwd = {"A": w / "spec", "B": w / "other", "C": w / "other"}[mode]
    arg = {"A": f"{stem}{ext}", "B": f"{w}/spec/{stem}{ext}", "C": f"../spec/{stem}{ext}"}[mode]
    jopts = []
    jar = JAR
    if kind == "sany" and extra == "specdir":
        jopts = [f"-DTLA-Library={w}/spec"]
    elif kind == "sany" and extra == "cp":
        jar = f"{JAR}{os.pathsep}{w}/spec"
    elif kind == "sany" and extra:
        jopts = [f"-DTLA-Library={w}/lib" if extra is True else "-DTLA-Library=../lib"]
    cls = "tla2sany.SANY" if kind == "sany" else "pcal.trans"
    args = ([] if kind == "sany" else list(extra)) + [arg]
    cmd = [JAVA, *jopts, "-cp", jar, cls, *args]
    rc, so, se = run(cmd, cwd, w)
    outs = [(rc, so, se)]
    if style == "twice":
        outs.append(run(cmd, cwd, w))
    after = snapshot(w)
    ch = []
    for k in sorted(set(before) | set(after)):
        if k not in before: ch.append(f"NEW      {k}  sha={hashlib.sha256(after[k]).hexdigest()[:10]}")
        elif k not in after: ch.append(f"DELETED  {k}")
        elif before[k] != after[k]: ch.append(f"CHANGED  {k}  sha={hashlib.sha256(after[k]).hexdigest()[:10]}")
    text = f"$ cd <w>/{cwd.relative_to(w)}\n$ " + norm(f"java {' '.join(jopts)} -cp {jar} {cls} {' '.join(args)}", w) + "\n"
    for i, (rc, so, se) in enumerate(outs):
        text += f"--- run {i+1} stdout\n{so}--- run {i+1} stderr\n{se}--- run {i+1} exit {rc}\n"
    text += "--- files changed\n" + "\n".join(ch) + "\n"
    # keep contents of generated/changed files (small) for pcal
    for k in sorted(set(after)):
        if (k not in before or before[k] != after[k]) and len(after[k]) < 3000:
            text += f"--- content {k}\n{after[k].decode(errors='replace')}"
    shutil.rmtree(w)
    return text

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    base = Path(os.environ.get("Q32_WORK", tempfile.gettempdir()))
    res = {}
    for name, spec, other, lib, uselib in SANY:
        for m in "ABC":
            extra = uselib if uselib else None
            res[("sany", name, m)] = one("sany", name, spec, other, lib, extra, "ext", m, base)
    for name, spec, other, extra, style in PCAL:
        for m in "ABC":
            res[("pcal", name, m)] = one("pcal", name, spec, other, {}, extra, style, m, base)
    for (kind, name, m), t in res.items():
        d = OUT / kind; d.mkdir(exist_ok=True)
        (d / f"{name}.{m}.txt").write_text(t)
    # summary of A-vs-B and A-vs-C differences, ignoring the command lines
    import difflib
    lines = []
    for (kind, name, m) in res:
        if m != "A": continue
        for o in "BC":
            a = res[(kind, name, "A")].split("\n")[2:]
            b = res[(kind, name, o)].split("\n")[2:]
            d = list(difflib.unified_diff(a, b, "A", o, lineterm="", n=0))
            lines.append(f"##### {kind} {name}  A vs {o}: {'SAME' if not d else 'DIFFERENT'}")
            lines += d
    (OUT / "diffs.txt").write_text("\n".join(lines) + "\n")

main()
