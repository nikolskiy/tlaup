#!/usr/bin/env python3
"""Hexdump the relevant raw lines for chosen cells. Usage: excerpts.py <captures-root> <cell>...
<captures-root> holds v174b/ v174x/ v180/ v180x/ ; a cell is e.g. v180-j25-C-none."""
import sys, pathlib, re
root = pathlib.Path(sys.argv[1])
def find(cell, kind):
    v = cell.split('-')[0]
    main, extra = ('v174b', 'v174x') if v == 'v174' else ('v180', 'v180x')
    return root / (extra if kind in ('sanybad2', 'pcalok') else main) / f'{cell}-{kind}'
def lines(p, ext, pat):
    f = pathlib.Path(str(p) + ext)
    if not f.exists(): return []
    return [l for l in f.read_bytes().split(b'\n') if re.search(pat, l)]
def hx(b): return ' '.join(f'{x:02x}' for x in b)
for cell in sys.argv[2:]:
    print('###', cell)
    for kind, ext, pat, title in [
        ('tlc', '.out', rb'^(/\\ )?s = ', 'TLC error trace values'),
        ('tlcprint', '.out', rb'^"?printt?: ', 'Print / PrintT'),
        ('sanybad2', '.out', rb'^Encountered', 'SANY parse error quoting a string token'),
        ('pcal-EncPcal', '.out', rb'Illegal character', 'PlusCal message quoting a string')]:
        for l in lines(find(cell, kind), ext, pat)[:3]:
            print(f'  [{title}] {l.decode("utf-8", "replace")!r}')
            print(f'      {hx(l)}')
