#!/bin/bash
# watch.sh: every 20 s, append a listing of every metadir to logs/<name>.tree: relative path, size, modification time.
# The header time is UTC (date -u); the copies under trees/ were converted to the clock of the file times.
S=<tmp>/q25
while true; do
  for d in $S/meta/*/; do n=$(basename $d)
    { echo "== $(date -u +%T)"; (cd $d && find . -type f -printf '%P %s %TT\n' | sort); } >> $S/logs/$n.tree
  done
  [ -e $S/stopwatch ] && exit 0
  sleep 20
done
