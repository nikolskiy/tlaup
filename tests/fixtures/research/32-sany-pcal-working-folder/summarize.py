import re,sys
from pathlib import Path
d=Path(sys.argv[1])
for f in sorted((d/"sany").glob("*.A.txt")):
    name=f.name[:-6]
    row=[]
    for m in "ABC":
        t=(d/"sany"/f"{name}.{m}.txt").read_text()
        helper=re.findall(r"Parsing file (\S*(?:Helper|Main)\.tla)",t)
        h=[x.replace("<w>/","") for x in helper if "Helper" in x]
        ex=re.search(r"--- run 1 exit (\d+)",t).group(1)
        row.append(f"{m}: helper={h[0] if h else '-'} exit={ex}")
    print(f"{name:45s} "+" | ".join(row))
