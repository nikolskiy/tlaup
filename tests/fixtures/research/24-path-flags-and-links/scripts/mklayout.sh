#!/bin/bash
: "${TMP_ROOT:?set TMP_ROOT to the scratch root that holds jars/ and q24/}"
# Builds the test tree under $1 (default ./t). Idempotent.
T=${1:-$PWD/t}; rm -rf "$T"; mkdir -p "$T"; cd "$T"
spec() { # dir marker
cat > "$1/Spec.tla" <<EOS
---- MODULE Spec ----
EXTENDS Naturals, Helper, TLC
CONSTANT N
VARIABLE x
Init == x = 0 /\\ PrintT(<<"N", N, "marker", Marker, "specfile", "$2">>)
Next == x < 3 /\\ x' = x + 1
Spec == Init /\\ [][Next]_x
Inv == x < 2
====
EOS
}
helper() { printf -- '---- MODULE Helper ----\nMarker == "%s"\n====\n' "$2" > "$1/Helper.tla"; }
cfg() { printf 'SPECIFICATION Spec\nINVARIANT Inv\nCONSTANT N = %s\n' "$2" > "$1"; }
mkdir -p real/proj/sub real/other L work
spec real/proj spec-real; helper real/proj helper-real-proj
cfg real/proj/Spec.cfg 1; cfg real/proj/sub/a.cfg 2
cfg real/out.cfg 4                     # reached from real/proj with ..
cfg real/other/o.cfg 5
# decoys lexically reached: L/out.cfg, L/Helper.tla (beside the link path)
cfg L/out.cfg 44; helper L helper-beside-link-parent
# link to folder
ln -s ../real/proj L/lnk
# link to the file itself
mkdir -p Lf; ln -s ../real/proj/Spec.tla Lf/Spec.tla; helper Lf helper-beside-file-link; cfg Lf/Spec.cfg 77
# link to folder whose target is deeper elsewhere
mkdir -p deep/a/b L2; cp real/proj/Spec.tla real/proj/Helper.tla deep/a/b/; cfg deep/a/b/Spec.cfg 11; cfg deep/a/out.cfg 12; cfg deep/out.cfg 13; cfg L2/out.cfg 99
ln -s ../deep/a/b L2/lnk
# cwd decoys
helper work helper-in-cwd; cfg work/out.cfg 55
mkdir -p outside; cfg outside/o.cfg 6
