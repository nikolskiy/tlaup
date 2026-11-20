#!/bin/bash
: "${TMP_ROOT:?set TMP_ROOT to the scratch root that holds jars/ and q24/}"
# usage: run.sh <174|180> <cwd under $T> <tlc args...>   env: NOMETA=1 (no -metadir), JAVA=<java>
Q=$TMP_ROOT/q24; T=$Q/t
v=$1; cwd=$2; shift 2
case $v in 174) J=$TMP_ROOT/jars/v1.7.4/tla2tools.jar;; 180) J=$TMP_ROOT/jars/rolling/tla2tools.jar;; esac
M=$Q/meta/$$-$RANDOM; mkdir -p $M; MD="-metadir $M"; [ -n "$NOMETA" ] && MD=""
cd "$T/$cwd" && timeout 60 ${JAVA:-java} -XX:+UseParallelGC -cp $J tlc2.TLC -nowarning -workers 1 $MD "$@" 2>&1 | grep -E '^<<"N"|File not found|rror|exception|Exception|exit|Invariant|violated|Unknown|cannot|Cannot|No such' | head -8
echo "exit=${PIPESTATUS[0]}"
