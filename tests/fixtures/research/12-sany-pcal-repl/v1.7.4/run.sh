#!/bin/bash
# usage: run.sh <version> <label> <cmd args after java -cp jar> ; runs in work dir, records cmd, output, rc
v=$1; label=$2; shift 2
cd $S/work-$v
{ echo "\$ java -cp tla2tools.jar $*"; java -cp $S/jar-$v/tla2tools.jar "$@" 2>&1 </dev/null; echo "[exit=$?]"; } > $S/out-$v/$label.txt
cat $S/out-$v/$label.txt
