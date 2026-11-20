#!/bin/bash
# run_bg.sh jar-dir name [tlc args...]: one TLC run, -workers 1, metadir <tmp>/q25/meta/<name>
S=<tmp>/q25
v=$1; n=$2; shift 2
mkdir -p $S/meta/$n $S/run/$n; cd $S/run/$n
date -u +%FT%TZ > $S/logs/$n.start
java -cp <tmp>/jars/$v/tla2tools.jar tlc2.TLC -workers 1 -metadir $S/meta/$n "$@" $S/specs/Long.tla > $S/logs/$n.out 2>&1 &
echo $! > $S/logs/$n.pid
wait $!; echo $? > $S/logs/$n.exit; date -u +%FT%TZ > $S/logs/$n.end
