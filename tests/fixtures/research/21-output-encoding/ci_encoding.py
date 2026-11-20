#!/usr/bin/env python3
"""q21: which encoding do TLC and the PlusCal translator write in, with and without JVM encoding options.
Run from the ci folder: python q21/encoding.py
Env: TLA2TOOLS_174, TLA2TOOLS_ROLLING (jar paths); optional JAVA11_HOME, JAVA21_HOME. Always exits 0."""
import os, re, shutil, subprocess, sys, tempfile, time

START = time.time()
BUDGET = 150
OS = sys.platform
VALUES = ["café", "日語文", "ø"]          # BMP characters that v1.7.4's lexer accepts
SPEC = '''---- MODULE Enc ----
EXTENDS Naturals, TLC
VARIABLE s
Init == s = "café"
Next == \\/ /\\ s = "café" /\\ s' = "日語文"
        \\/ /\\ s = "日語文" /\\ s' = "ø"
        \\/ /\\ s = "ø" /\\ s' = "ø"
Inv == s # "ø"
Spec == Init /\\ [][Next]_s
P == Print("print: café 日語文", TRUE)
====
'''
CFG = "SPECIFICATION Spec\nINVARIANT Inv\n"
PCAL = '''---- MODULE EncPcal ----
\\* before: café 日語文
EXTENDS Naturals, TLC
(* --algorithm Enc
variables x = "ascii";
begin
  \\* inside: café 日語文
  A: print "ascii only";
  B: x := "b";
end algorithm *)
\\* after: café 日語文
====
'''
OPTS = {"none": [], "utf8": ["-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-Dstderr.encoding=UTF-8"]}
ENCS = ["utf-8", "ascii", "cp1252", "cp850", "cp437", "mac_roman", "latin-1"]


def classify(raw, text):
    """Name the encoding under which `text` would give exactly `raw`."""
    if raw is None:
        return "no-line"
    if raw == text.encode("utf-8"):
        return "utf-8"
    if raw == text.encode("ascii", "replace"):
        return "ascii-?-replaced"
    for e in ENCS[2:]:
        if raw == text.encode(e, "replace"):
            return e
    if raw == b"?" * len(text.encode("utf-8")):
        return "per-byte-?-(input-misread)"
    return "other"


def run(cmd, cwd, timeout=60):
    try:
        p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           stdin=subprocess.DEVNULL, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except Exception as e:  # timeout, missing java
        return None, b"", ("%s" % e).encode()


def javas():
    found, seen = [], set()
    cands = [("path", shutil.which("java"))]
    for var in ("JAVA11_HOME", "JAVA21_HOME"):
        h = os.environ.get(var)
        if h:
            cands.append((var.split("_")[0].lower(), os.path.join(h, "bin", "java.exe" if os.name == "nt" else "java")))
    for label, exe in cands:
        if exe and os.path.exists(exe):
            real = os.path.realpath(exe)
            if real not in seen:
                seen.add(real)
                found.append((label, exe))
    return found


def props(java, work):
    rc, out, err = run([java, "-XshowSettings:properties", "-version"], work, 30)
    t = (out + err).decode("utf-8", "replace")
    got = {}
    for k in ("stdout.encoding", "native.encoding", "file.encoding", "sun.jnu.encoding"):
        m = re.search(r"^\s+%s = (\S+)" % re.escape(k), t, re.M)
        got[k] = m.group(1) if m else "n/a"
    m = re.search(r'version "([^"]+)"', t)
    return (m.group(1) if m else "?"), got


def main():
    work = tempfile.mkdtemp(prefix="q21-", dir=os.getcwd())
    try:
        with open(os.path.join(work, "Enc.tla"), "w", encoding="utf-8", newline="\n") as f:
            f.write(SPEC)
        with open(os.path.join(work, "Enc.cfg"), "w", encoding="utf-8", newline="\n") as f:
            f.write(CFG)
        jars = [("v1.7.4", os.environ.get("TLA2TOOLS_174")), ("rolling", os.environ.get("TLA2TOOLS_ROLLING"))]
        for jlabel, java in javas():
            ver, pr = props(java, work)
            pstr = " ".join("%s=%s" % kv for kv in pr.items())
            print("RESULT q21 java-properties %s : java=%s(%s) %s" % (OS, jlabel, ver, pstr))
            for jarname, jar in jars:
                if not jar or not os.path.exists(jar):
                    print("RESULT q21 skip %s : jar %s missing" % (OS, jarname))
                    continue
                for oname, opts in OPTS.items():
                    if time.time() - START > BUDGET:
                        print("RESULT q21 skip %s : time budget used up" % OS)
                        return
                    tag = "java=%s(%s) jar=%s opts=%s" % (jlabel, ver, jarname, oname)
                    meta = os.path.join(work, "m-%s-%s-%s-%s" % (jlabel, jarname, oname, ver))
                    rc, out, err = run([java] + opts + ["-cp", jar, "tlc2.TLC", "-metadir", meta, "-config", "Enc.cfg", "Enc.tla"], work, 90)
                    lines = [l.rstrip(b"\r") for l in out.split(b"\n")]
                    got = [m.group(1) for l in lines for m in [re.match(rb'^(?:/\\ )?s = "(.*)"$', l)] if m]
                    labels = [classify(g, v) for g, v in zip(got, VALUES)] if got else ["no-trace"]
                    pl = [l for l in lines if l.startswith(b'"print: ')]
                    plab = classify(pl[0][len(b'"print: '):].rstrip(b'"') if False else (pl[0][1:].rsplit(b'"', 1)[0] if pl else None), "print: café 日語文")
                    first = got[0] if got else b""
                    print("RESULT q21 tlc-output %s : %s rc=%s trace=%s print=%s hex(first-value)=%s stderr-bytes=%d"
                          % (OS, tag, rc, "/".join(labels), plab, first.hex(), len(err)))
                    # translator: non-ASCII only in comments; are the file's bytes kept?
                    pdir = os.path.join(work, "p-%s-%s-%s" % (jlabel, jarname, oname))
                    os.makedirs(pdir, exist_ok=True)
                    orig = PCAL.encode("utf-8")
                    with open(os.path.join(pdir, "EncPcal.tla"), "wb") as f:
                        f.write(orig)
                    prc, pout, perr = run([java] + opts + ["-cp", jar, "pcal.trans", "EncPcal.tla"], pdir, 90)
                    with open(os.path.join(pdir, "EncPcal.tla"), "rb") as f:
                        after = f.read().replace(b"\r\n", b"\n")
                    keep = [l for l in orig.split(b"\n") if "café".encode() in l]
                    ok = all(l in after.split(b"\n") for l in keep)
                    changed = next((l for l in keep if l not in after.split(b"\n")), b"")
                    ex = [l for l in after.split(b"\n") if l.startswith(b"\\* before")]
                    print("RESULT q21 pcal-rewrite %s : %s rc=%s comments-%s hex(before-line)=%s"
                          % (OS, tag, prc, "kept" if ok else "CHANGED", (ex[0] if ex else changed).hex()))
    except Exception as e:
        print("RESULT q21 error %s : %r" % (OS, e))
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except BaseException as e:
        print("RESULT q21 error %s : %r" % (OS, e))
    sys.exit(0)
