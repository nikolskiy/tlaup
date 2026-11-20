"""Scan every Typer wheel from 0.22.0 to the newest for the names tlaup relies on (no install). Prints a table."""
import io, json, re, sys, urllib.request, zipfile
d = json.load(urllib.request.urlopen("https://pypi.org/pypi/typer/json"))
def key(v): return tuple(int(x) for x in re.findall(r"\d+", v)[:3])
vs = sorted((v for v in d["releases"] if re.fullmatch(r"\d+\.\d+\.\d+", v) and key(v) >= (0, 22, 0)), key=key)
print("version | requires click | bundled typer/_click | typer.TyperException public | _completion_classes | _completion_shared | completion_init in _completion_classes | get_completion_script in _completion_shared | requires python")
for v in vs:
    f = [x for x in d["releases"][v] if x["filename"].endswith(".whl")][0]
    z = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(f["url"]).read()))
    names = z.namelist()
    meta = z.read([n for n in names if n.endswith("METADATA")][0]).decode()
    click = bool(re.search(r"^Requires-Dist: click", meta, re.M))
    init = z.read("typer/__init__.py").decode()
    te = "TyperException" in init
    cc = "typer/_completion_classes.py" in names
    cs = "typer/_completion_shared.py" in names
    ci = cc and "def completion_init" in z.read("typer/_completion_classes.py").decode()
    gs = cs and "def get_completion_script" in z.read("typer/_completion_shared.py").decode()
    print(f"{v} | {click} | {any(n.startswith('typer/_click/') for n in names)} | {te} | {cc} | {cs} | {ci} | {gs} | {f.get('requires_python')}")
