import subprocess, signal, sys, os, time
# usage: sigrun.py ver spec metadir log signal delay [tlc args]
S="<tmp>/q17"
v, sp, m, log, sig, delay = sys.argv[1:7]; extra = sys.argv[7:]
os.makedirs(m, exist_ok=True)
p = subprocess.Popen(["java","-cp",f"{S}/j/{v}/tla2tools.jar","tlc2.TLC","-workers","1","-metadir",m,*extra,f"{S}/specs/{sp}.tla"],
    cwd=f"{S}/run", stdout=open(log,"w"), stderr=subprocess.STDOUT, preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_DFL))
open(log+".pid","w").write(str(p.pid))
time.sleep(float(delay)); p.send_signal(getattr(signal, sig))
rc = p.wait(); open(log+".exit","w").write(str(rc))
