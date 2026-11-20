"""Question 28, part 3: what is the `java` on PATH, and does it pick a JDK by
itself? Written for macOS (/usr/bin/java and /usr/libexec/java_home); runs on
Linux and Windows too, for comparison.

Run from the `ci` folder:  python q28/java_launcher.py

Optional environment: JAVA11_HOME, JAVA21_HOME (JDK folders set up by the
workflow). Prints `RESULT q28 <check> <os> : <outcome>` lines; exits 0.
Paths under the runner's home folder are printed as `~`.
"""
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

OS = {"Linux": "linux", "Darwin": "macos", "Windows": "windows"}.get(platform.system(), platform.system())
EXE = ".exe" if os.name == "nt" else ""
HOME = str(Path.home())


def tidy(s):
    return s.replace(HOME, "~") if HOME and len(HOME) > 1 else s


def run(cmd, env=None, timeout=60):
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=timeout)
        return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return "timeout", "", ""
    except OSError as e:
        return "start-error", "", str(e)


def show(title, text):
    print(f"--- {title}")
    for line in text.strip().splitlines()[:40]:
        print("  " + tidy(line))


def version_and_home(java, env=None):
    code, out, err = run([str(java), "-XshowSettings:properties", "-version"], env=env)
    text = out + err
    home = re.search(r"^\s*java\.home = (.*)$", text, re.M)
    ver = re.search(r'version "([^"]+)"', text)
    return code, (ver.group(1) if ver else None), (home.group(1).strip() if home else None), text


def which_all(name):
    found = []
    for d in os.environ.get("PATH", "").split(os.pathsep):
        for n in ([name + ".exe", name] if os.name == "nt" else [name]):
            p = Path(d) / n
            if p.is_file() and os.access(p, os.X_OK) and str(p) not in found:
                found.append(str(p))
    return found


