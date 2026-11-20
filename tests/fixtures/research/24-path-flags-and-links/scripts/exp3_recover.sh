#!/bin/bash
: "${TMP_ROOT:?set TMP_ROOT to the scratch root that holds jars/ and q24/}"
# Part 3: -recover with a relative path. Starts a run with -checkpoint 1 in t/rec, kills it by PID once a checkpoint exists,
# then recovers with the relative metadir path from the same cwd and from another cwd. Version arg: 174|180
Q=$TMP_ROOT/q24; T=$Q/t; v=$1
case $v in 174) J=$Q/../jars/v1.7.4/tla2tools.jar;; 180) J=$Q/../jars/rolling/tla2tools.jar;; esac
rm -rf $T/rec/*; mkdir -p $T/rec $T/rec2; cd $T/rec
java -Xmx3g -cp $J tlc2.TLC -nowarning -workers 1 -checkpoint 1 -metadir relck $T/big/Big.tla > $T/rec/first.log 2>&1 &
pid=$!
for i in $(seq 1 150); do sleep 2; ls relck/*/*.chkpt >/dev/null 2>&1 && ls relck/*/ | grep -q chkpt && break; kill -0 $pid 2>/dev/null || break; done
sleep 3; kill $pid; wait $pid 2>/dev/null
echo "files after kill:"; find relck | sort | head -20
D=$(ls -d relck/*/ | head -1); D=${D%/}
echo "recover dir (relative): $D"
echo "--- recover, same cwd (rec), relative path"
timeout 100 java -Xmx3g -cp $J tlc2.TLC -nowarning -workers 1 -recover $D -metadir relck2 $T/big/Big.tla 2>&1 | grep -iE "recover|checkpoint|error|exception|not found|No such|Finished|distinct" | head -8
echo "--- recover, other cwd (rec2), same relative path"
cd $T/rec2
timeout 100 java -Xmx3g -cp $J tlc2.TLC -nowarning -workers 1 -recover $D -metadir relck2 $T/big/Big.tla 2>&1 | grep -iE "recover|checkpoint|error|exception|not found|No such|Finished|distinct" | head -8
echo "--- recover, other cwd (rec2), spec-folder-relative? (path of the checkpoint under big/: none)"
