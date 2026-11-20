#!/bin/bash
# workers auto under taskset and a cgroup CPU quota
T=<tmp>
cd $T/q19/specs
for jl in v1.7.4 rolling; do
 for jv in java $T/jdk11/jdk-11.0.33+10/bin/java; do
  echo "--- $jl $($jv -version 2>&1|head -1) taskset -c 0-2 (nproc=$(taskset -c 0-2 nproc))"
  taskset -c 0-2 $jv -cp $T/jars/$jl/tla2tools.jar tlc2.TLC -workers auto -metadir $T/q19/meta W 2>&1 | grep -o "with [0-9]* workers\? on [0-9]* cores"
  echo "--- $jl taskset -c 5 (nproc=1)"
  taskset -c 5 $jv -cp $T/jars/$jl/tla2tools.jar tlc2.TLC -workers auto -metadir $T/q19/meta W 2>&1 | grep -o "with [0-9]* workers\? on [0-9]* cores"
 done
done
