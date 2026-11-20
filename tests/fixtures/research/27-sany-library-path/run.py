"""Research 27: does standalone SANY honour -DTLA-Library and classpath entries like TLC does?
Usage: python run.py WORK JARS OUT [JAVA]   (WORK from setup.sh; JARS has v1.7.4/ and rolling/; CM has the
CommunityModules jars in WORK/cm and WORK/cm-deps).  Writes OUT/<id>.{cmd,out,err,exit}."""
import os, subprocess, sys, shutil, pathlib
W = pathlib.Path(sys.argv[1]).resolve(); JARS = pathlib.Path(sys.argv[2]).resolve()
OUT = pathlib.Path(sys.argv[3]).resolve(); JAVA = sys.argv[4] if len(sys.argv) > 4 else "java"
OUT.mkdir(parents=True, exist_ok=True)
SEP = os.pathsep
VERS = {"v1.7.4": JARS / "v1.7.4/tla2tools.jar", "rolling": JARS / "rolling/tla2tools.jar"}
SANY, TLC = "tla2sany.SANY", "tlc2.TLC"
TOOLS = ("sany",) if os.environ.get("ONLY_SANY") else ("sany", "tlc")

def spec(extends, extra=""):
    ext = ", ".join(["Naturals"] + extends)
    return (f"---- MODULE S ----\nEXTENDS {ext}\nVARIABLE v\nInit == v = 0\nNext == v' = v\n"
            f"Spec == Init /\\ [][Next]_v\n{extra}\n====\n")

def write_spec(d, extends, extra=""):
    d.mkdir(parents=True, exist_ok=True)
    (d / "S.tla").write_text(spec(extends, extra))
    (d / "S.cfg").write_text("SPECIFICATION Spec\n")

def run(cid, ver, tool, cwd, specarg, lib=None, cp=(), extra_opts=()):
    jar = VERS[ver]
    cmd = [JAVA]
    if lib is not None: cmd.append(f"-DTLA-Library={lib}")
    cmd += ["-cp", SEP.join([str(jar)] + [str(c) for c in cp])]
    if tool == "sany": cmd += [SANY, specarg]
    else:
        md = W / "meta" / cid; shutil.rmtree(md, ignore_errors=True)
        cmd += [TLC, "-metadir", str(md), "-workers", "1", specarg]
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)
        o, e, x = r.stdout, r.stderr, r.returncode
    except subprocess.TimeoutExpired:
        o, e, x = "", "TIMEOUT", -1
    def scrub(s):
        s = s.replace(str(W), "<work>").replace(str(JARS), "<jars>").replace(str(pathlib.Path.home()), "<home>")
        import re, tempfile
        s = re.sub(r"Start time: .*|Finished in .*|Computing initial states.*|Finished computing.*|Progress.*|Starting\.\.\. .*|Finished checking.*|\(\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d\)", "", s)
        return s
    base = OUT / f"{ver}-{tool}-{cid}"
    pathlib.Path(str(base) + ".cmd").write_text(scrub(" ".join(cmd)) + f"\n# cwd={scrub(str(cwd))}\n")
    pathlib.Path(str(base) + ".out").write_text(scrub(o)); (pathlib.Path(str(base) + ".err")).write_text(scrub(e))
    pathlib.Path(str(base) + ".exit").write_text(f"{x}\n")
    return x, o, e

def verdict(x, o, e, tool):
    t = o + e
    if "Cannot find source file for module" in t or "Could not find module" in t or "Cannot find" in t: miss = True
    else: miss = False
    return f"exit={x} {'MODULE-NOT-FOUND' if miss else ('ok' if x == 0 or (tool=='sany' and 'Semantic' in t) else 'other')}"

rows = []
def case(cid, extends, tool, ver, lib=None, cp=(), cwd="spec", extra="", absolute=False, sibling=None):
    d = W / "spec"
    write_spec(d, extends, extra)
    cwd_p = W / cwd
    specarg = str(d / "S.tla") if absolute else "S.tla"
    x, o, e = run(cid, ver, tool, cwd_p, specarg, lib, cp)
    rows.append((ver, tool, cid, verdict(x, o, e, tool)))
    return x, o, e

