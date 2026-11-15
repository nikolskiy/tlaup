#!/bin/bash
# run_bg.sh ver spec metadir logfile [tlc args...] ; writes <logfile>.exit; java pid in <logfile>.pid
S=<tmp>/q17
v=$1; sp=$2; m=$3; log=$4; shift 4
cd ${CWD:-$S/run}
java -cp $S/j/$v/tla2tools.jar tlc2.TLC -workers ${W:-2} -metadir $m "$@" $S/specs/$sp.tla > $log 2>&1 &
echo $! > $log.pid
wait $!; echo $? > $log.exit