def main():
    print(f"q28 os={OS} release={platform.release()} machine={platform.machine()}")
    print(f"q28 JAVA_HOME={'set' if os.environ.get('JAVA_HOME') else 'unset'}: {tidy(os.environ.get('JAVA_HOME', ''))}")
    # 1. Every java on PATH.
    alls = which_all("java")
    print(f"RESULT q28 which-a-java {OS} : {len(alls)} found: {', '.join(tidy(p) for p in alls)}")
    for p in alls:
        pp = Path(p)
        target = os.path.realpath(p)
        st = pp.stat()
        with open(target, "rb") as f:
            head = f.read(4)
        kind = "script" if head[:2] == b"#!" else ("Mach-O" if head in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xfe\xed\xfa\xcf") else
                ("ELF" if head == b"\x7fELF" else ("PE" if head[:2] == b"MZ" else head.hex())))
        print(f"  {tidy(p)}: symlink={pp.is_symlink()} -> {tidy(target)} size={st.st_size} header={kind}")
        if shutil.which("file"):
            c, o, e = run(["file", "-L", p])
            print("  file -L: " + tidy(o.strip() or e.strip()))
            c, o, e = run(["file", p])
            print("  file: " + tidy(o.strip() or e.strip()))

    # 2. macOS specifics.
    usr = Path("/usr/bin/java")
    if OS == "macos":
        print(f"RESULT q28 usr-bin-java-symlink {OS} : exists={usr.exists()} symlink={usr.is_symlink()}"
              + (f" -> {os.readlink(usr)}" if usr.is_symlink() else ""))
        if usr.exists():
            c, o, e = run(["file", str(usr)])
            print(f"RESULT q28 usr-bin-java-file {OS} : {o.strip()}")
            c, o, e = run(["ls", "-l", str(usr)])
            print("  ls -l: " + o.strip())
            c, o, e = run(["ls", "-l", "/usr/libexec/java_home"])
            print("  ls -l java_home: " + o.strip())
        jh = Path("/usr/libexec/java_home")
        if jh.exists():
            c, o, e = run([str(jh), "-V"])
            show(f"/usr/libexec/java_home -V (exit {c})", o + e)
            c, o, e = run([str(jh)])
            print(f"RESULT q28 java_home-default {OS} : exit={c} {tidy(o.strip() or e.strip())}")
        else:
            print(f"RESULT q28 java_home-default {OS} : /usr/libexec/java_home missing")
        c, o, e = run(["ls", "/Library/Java/JavaVirtualMachines"])
        print("  /Library/Java/JavaVirtualMachines: " + (o.strip().replace("\n", " ") or e.strip()))

    # 3. java.home through each java, with JAVA_HOME as given, unset, and pointed at 11 / 21.
    base = dict(os.environ)
    variants = {"as-given": base}
    nojh = {k: v for k, v in base.items() if k != "JAVA_HOME"}
    variants["JAVA_HOME-unset"] = nojh
    for name in ("JAVA11_HOME", "JAVA21_HOME"):
        if base.get(name):
            variants[f"JAVA_HOME={name}"] = dict(nojh, JAVA_HOME=base[name])
    targets = {}
    if usr.exists():
        targets["/usr/bin/java"] = usr
    if alls:
        targets["first-on-PATH"] = Path(alls[0])
    if base.get("JAVA_HOME"):
        targets["$JAVA_HOME/bin/java"] = Path(base["JAVA_HOME"]) / "bin" / f"java{EXE}"
    for tl, t in targets.items():
        for vl, env in variants.items():
            c, ver, home, text = version_and_home(t, env)
            print(f"RESULT q28 java-home[{tl}][{vl}] {OS} : exit={c} version={ver} java.home={tidy(str(home))}")
            if ver is None:
                show("output", text)

    # 4. macOS: /usr/bin/java with no JDK reachable. Hide every JDK by pointing
    # JAVA_HOME at an empty folder (the stub honours JAVA_HOME) and, separately,
    # at a folder that does not exist. The runner's installed JDKs cannot be
    # removed safely, so "no JDK installed at all" is approximated, not tested.
    if OS == "macos" and usr.exists():
        empty = Path("q28-empty-jdk").resolve()
        empty.mkdir(exist_ok=True)
        for vl, env in {"JAVA_HOME=empty-folder": dict(nojh, JAVA_HOME=str(empty)),
                        "JAVA_HOME=missing-folder": dict(nojh, JAVA_HOME=str(empty / "nope"))}.items():
            c, o, e = run([str(usr), "-version"], env=env, timeout=30)
            print(f"RESULT q28 usr-bin-java-no-jdk[{vl}] {OS} : exit={c}")
            show("stdout", o)
            show("stderr", e)
        # JAVA_VERSION is read by java_home (and so maybe by the stub): ask for a version that is absent.
        env = dict(nojh, JAVA_VERSION="1.6")
        c, ver, home, text = version_and_home(usr, env)
        print(f"RESULT q28 usr-bin-java-JAVA_VERSION=1.6 {OS} : exit={c} version={ver} java.home={tidy(str(home))}")
        if ver is None:
            show("output", text)
        c, o, e = run(["/usr/libexec/java_home", "-v", "1.6"], env=nojh)
        print(f"  java_home -v 1.6: exit={c} {tidy((o + e).strip())}")
        # Real "no JDK registered": only with Q28_ALLOW_SUDO=1 (ephemeral runner).
        # Moves the system JDK folders aside with sudo, asks /usr/bin/java with
        # JAVA_HOME unset, and always moves them back.
        if base.get("Q28_ALLOW_SUDO") == "1":
            dirs = [Path("/Library/Java/JavaVirtualMachines"), Path(HOME) / "Library/Java/JavaVirtualMachines"]
            moved = []
            try:
                for d in dirs:
                    if d.exists():
                        dst = d.with_name(d.name + ".q28-aside")
                        c, o, e = run(["sudo", "-n", "mv", str(d), str(dst)], timeout=30)
                        if c == 0:
                            moved.append((d, dst))
                        else:
                            print(f"  could not move {tidy(str(d))}: {e.strip()}")
                c, o, e = run(["/usr/libexec/java_home", "-V"], env=nojh, timeout=30)
                show(f"java_home -V with JDK folders aside (exit {c})", o + e)
                c, o, e = run([str(usr), "-version"], env=nojh, timeout=30)
                print(f"RESULT q28 usr-bin-java-no-jdk-registered {OS} : exit={c} moved={len(moved)}")
                show("stdout", o)
                show("stderr", e)
            finally:
                for d, dst in moved:
                    run(["sudo", "-n", "mv", str(dst), str(d)], timeout=30)
                print(f"  restored {len(moved)} folder(s)")

    # 5. Run both jars through /usr/bin/java (macOS) and through JAVA11_HOME's java.
    jars = {"v1.7.4": base.get("TLA2TOOLS_174"), "rolling": base.get("TLA2TOOLS_ROLLING")}
    runners = {}
    if base.get("JAVA11_HOME"):
        runners["JAVA11_HOME"] = (Path(base["JAVA11_HOME"]) / "bin" / f"java{EXE}", nojh)
    if OS == "macos" and usr.exists() and base.get("JAVA11_HOME"):
        runners["/usr/bin/java+JAVA_HOME=11"] = (usr, dict(nojh, JAVA_HOME=base["JAVA11_HOME"]))
    work = Path("q28-launcher-work").resolve()
    work.mkdir(exist_ok=True)
    (work / "pass.tla").write_text("---- MODULE pass ----\nEXTENDS Naturals\nVARIABLE x\nInit == x = 0\n"
                                   "Next == x' = (x + 1) % 5\nTypeOK == x \\in 0..4\n====\n")
    (work / "pass.cfg").write_text("INIT Init\nNEXT Next\nINVARIANT TypeOK\n")
    for jl, jar in jars.items():
        if not jar:
            continue
        for rl, (java, env) in runners.items():
            meta = work / f"md-{jl}-{len(rl)}"
            try:
                p = subprocess.run([str(java), "-XX:+UseParallelGC", "-cp", jar, "tlc2.TLC", "-workers", "1",
                                    "-metadir", str(meta), "-config", "pass.cfg", "-tool", "pass.tla"],
                                   cwd=work, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=240)
                out = p.stdout.decode("utf-8", "replace")
                code = p.returncode
            except subprocess.TimeoutExpired:
                out, code = "", "timeout"
            ver = re.search(r"TLC2 Version [^\n]*", out)
            ok = "Model checking completed. No error has been found." in out
            print(f"RESULT q28 tlc-pass-{jl}-{rl} {OS} : exit={code} no-error-found={ok} "
                  f"{ver.group(0) if ver else ''}")
            if not ok:
                show("output", out[-3000:])


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"RESULT q28 java_launcher {OS} : script error {type(e).__name__}: {e}")
    sys.exit(0)
