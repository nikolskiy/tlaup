#!/bin/bash
# One matrix cell: cell.sh <v174|v180> <11|21|25> <locale-name> <opt-name> <extra:0|1>
# Environment: SPEC (spec folder), OUT (capture folder). Raw stdout and stderr go to separate files.
T=${TMP:?set TMP to the scratch root};  W=$TMP/q21/work
declare -A JARS=( [174]=$T/jars/v1.7.4/tla2tools.jar [180]=$T/jars/rolling/tla2tools.jar )
declare -A JAVAS=( [11]=$T/jdk11/jdk-11.0.33+10/bin/java [21]=/usr/lib/jvm/java-21-openjdk-amd64/bin/java [25]=java )
declare -A OPTS=( [none]="" [fileenc]="-Dfile.encoding=UTF-8"
  [stdout]="-Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8"
  [sunstdout]="-Dsun.stdout.encoding=UTF-8 -Dsun.stderr.encoding=UTF-8"
  [all]="-Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8 -Dsun.stdout.encoding=UTF-8 -Dsun.stderr.encoding=UTF-8"
  [latin1]="-Dfile.encoding=ISO-8859-1" [minimal]="-Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8" )
declare -A LOCS=( [C]=C [POSIX]=POSIX [Cutf8]=C.utf8 [enUS]=en_US.utf8 )
v=$1; j=$2; l=$3; o=$4; extra=$5
LOC=${LOCS[$l]}; J=${JAVAS[$j]}; JAR=${JARS[$v]}; O=${OPTS[$o]}
p="v$v-j$j-$l-$o"
mkdir -p "$OUT"
run() { name=$1; shift; ( cd "$SPEC"; env -i PATH="$PATH" HOME="$HOME" LC_ALL="$LOC" timeout 180 "$@" >"$OUT/$p-$name.out" 2>"$OUT/$p-$name.err"; echo $? >"$OUT/$p-$name.rc" ); }
run tlc      $J $O -cp $JAR tlc2.TLC -metadir $W/m-$p -config Enc.cfg Enc.tla
run tlcprint $J $O -cp $JAR tlc2.TLC -metadir $W/m-$p -config EncPrint.cfg EncPrint.tla
run sanybad  $J $O -cp $JAR tla2sany.SANY EncBad.tla
if [ "$extra" = 1 ]; then
  run tlctool $J $O -cp $JAR tlc2.TLC -tool -metadir $W/m-$p -config Enc.cfg Enc.tla
  run sanysem $J $O -cp $JAR tla2sany.SANY EncSem.tla
fi
for f in EncPcal EncPcalBad; do
  mkdir -p $W/pc-$p-$f; cp $SPEC/$f.tla $W/pc-$p-$f/
  ( cd $W/pc-$p-$f; env -i PATH="$PATH" HOME="$HOME" LC_ALL="$LOC" timeout 180 $J $O -cp $JAR pcal.trans $f.tla >"$OUT/$p-pcal-$f.out" 2>"$OUT/$p-pcal-$f.err"; echo $? >"$OUT/$p-pcal-$f.rc"; cp $f.tla "$OUT/$p-pcal-$f.tla.after" )
done
rm -rf $W/m-$p $W/pc-$p-*
