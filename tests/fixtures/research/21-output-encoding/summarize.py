#!/usr/bin/env python3
"""Summarise how non-ASCII text came out in each capture.
Usage: summarize.py <capture-dir> <version-prefix: v174|v180>
For every cell prints one row; each column is a label for the bytes found:
  UTF8   bytes equal the UTF-8 encoding of what the spec holds
  ASCII? every character became one '?' (Java's encoder replacement for an unmappable character)
  BYTE?  every UTF-8 *byte* became '?' (input decoded with a charset that has no mapping)
  L1     Latin-1 bytes (e9 for e-acute)
  -      the line was not in the output
  other  raw hex"""
import sys, pathlib, re
d = pathlib.Path(sys.argv[1]); ver = sys.argv[2]
EXP = {'v180': ['café', '日本語', '😀'], 'v174': ['café', '日語文', 'ø']}[ver]
SRC_Q = {'v180': 'café 日本語 😀', 'v174': 'café 日語文'}[ver]

def lab(b, e):
    if b is None: return '-'
    if b == e.encode('utf-8'): return 'UTF8'
    if b == e.encode('ascii', 'replace'): return 'ASCII?'
    if b == b'?' * len(e.encode('utf-8')) and not e.isascii(): return 'BYTE?'
    try:
        if b == e.encode('latin-1'): return 'L1'
    except UnicodeEncodeError: pass
    if b == e.encode('latin-1', 'replace'): return 'L1?'
    return 'other:' + b.hex()

def get(name, ext='.out'):
    p = d / (name + ext)
    return p.read_bytes() if p.exists() else None

def tlc_values(b):
    if b is None: return None
    return re.findall(rb'(?m)^(?:/\\ )?s = "(.*)"\r?$', b)

rows = []
cells = sorted({re.match(r'(v\d+-j\d+-\w+-\w+)-', p.name).group(1) for p in d.glob('*.rc')})
for c in cells:
    r = {}
    for tool in ('tlc', 'tlctool'):
        vals = tlc_values(get(f'{c}-{tool}'))
        r[tool] = '-' if not vals else '/'.join(lab(v, e) for v, e in zip(vals, EXP))
    pb = get(f'{c}-tlcprint')
    m = re.findall(rb'(?m)^"?printt?: ([^"\n]*)', pb or b'')
    r['print'] = '-' if not m else lab(m[0], SRC_Q)
    sb = get(f'{c}-sanybad2', '.out') if (d / f'{c}-sanybad2.out').exists() else None
    if sb is not None:
        m = re.search(rb'Encountered "\\?"?(.*?)\\?""? at line', sb)
        r['sany'] = '-' if not m else lab(m.group(1), SRC_Q)
    pc = get(f'{c}-pcal-EncPcal')
    m = re.search(rb"in string `(.*)' found", pc or b'')
    r['pcal-msg'] = '-' if not m else lab(m.group(1), 'café')
    rows.append((c, r))
for c, r in rows:
    print(c.ljust(26), ' '.join(f'{k}={v}' for k, v in r.items()))
