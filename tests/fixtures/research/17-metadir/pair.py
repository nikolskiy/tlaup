import subprocess, sys, os, shutil, collections
S="<tmp>/q17"
v, n, hold = sys.argv[1], int(sys.argv[2]), sys.argv[3]   # hold = spec name
extra = sys.argv[4:]
res = collections.Counter(); names=[]
m = f"{S}/out/pair_{v}"
for i in range(n):
    shutil.rmtree(m, ignore_errors=True); os.makedirs(m)
    ps = [subprocess.Popen(["java","-cp",f"{S}/j/{v}/tla2tools.jar","-Xshare:auto","tlc2.TLC",*extra,"-nowarning","-workers","1","-metadir",m,f"{S}/specs/{hold}.tla"],
          cwd=f"{S}/run", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) for _ in range(2)]
    outs = [p.communicate()[0] for p in ps]
    rcs = tuple(p.returncode for p in ps)
    res[rcs]+=1
    for o in outs:
        for l in o.splitlines():
            if l.startswith("Error") and "xists" in l or "METADIR" in l or "already" in l: names.append(l[:200])
    # record runtime dir names seen (use a log of leftover dirs)
print(dict(res)); print(collections.Counter(names))
