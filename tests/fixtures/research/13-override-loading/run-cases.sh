#!/usr/bin/env bash
# Usage: run-cases.sh <version-dir> <path-to-tla2tools.jar> [case ...]
# Compiles each case's Java sources against the jar, then runs TLC the way tlaup does:
#   java -XX:+IgnoreUnrecognizedVMOptions -XX:+UseParallelGC -DTLA-Library=<modules> [-Dtlc2.overrides.TLCOverrides=<prop>]
#        -cp <classes>:<modules>:<jar> tlc2.TLC -metadir <dir> -config spec.cfg -tool spec.tla
# Output (stdout+stderr merged) goes to <version-dir>/out/<case>.txt, exit code to <version-dir>/out/<case>.exit
set -u
V="$(cd "$1" && pwd)"; JAR="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"; shift 2
CASES=("$@"); [ ${#CASES[@]} -eq 0 ] && CASES=($(ls "$V/cases"))
mkdir -p "$V/out"
META="$(mktemp -d)"
for c in "${CASES[@]}"; do
  C="$V/cases/$c"; mkdir -p "$C/classes"
  if [ -d "$C/java" ]; then
    javac -cp "$JAR" -d "$C/classes" $(find "$C/java" -name '*.java') > "$V/out/$c.javac.txt" 2>&1
    echo "javac exit $?" >> "$V/out/$c.javac.txt"
  fi
  PROP=()
  if [ -f "$C/noprop" ]; then :; elif [ -f "$C/prop" ]; then PROP=("-Dtlc2.overrides.TLCOverrides=$(cat "$C/prop")")
  else PROP=("-Dtlc2.overrides.TLCOverrides=tlc2.overrides.TLCOverrides"); fi
  CP="$C/classes:$C/modules:$JAR"; [ -f "$C/no_classes" ] && CP="$C/modules:$JAR"
  CMD=(java -XX:+IgnoreUnrecognizedVMOptions -XX:+UseParallelGC "-DTLA-Library=$C/modules" "${PROP[@]}" -cp "$CP" tlc2.TLC -metadir "$META/$c" -config spec.cfg -tool spec.tla)
  echo "cd $C && ${CMD[*]}" > "$V/out/$c.cmd"
  ( cd "$C" && timeout 120 "${CMD[@]}" > "$V/out/$c.txt" 2>&1; echo $? > "$V/out/$c.exit" )
  echo "== $c exit=$(cat "$V/out/$c.exit")"
done
