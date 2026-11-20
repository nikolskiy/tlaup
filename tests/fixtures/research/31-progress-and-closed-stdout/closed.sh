#!/bin/bash
# usage: closed.sh NAME JAR MODE EXTRA...   MODE: head | reader | closed-out | closed-err | full-err | tool-head
# Starts TLC with its stdout (or stderr) consumer gone and watches the java pid until it exits.
name=$1; jar=$2; mode=$3; shift 3
d=run-$name; rm -rf "$d"; mkdir "$d"; cp Mid.tla Mid.cfg "$d"; cd "$d"
J="exec java -Xmx250m -XX:+UseParallelGC -jar ../$jar -workers 1 -metadir ./states -nowarning $* Mid"
start=$(date +%s)
case $mode in
  head)       { bash -c "echo \$\$ > pid; $J"; echo "exit=$?" > rc; } | head -1 > first.txt ;;
  reader)     { bash -c "echo \$\$ > pid; $J"; echo "exit=$?" > rc; } | python3 -c 'import sys; sys.stdout.write(sys.stdin.readline())' > first.txt ;;
  closed-out) { bash -c "echo \$\$ > pid; $J"; echo "exit=$?" > rc; } >&- ;;
  closed-err) { bash -c "echo \$\$ > pid; $J" > out.txt; echo "exit=$?" > rc; } 2>&- ;;
  full-err)   { bash -c "echo \$\$ > pid; $J" > out.txt; echo "exit=$?" > rc; } 2>/dev/full ;;
esac &
sleep 2
pid=$(cat pid)
echo "# $name mode=$mode pid=$pid first-line-seen: $(cat first.txt 2>/dev/null | head -c 100)"
echo "# fd listing at +2s:"; ls -l /proc/$pid/fd 2>&1 | awk '$9<=2 {print "#   " $9 " -> " $11}'
while kill -0 $pid 2>/dev/null; do
  t=$(( $(date +%s) - start )); st=$(awk '{print $3, $14+$15}' /proc/$pid/stat 2>/dev/null)
  echo "t=${t}s alive state/cpu-ticks=$st"; sleep 10
done
t=$(( $(date +%s) - start ))
sleep 1
echo "t=${t}s java gone; $(cat rc 2>/dev/null)"
[ -f out.txt ] && { echo "# out.txt lines: $(wc -l < out.txt); last:"; tail -2 out.txt; }
