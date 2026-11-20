#!/usr/bin/env python3
"""Merge the main and extra captures into one table. Usage: merge.py <v174|v180> <main-dir> <extra-dir>"""
import sys, pathlib, re, subprocess
ver, main, extra = sys.argv[1], pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
EXPSRC = {'v180': 'café 日本語 😀', 'v174': 'café 日語文'}[ver]
def lab(b, e):
    if b is None: return '-'
    if b == e.encode('utf-8'): return 'UTF8'
    if b == e.encode('ascii', 'replace'): return 'ASCII?'
    if b == b'?' * len(e.encode('utf-8')): return 'BYTE?'
    if b == '�'.encode() * len(e.encode('utf-8')): return 'FFFD/byte'
    try:
        if b == e.encode('latin-1'): return 'L1'
    except UnicodeEncodeError: pass
    return 'other:' + b.hex()
def rd(p): return p.read_bytes() if p.exists() else None
out = subprocess.run([sys.executable, str(pathlib.Path(__file__).parent / 'summarize.py'), str(main), ver], capture_output=True, text=True).stdout.splitlines()
for line in out:
    c = line.split()[0]
    sb = rd(extra / f'{c}-sanybad2.out')
    m = re.search(rb'Encountered "\\?"(.*?)\\?"" at line', sb or b'', re.S)
    # message looks like: Encountered ""café 日本語 😀"" ... (outer quotes + string quotes)
    m = re.search(rb'Encountered ""(.*?)"" at line', sb or b'', re.S)
    lex = re.search(rb'Lexical error[^\n]*', sb or b'')
    s = '-' if not m else lab(m.group(1), EXPSRC)
    if not m and lex: s = 'LEXERR(' + ('ascii-escaped' if lex.group(0).isascii() else 'nonascii') + ')'
    a = rd(extra / f'{c}-pcalok.tla.after')
    src = rd(pathlib.Path(sys.argv[2]).parent.parent.parent / ('spec-bmp' if ver == 'v174' else 'spec') / 'EncPcalOk.tla')
    po = '-' if a is None else ('comments-intact' if a.split(b'\n')[0:2] == src.split(b'\n')[0:2] and all(l in a for l in [x for x in src.split(b'\n') if b'caf' in x]) else 'COMMENTS-CHANGED')
    print(line, 'sanyquote=' + s, 'pcalfile=' + po)
