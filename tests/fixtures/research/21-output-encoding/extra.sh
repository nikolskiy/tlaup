#!/bin/bash
# Extra runs per cell: SANY parse error quoting a non-ASCII string token; PlusCal translation of a spec with non-ASCII only in comments.
# usage: extra.sh <v> <j> <l> <o>   (env SPEC, OUT)
T=${TMP:?set TMP to the scratch root};  W=$TMP/q21/work
declare -A JARS=( [174]=$T/jars/v1.7.4/tla2tools.jar [180]=$T/jars/rolling/tla2tools.jar )
declare -A JAVAS=( [11]=$T/jdk11/jdk-11.0.33+10/bin/java [21]=/usr/lib/jvm/java-21-openjdk-amd64/bin/java [25]=java )
declare -A OPTS=( [none]="" [fileenc]="-Dfile.encoding=UTF-8"
  [stdout]="-Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8"
  [sunstdout]="-Dsun.stdout.encoding=UTF-8 -Dsun.stderr.encoding=UTF-8"
  [all]="-Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8 -Dsun.stdout.encoding=UTF-8 -Dsun.stderr.encoding=UTF-8"
  [latin1]="-Dfile.encoding=ISO-8859-1" [minimal]="-Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8" )
declare -A LOCS=( [C]=C [POSIX]=POSIX [Cutf8]=C.utf8 [enUS]=en_US.utf8 )
v=$1; j=$2; l=$3; o=$4
LOC=${LOCS[$l]}; J=${JAVAS[$j]}; JAR=${JARS[$v]}; O=${OPTS[$o]}; p="v$v-j$j-$l-$o"
mkdir -p "$OUT" $W/x-$p; cp $SPEC/EncPcalOk.tla $W/x-$p/
( cd "$SPEC"; env -i PATH="$PATH" HOME="$HOME" LC_ALL="$LOC" timeout 180 $J $O -cp $JAR tla2sany.SANY EncBad2.tla >"$OUT/$p-sanybad2.out" 2>"$OUT/$p-sanybad2.err"; echo $? >"$OUT/$p-sanybad2.rc" )
( cd $W/x-$p; env -i PATH="$PATH" HOME="$HOME" LC_ALL="$LOC" timeout 180 $J $O -cp $JAR pcal.trans EncPcalOk.tla >"$OUT/$p-pcalok.out" 2>"$OUT/$p-pcalok.err"; echo $? >"$OUT/$p-pcalok.rc"; cp EncPcalOk.tla "$OUT/$p-pcalok.tla.after"; ls >"$OUT/$p-pcalok.ls" )
rm -rf $W/x-$p
