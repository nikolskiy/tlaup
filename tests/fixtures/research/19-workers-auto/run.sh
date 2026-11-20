#!/bin/bash
# usage: run.sh <jarlabel> <javalabel> <outfile>; runs the matrix, appends to outfile
T=<tmp>
declare -A JAR=([v174]=$T/jars/v1.7.4/tla2tools.jar [roll]=$T/jars/rolling/tla2tools.jar)
declare -A JAVA=([j25]=java [j21]=/usr/lib/jvm/java-21-openjdk-amd64/bin/java [j11]=$T/jdk11/jdk-11.0.33+10/bin/java)
cd $T/q19/specs
for jl in v174 roll; do for jv in "$@"; do
 echo "##### jar=$jl java=$jv: $(${JAVA[$jv]} -version 2>&1 | head -1)"
 for w in "auto" "AUTO" " auto " "1" "4" "0" "-1" "x" "2.5" "+3" ""; do
  for tool in "" "-tool"; do
   echo "=== workers='$w' tool='$tool'"
   timeout 120 ${JAVA[$jv]} -XX:+UseParallelGC -cp ${JAR[$jl]} tlc2.TLC $tool -workers "$w" -metadir $T/q19/meta -nowarning W 2>&1 | head -12
   echo "exit=${PIPESTATUS[0]}"
  done
 done
 echo "=== -workers missing value"
 ${JAVA[$jv]} -cp ${JAR[$jl]} tlc2.TLC W -workers 2>&1 | head -8; echo "exit=${PIPESTATUS[0]}"
done; done
