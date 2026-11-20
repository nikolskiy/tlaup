#!/bin/bash
# stderr + file-name experiment, rolling jar and v1.7.4. usage: fn.sh <v174|v180> <java> <locale> <optname>
T=${TMP:?set TMP to the scratch root};  Q=$TMP/q21
declare -A JARS=( [174]=$T/jars/v1.7.4/tla2tools.jar [180]=$T/jars/rolling/tla2tools.jar )
declare -A JAVAS=( [11]=$T/jdk11/jdk-11.0.33+10/bin/java [21]=/usr/lib/jvm/java-21-openjdk-amd64/bin/java [25]=java )
declare -A OPTS=( [none]="" [all]="-Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8" [jnu]="-Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8 -Dsun.jnu.encoding=UTF-8" [stderr]="-Dstderr.encoding=UTF-8" [sunerr]="-Dsun.stderr.encoding=UTF-8" )
declare -A LOCS=( [C]=C [Cutf8]=C.utf8 )
v=$1; J=${JAVAS[$2]}; L=${LOCS[$3]}; O=${OPTS[$4]}; JAR=${JARS[$v]}; p=v$v-j$2-$3-$4
cd $Q/fn
env -i PATH="$PATH" HOME="$HOME" LC_ALL=$L timeout 120 $J $O -cp $JAR tla2sany.SANY café日.tla >$Q/out/fn/$p-sanymissing.out 2>$Q/out/fn/$p-sanymissing.err; echo $? > $Q/out/fn/$p-sanymissing.rc
env -i PATH="$PATH" HOME="$HOME" LC_ALL=$L timeout 120 $J $O -cp $JAR tlc2.TLC -metadir $Q/work/fn-$p -config "$Q/fn/dé日/Enc.cfg" "$Q/fn/dé日/Enc.tla" >$Q/out/fn/$p-tlcpath.out 2>$Q/out/fn/$p-tlcpath.err; echo $? > $Q/out/fn/$p-tlcpath.rc
rm -rf $Q/work/fn-$p
