"""q24: where TLC resolves relative paths given to path-taking flags (absolute spec, other cwd),
and how it treats a spec reached through a symbolic link. Standard library only.
Env: TLA2TOOLS_174, TLA2TOOLS_ROLLING (jar paths); `java` on PATH. Always exits 0."""
import os, platform, re, shutil, subprocess, sys, tempfile

OS = {"Linux": "linux", "Darwin": "macos", "Windows": "windows"}.get(platform.system(), platform.system())
JARS = {"1.7.4": os.environ.get("TLA2TOOLS_174"), "1.8.0": os.environ.get("TLA2TOOLS_ROLLING")}


def res(check, outcome):
    print(f"RESULT q24 {check} {OS} : {outcome}", flush=True)


def w(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="\n") as f:
        f.write(text)


def spec(d):
    w(os.path.join(d, "Spec.tla"),
      '---- MODULE Spec ----\nEXTENDS Naturals, Helper, TLC\nCONSTANT N\nVARIABLE x\n'
      'Init == x = 0 /\\ PrintT(<<"N", N, "marker", Marker>>)\nNext == x < 3 /\\ x\' = x + 1\n'
      'Spec == Init /\\ [][Next]_x\nInv == x < 2\n====\n')


def helper(d, m):
    w(os.path.join(d, "Helper.tla"), f'---- MODULE Helper ----\nMarker == "{m}"\n====\n')


def cfg(path, n):
    w(path, f"SPECIFICATION Spec\nINVARIANT Inv\nCONSTANT N = {n}\n")


def tlc(ver, cwd, args, meta):
    cmd = ["java", "-cp", JARS[ver], "tlc2.TLC", "-nowarning", "-workers", "1", "-metadir", meta] + args
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=90)
        out = p.stdout + p.stderr
        rc = p.returncode
    except subprocess.TimeoutExpired:
        return None, "timeout", -1
    m = re.search(r'<<"N", (\d+), "marker", "([^"]*)">>', out)
    return (m.group(1) if m else None), (m.group(2) if m else None), rc, out


def ls(root):
    found = set()
    for dp, dn, fn in os.walk(root):
        for n in dn + fn:
            found.add(os.path.relpath(os.path.join(dp, n), root).replace("\\", "/"))
    return found


def main():
    for v, j in JARS.items():
        if not j or not os.path.exists(j):
            res("setup", f"jar for {v} missing"); return
    base = tempfile.mkdtemp(prefix="q24-")
    try:
        run(base)
    finally:
        shutil.rmtree(base, ignore_errors=True)


