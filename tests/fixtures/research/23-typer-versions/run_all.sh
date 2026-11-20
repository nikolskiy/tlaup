#!/usr/bin/env bash
# Usage: run_all.sh <work-dir>   (needs uv and python3.13; run from anywhere)
# Builds one uv environment per (typer, rich) pair and runs the four probes in each.
set -u
W=$(cd "$1" && pwd); FX=$(cd "$(dirname "$0")" && pwd)
PAIRS="0.22.0:13.7.0 0.22.0:13.9.4 0.23.2:13.7.0 0.23.2:13.9.4 0.24.2:13.7.0 0.24.2:13.9.4
0.25.1:13.8.0 0.25.1:13.9.4 0.26.0:13.8.0 0.26.0:13.9.4 0.26.8:13.8.0 0.26.8:13.9.4 0.27.1:13.8.0 0.27.1:13.9.4 0.27.2:13.8.0 0.27.2:13.9.4 0.27.3:13.8.0 0.27.3:13.9.4
0.28.0:13.8.0 0.28.0:13.9.4 0.29.0:13.8.0 0.29.0:13.9.4 0.29.1:13.8.0 0.29.1:13.9.4 0.29.2:13.8.0 0.29.2:13.9.4"
one() {
  t=${1%%:*}; r=${1##*:}; n="t$t-r$r"
  uv venv -q --clear --python 3.13 "$W/envs/$n" && uv pip install -q --python "$W/envs/$n/bin/python" "typer==$t" "rich==$r" || { echo "install failed $n"; return; }
  P="$W/envs/$n/bin/python"; mkdir -p "$W/out/$n"
  "$P" "$FX/inproc.py" > "$W/out/$n/inproc.json" 2> "$W/out/$n/inproc.err"
  python3 "$FX/proc.py" "$P" > "$W/out/$n/proc.json" 2> "$W/out/$n/proc.err"
  python3 "$FX/comp.py" "$P" > "$W/out/$n/comp.json" 2> "$W/out/$n/comp.err"
  python3 "$FX/docs.py" "$P" "$W/out/$n" > "$W/out/$n/docs.json" 2> "$W/out/$n/docs.err"
  echo "done $n"
}
export -f one; export W FX
echo $PAIRS | tr ' ' '\n' | xargs -P 3 -I{} bash -c 'one {}'
