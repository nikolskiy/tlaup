"""Read META-INF/MANIFEST.MF of each tla2tools.jar; print JSON lines. Usage: read_manifests.py JARS_DIR"""
import hashlib, json, sys, zipfile
from pathlib import Path

def parse(text):
    lines = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        if raw.startswith(" ") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    out = {}
    for l in lines:
        if ": " in l:
            k, v = l.split(": ", 1)
            out[k] = v
        elif l.endswith(":"):
            out[l[:-1]] = ""
    return out

for d in sorted(Path(sys.argv[1]).iterdir()):
    jar = d / "tla2tools.jar"
    z = zipfile.ZipFile(jar)
    raw = z.read("META-INF/MANIFEST.MF").decode()
    (Path(sys.argv[2]) / f"{d.name}.MANIFEST.MF").write_bytes(raw.encode())
    print(json.dumps({"tag": d.name, "sha256": hashlib.sha256(jar.read_bytes()).hexdigest(),
                      "size": jar.stat().st_size, "manifest": parse(raw)}))