def run(base):
    T = os.path.realpath(base)
    for d in ("real/proj/sub", "work", "outside", "L", "Lf", "deep/a/b", "L2", "te"):
        os.makedirs(os.path.join(T, d), exist_ok=True)
    spec(os.path.join(T, "real/proj")); helper(os.path.join(T, "real/proj"), "helper-real")
    cfg(os.path.join(T, "real/proj/Spec.cfg"), 1)
    cfg(os.path.join(T, "real/out.cfg"), 4)
    cfg(os.path.join(T, "L/out.cfg"), 44); helper(os.path.join(T, "L"), "helper-beside-link-parent")
    spec(os.path.join(T, "deep/a/b")); helper(os.path.join(T, "deep/a/b"), "helper-real")
    cfg(os.path.join(T, "deep/a/b/Spec.cfg"), 11); cfg(os.path.join(T, "deep/a/out.cfg"), 12)
    cfg(os.path.join(T, "L2/out.cfg"), 99)
    helper(os.path.join(T, "Lf"), "helper-beside-file-link"); cfg(os.path.join(T, "Lf/Spec.cfg"), 77)
    helper(os.path.join(T, "work"), "helper-in-cwd")
    S = os.path.join(T, "real/proj/Spec.tla")
    work = os.path.join(T, "work")

    # 1. where relative paths of path-taking flags land (absolute spec, cwd = work)
    for ver in JARS:
        meta = os.path.join(T, "meta")
        cases = [("-dump", ["-dump", "relx"], "relx.dump"),
                 ("-metadir", None, "relmeta"),
                 ("-userFile", ["-userFile", "rel.out"], "rel.out")]
        if ver == "1.8.0":
            cases += [("-dumpTrace", ["-dumpTrace", "json", "rel.json"], "rel.json"),
                      ("-teSpecOutDir", ["-teSpecOutDir", "te"], "te/")]
        for name, args, marker in cases:
            before = ls(T)
            if name == "-metadir":
                cmd = ["java", "-cp", JARS[ver], "tlc2.TLC", "-nowarning", "-workers", "1", "-metadir", "relmeta", S]
                subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=90)
            else:
                tlc(ver, work, args + [S], meta)
            new = ls(T) - before
            hit = [n for n in new if n.rstrip("/").split("/")[-1].startswith(marker.rstrip("/").split("/")[-1])
                   or n.startswith(marker)]
            where = sorted({("cwd" if n.startswith("work/") else "spec-folder" if n.startswith("real/proj/") else n) for n in hit})
            res(f"flag-{name}-{ver}", "lands in " + (",".join(where) if where else "NOT FOUND, new files: " + ",".join(sorted(new))[:200]))
            # clean for the next case
            for n in sorted(new, reverse=True):
                p = os.path.join(T, n)
                if os.path.isfile(p) and not n.startswith("te/"):
                    os.remove(p)
            shutil.rmtree(os.path.join(work, "relmeta"), ignore_errors=True)

    # 2. cfg outside the spec's folder reached with .. , absolute spec, no link (the v1.7.4 case)
    for ver in JARS:
        r = tlc(ver, work, ["-config", "../out.cfg", S], os.path.join(T, "meta"))
        res(f"abs-spec-cfg-dotdot-{ver}", f"N={r[0]} (4 = the file beside the spec's parent; None = not read) rc={r[2]}")

    # 3. symlinks
    try:
        os.symlink(os.path.relpath(os.path.join(T, "real/proj"), os.path.join(T, "L")), os.path.join(T, "L/lnk"), target_is_directory=True)
        os.symlink(os.path.relpath(os.path.join(T, "deep/a/b"), os.path.join(T, "L2")), os.path.join(T, "L2/lnk"), target_is_directory=True)
        os.symlink(os.path.relpath(S, os.path.join(T, "Lf")), os.path.join(T, "Lf/Spec.tla"))
    except (OSError, NotImplementedError) as e:
        res("symlinks", f"SKIPPED: cannot create symbolic links ({type(e).__name__})"); return
    for ver in JARS:
        meta = os.path.join(T, "meta")
        r = tlc(ver, work, [os.path.join(T, "L/lnk/Spec.tla")], meta)
        res(f"link-folder-default-{ver}", f"N={r[0]} marker={r[1]} (expect N=1 helper-real)")
        r = tlc(ver, work, ["-config", "../out.cfg", os.path.join(T, "L/lnk/Spec.tla")], meta)
        res(f"link-folder-config-dotdot-{ver}", f"N={r[0]} (4 = operating system walked the link, 44 = TLC tidied .. as text)")
        r = tlc(ver, work, ["-config", "../out.cfg", os.path.join(T, "L2/lnk/Spec.tla")], meta)
        res(f"link-deep-config-dotdot-{ver}", f"N={r[0]} (12 = walked the link, 99 = tidied as text)")
        r = tlc(ver, work, [os.path.join(T, "L/lnk/../proj/Spec.tla")], meta)
        res(f"link-spec-path-with-dotdot-{ver}", f"N={r[0]} marker={r[1]} (1 = walked the link, None = tidied as text)")
        r = tlc(ver, work, [os.path.join(T, "Lf/Spec.tla")], meta)
        res(f"link-file-modules-{ver}", f"N={r[0]} marker={r[1]} (helper-beside-file-link/77 = beside the link; helper-real/1 = beside the target)")
        # R4 rule
        for label, sp, cf in [("folder-dotdot", "L2/lnk/Spec.tla", "L2/lnk/../out.cfg"),
                              ("beside-link-parent", "L2/lnk/Spec.tla", "L2/out.cfg"),
                              ("shallow-folder-dotdot", "L/lnk/Spec.tla", "L/lnk/../out.cfg")]:
            spp, cff = os.path.join(T, sp), os.path.join(T, cf)
            rel = os.path.relpath(os.path.realpath(cff), os.path.realpath(os.path.dirname(spp)))
            want = re.search(r"N = (\d+)", open(cff).read()).group(1)
            r = tlc(ver, work, ["-config", rel, spp], meta)
            res(f"r4-relative-config-{label}-{ver}", f"validated N={want} TLC read N={r[0]} -> {'same file' if r[0] == want else 'DIFFERENT or not read'}")


try:
    main()
except Exception as e:  # never fail the job
    res("script", f"error {type(e).__name__}: {e}")