A, B, C, J = W / "libA", W / "libB", W / "cpdir", W / "mods.jar"
CM, CMD = next((W / "cm").glob("*.jar")), next((W / "cm-deps").glob("*.jar"))
for ver in (VERS if not os.environ.get("ONLY_LADDER") else ()):
    for tool in TOOLS:
        case("01-lib-one", ["OnlyInLibA"], tool, ver, lib=A)
        case("02-no-lib-control", ["OnlyInLibA"], tool, ver)
        case("03-lib-two", ["OnlyInLibA", "OnlyInLibB"], tool, ver, lib=f"{A}{SEP}{B}")
        case("04-lib-second-only", ["OnlyInLibB"], tool, ver, lib=f"{A}{SEP}{B}")
        case("05-lib-trailing-sep", ["OnlyInLibB"], tool, ver, lib=f"{A}{SEP}{B}{os.sep}")
        case("06-lib-missing-entry", ["OnlyInLibB"], tool, ver, lib=f"{W/'nope'}{SEP}{B}")
        case("07-lib-empty-entry", ["OnlyInLibB"], tool, ver, lib=f"{A}{SEP}{SEP}{B}")
        case("08-lib-relative", ["OnlyInLibA"], tool, ver, lib="../libA")
        case("09-cp-folder-only", ["OnlyInCpDir"], tool, ver, cp=[C])
        case("10-cp-jar-only", ["OnlyInJar"], tool, ver, cp=[J])
        case("11-cm-jar-cp", ["Functions"], tool, ver, cp=[CM])
        case("12-cm-deps-jar-cp", ["Functions"], tool, ver, cp=[CMD])
        case("13-cm-jar-no-cp-control", ["Functions"], tool, ver)
        case("14-cm-jar-in-library", ["Functions"], tool, ver, lib=CM)  # a jar given as a library entry
        case("15-lib-and-cp-folder", ["OnlyInLibA", "OnlyInCpDir"], tool, ver, lib=A, cp=[C])
        case("16-other-cwd-absolute-spec-sibling", ["Dup"], tool, ver, cwd="other", absolute=True)
        case("17-other-cwd-relative-spec", ["Dup"], tool, ver, cwd="other")  # spec path relative to wrong folder
# precedence ladder: Dup exists in spec folder, libA, libB, cpdir, dup.jar
LADDER = lambda tool, ver, tag, **k: case(tag, ["TLC", "Dup"], tool, ver, extra='ASSUME PrintT(<<"WHERE", Where>>)', **k)
for ver in VERS:
    for tool in TOOLS:
        full = dict(lib=f"{A}{SEP}{B}", cp=[C, W / "dup.jar"])
        LADDER(tool, ver, "20-ladder-all", **full)
        # remove the winner step by step
        (W/"spec/Dup.tla").rename(W/"spec/Dup.tla.off")
        # case() rewrites S only, so Dup.tla stays removed
        LADDER(tool, ver, "21-ladder-no-spec-dup", **full)
        (W/"libA/Dup.tla").rename(W/"libA/Dup.tla.off")
        LADDER(tool, ver, "22-ladder-no-spec-libA", **full)
        (W/"libB/Dup.tla").rename(W/"libB/Dup.tla.off")
        LADDER(tool, ver, "23-ladder-cp-folder-before-jar", lib=None, cp=[C, W / "dup.jar"])
        LADDER(tool, ver, "24-ladder-jar-before-cp-folder", lib=None, cp=[W / "dup.jar", C])
        # restore
        for p in ("spec/Dup.tla", "libA/Dup.tla", "libB/Dup.tla"): (W/(p+".off")).rename(W/p)
        # library module named like a standard module (Naturals) in libA, spec folder untouched
        (W/"libA/Naturals.tla").write_text('---- MODULE Naturals ----\nNat == {0}\nWhere == "fake-naturals"\n====\n')
        case("25-std-name-in-library", ["TLC"], tool, ver, lib=A, extra='ASSUME PrintT(<<"WHERE", Where>>)')
        (W/"libA/Naturals.tla").unlink()
        # library module named like a standard module in the spec folder
        (W/"spec/Naturals.tla").write_text('---- MODULE Naturals ----\nNat == {0}\nWhere == "fake-naturals-in-spec"\n====\n')
        case("26-std-name-in-spec-folder", ["TLC"], tool, ver, extra='ASSUME PrintT(<<"WHERE", Where>>)')
        (W/"spec/Naturals.tla").unlink()
        # standard module name in a cp folder
        (W/"cpdir/Naturals.tla").write_text('---- MODULE Naturals ----\nNat == {0}\nWhere == "fake-naturals-in-cpdir"\n====\n')
        case("27-std-name-in-cp-folder", ["TLC"], tool, ver, cp=[C], extra='ASSUME PrintT(<<"WHERE", Where>>)')
        (W/"cpdir/Naturals.tla").unlink()
for r in rows: print(*r)
