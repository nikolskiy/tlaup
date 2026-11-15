#!/bin/bash
# usage: run_matrix.sh JAR OUTDIR   (runs each spec with plain `java -cp JAR tlc2.TLC`, records $?)
JAR=$1; OUT=$2; mkdir -p "$OUT"; cd "$(dirname "$0")/specs"
M=$(mktemp -d)
run() { name=$1; shift
  timeout 120 java "${JVMOPTS[@]}" -cp "$JAR" tlc2.TLC -metadir "$M/$name" "$@" > "$OUT/$name.out" 2>&1
  echo "$name | $* | exit=$?"; }
JVMOPTS=()
for s in Ok Inv Live Act Dead Asrt Assum Parse Sem NoCfg BadCfg CfgSyn Eval NextEval; do run $s $s.tla; done
run Ok_tool -tool Ok.tla
run Inv_tool -tool Inv.tla
run Parse_tool -tool Parse.tla
run BadFlag -bogus Ok.tla
run NoSpecFile NoSuchFile.tla
run NoArgs
run Help -help
run Version -version
run Cfg_missing -config nope.cfg Ok.tla
run Workers_bad -workers abc Ok.tla
JVMOPTS=(-Xmx64m)
run Oom_Xmx64m Oom.tla
rm -f "$(dirname "$0")"/specs/*_TTrace_*   # rolling build writes trace specs next to the spec
