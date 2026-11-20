"""Per-env verdict against the reference (typer 0.29.1 + rich 13.9.4), on the deterministic checks only.
Racy checks (a short output into `| head -1`: the writer may finish before the reader leaves) are listed apart.
python3 verdict.py <out-dir>"""
import glob, json, os, sys
OUT = sys.argv[1]; REF = "t0.29.1-r13.9.4"
def L(n, f): return json.load(open(os.path.join(OUT, n, f)))
RACY = lambda k: (k.startswith("bash:") and "200000" not in k)
def det(n):
    i, p, c = L(n, "inproc.json"), L(n, "proc.json"), L(n, "comp.json")
    s = {}
    for k, v in i["runner"].items():
        if k != "prompt": s["runner: " + k] = v["code"]
    for k, v in p["f10"].items():
        if not RACY(k): s["proc f10: " + k] = (v["code"], v["traceback"])
    for k, v in c.items():
        if k not in ("inner", "bash without completion_init()"): s["comp: " + k] = (v["code"], v["stdout"], v["stderr"])
    inn = c["inner"]
    s["modules"] = json.dumps({k: v for k, v in inn.items() if k.startswith("typer.")}, sort_keys=True)
    s["scripts"] = json.dumps(inn["scripts"], sort_keys=True); s["sig"] = (inn["get_completion_script_signature"], inn["completion_init_signature"])
    return s
ref = det(REF)
names = sorted((os.path.basename(p) for p in glob.glob(OUT + "/t*")), key=lambda n: ([int(x) for x in n[1:].split("-r")[0].split(".")], n))
for n in names:
    s = det(n); diff = {k: (ref.get(k), s.get(k)) for k in set(ref) | set(s) if ref.get(k) != s.get(k)}
    p = L(n, "proc.json"); racy_bad = [k for m in ("f10",) for k, v in p[m].items() if RACY(k) and v["code"] not in (141, 2, 0)]
    print(f"{n:34} deterministic differences: {len(diff)} {json.dumps(diff)[:400] if diff else ''}")
