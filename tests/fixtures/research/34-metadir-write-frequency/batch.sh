#!/bin/bash
# Runs the experiments of question 34 in batches of up to four runs.
# Usage: batch.sh b1 b2 b3 b4 b5, from a folder that holds watch_run.py, specs/
# and ../jars/{v1.7.4,rolling}/tla2tools.jar.
cd "$(dirname "$0")"
J174=$PWD/../jars/v1.7.4/tla2tools.jar
J180=$PWD/../jars/rolling/tla2tools.jar
W="python3 watch_run.py"
X="--java-opt -Xmx1g"
b1() {
  $W big-174-default $J174 specs Big 900 $X -- -workers 2 &
  $W big-180-default $J180 specs Big 900 $X -- -workers 2 &
  $W slow-174-default $J174 specs Slow 2160 $X -- -workers 1 &
  $W slow-180-default $J180 specs Slow 2160 $X -- -workers 1 &
  wait
}
b2() {
  $W big-174-ck1 $J174 specs Big 900 $X -- -workers 2 -checkpoint 1 &
  $W big-180-ck1 $J180 specs Big 900 $X -- -workers 2 -checkpoint 1 &
  $W slow-174-ck1 $J174 specs Slow 900 $X -- -workers 1 -checkpoint 1 &
  $W slow-180-ck1 $J180 specs Slow 900 $X -- -workers 1 -checkpoint 1 &
  wait
}
b3() {
  $W sim-174 $J174 specs Big 600 $X -- -workers 1 -simulate -depth 100 &
  $W sim-180 $J180 specs Big 600 $X -- -workers 1 -simulate -depth 100 &
  $W live-174 $J174 specs Live 1800 $X -- -workers 2 &
  $W live-180 $J180 specs Live 1800 $X -- -workers 2 &
  wait
}
b4() {
  $W dfid-174 $J174 specs Big 600 $X -- -workers 1 -dfid 60 &
  $W dfid-180 $J180 specs Big 600 $X -- -workers 1 -dfid 60 &
  $W sim-180-ck1 $J180 specs Big 600 $X -- -workers 1 -simulate -depth 100 -checkpoint 1 &
  wait
}
# Run by hand after b1 to b4, alone or beside them. specs2/ holds Slow.tla with
# specs/SlowStep12min.cfg as Slow.cfg (one step about 12 minutes); specs3/ holds
# specs/Live4000.tla as Live.tla with Live.cfg.
b5() {
  $W veryslow-180-ck1 $J180 specs2 Slow 1200 $X -- -workers 1 -checkpoint 1 &
  $W live4000-180 $J180 specs3 Live 1800 --java-opt -Xmx1500m -- -workers 2 &
  wait
  $W live4000-174 $J174 specs3 Live 1800 --java-opt -Xmx1500m -- -workers 2 &
  $W dfid-180-ck1 $J180 specs Big 200 $X -- -workers 1 -dfid 60 -checkpoint 1 &
  wait
}
for b in "$@"; do echo "batch $b start $(date -u +%FT%TZ)"; $b; echo "batch $b end $(date -u +%FT%TZ)"; done
