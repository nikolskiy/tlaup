#!/usr/bin/env python3
"""Check that a -difftrace trace, with every variable that is missing from a state carried forward from the previous
state, equals the trace of the same run without -difftrace (headers and values, for each state).
usage: python3 verify_difftrace.py   (run in this folder; reads <version>/<case>.out)"""
import re, sys

def states(path):
    txt = open(path).read()
    out = []
    for m in re.finditer(r"@!@!@STARTMSG (2217|2216):4 @!@!@\n(.*?)\n@!@!@ENDMSG \1 @!@!@", txt, re.S):
        body = m.group(2).split("\n")
        head, rest = body[0], body[1:]
        vs, cur = {}, None
        if any(l.startswith("/\\ ") for l in rest):
            for l in rest:
                mm = re.match(r"/\\ (\w+) = (.*)$", l)
                if mm:
                    cur = mm.group(1); vs[cur] = [mm.group(2)]
                elif cur:
                    vs[cur].append(l)
        else:
            mm = re.match(r"(\w+) = (.*)$", rest[0]); cur = mm.group(1); vs[cur] = [mm.group(2)] + rest[1:]
        out.append((head, {k: "\n".join(v).rstrip() for k, v in vs.items()}))
    return out

def carry(sts):
    full, prev = [], {}
    for h, v in sts:
        prev = {**prev, **v}
        full.append((h, dict(prev)))
    return full

pairs = [("difftrace-violation", "difftrace-violation-nodiff"), ("difftrace-liveness", "difftrace-liveness-nodiff"),
         ("params-violation-difftrace", "params-violation"), ("alias-violation-difftrace", "alias-violation"),
         ("difftrace-q1-violation", "q01-violation")]
for v in ("v1.7.4", "v1.8.0"):
    for d, n in pairs:
        try:
            a, b = states(f"{v}/{d}.out"), states(f"{v}/{n}.out")
        except FileNotFoundError:
            continue
        if not a or not b:
            print(v, d, "no states (no ALIAS support or no trace)"); continue
        partial = sum(1 for (_, x), (_, y) in zip(a, b) if x != y)
        same = carry(a) == b
        print(v, d, "states", len(a), "vs", len(b), "partial states:", partial, "carry-forward equals full trace:", same)
