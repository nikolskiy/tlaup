"""Histogram of class-file major versions in a jar (55 = Java 11).

Usage: python -I class-versions.py <jar>...
Prints the Multi-Release manifest attribute, the count of classes per major
version (split by top-level package), and the newest classes found.
"""
import collections
import struct
import sys
import zipfile

for jar in sys.argv[1:]:
    with zipfile.ZipFile(jar) as z:
        mf = z.read("META-INF/MANIFEST.MF").decode("utf-8", "replace")
        mr = [l for l in mf.splitlines() if l.lower().startswith("multi-release")]
        print(f"== {jar.rsplit('/', 2)[-2]}  Multi-Release attribute: {mr or 'absent'}")
        hist = collections.Counter()
        by_pkg = collections.defaultdict(collections.Counter)
        newest = []
        for info in z.infolist():
            if not info.filename.endswith(".class"):
                continue
            head = z.open(info).read(8)
            if head[:4] != b"\xca\xfe\xba\xbe":
                continue
            minor, major = struct.unpack(">HH", head[4:8])
            hist[major] += 1
            pkg = info.filename.split("/")[0]
            if info.filename.startswith("META-INF/versions/"):
                pkg = "/".join(info.filename.split("/")[:3])
            by_pkg[pkg][major] += 1
            newest.append((major, info.filename))
        print("  classes per major version:", dict(sorted(hist.items())))
        for pkg, c in sorted(by_pkg.items()):
            print(f"    {pkg:30} {dict(sorted(c.items()))}")
        top = max(hist)
        hits = [n for m, n in newest if m == top]
        print(f"  newest major {top}: {len(hits)} classes, e.g. {hits[:5]}")
