"""condense.py TREE: print only the listings of a watch.sh log that differ from the one before, ignoring changes to the growing trace file <Spec>-0.st (time header kept). The header is in UTC here; the copies in the repository were converted to the clock of the file times.."""
import sys
prev, cur, head = None, [], None
def flush():
    global prev
    key = [l for l in cur if "-0.st " not in l]
    if head is not None and key != prev:
        print(head); print("\n".join(cur)); prev = key
for line in open(sys.argv[1]):
    line = line.rstrip("\n")
    if line.startswith("=="):
        flush(); head, cur = line + " UTC", []
    else:
        cur.append(line)
flush()
