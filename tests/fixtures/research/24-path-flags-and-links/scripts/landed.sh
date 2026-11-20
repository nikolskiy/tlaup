#!/bin/bash
: "${TMP_ROOT:?set TMP_ROOT to the scratch root that holds jars/ and q24/}"
# usage: landed.sh <ver> <cwd> <tlc args...>  : runs TLC, prints the TLC summary lines and every file or folder created under $T
Q=$TMP_ROOT/q24; T=$Q/t
touch $Q/stamp; sleep 1.1
OUT=$("$Q/run.sh" "$@")
echo "$OUT" | sed 's/^/    /'
echo "    NEW FILES (relative to T):"
(cd $T; find . -newer $Q/stamp \( -type f -o -type d \) | sed 's|^\./||' | sort | sed 's/^/      /')
