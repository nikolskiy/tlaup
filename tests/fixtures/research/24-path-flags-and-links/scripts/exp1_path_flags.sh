#!/bin/bash
: "${TMP_ROOT:?set TMP_ROOT to the scratch root that holds jars/ and q24/}"
# Part 1: where relative paths given to path-taking flags land, spec absolute, cwd = work (a folder other than the spec's).
# Run: exp1_path_flags.sh  (needs ./mklayout.sh run first)
Q=$TMP_ROOT/q24; T=$Q/t; S=$T/real/proj/Spec.tla
for v in 174 180; do
 echo "######## version $v  (cwd = work/, spec = <T>/real/proj/Spec.tla, cfg = Spec.cfg beside the spec, TLC violates Inv)"
 row() { echo "--- $1"; shift; "$Q/clean.sh"; "$Q/landed.sh" "$@"; }
 row "P1 -dump rel (no suffix)"            $v work -dump rel $S
 row "P2 -dump rel.dump"                   $v work -dump rel.dump $S
 row "P3 -dump dot rel.dot"                $v work -dump dot rel.dot $S
 row "P4 -dump sub/rel (sub exists only in spec folder)"  $v work -dump sub/rel $S
 row "P5 -dump dumps/rel (folder exists nowhere)"  $v work -dump dumps/rel $S
 row "P6 -dump \${metadir}/rel"            $v work -dump '${metadir}/rel' $S
 row "P7 -dump absolute"                   $v work -dump $T/outside/abs $S
 row "M1 -metadir relmeta"                 $v work -metadir relmeta $S
 row "M2 -metadir ../relmeta"              $v work -metadir ../relmeta $S
 NOMETA=1 row "M3 no -metadir (absolute spec)"      $v work $S
 row "U1 -userFile rel.out"                $v work -userFile rel.out $S
 row "U2 -userFile sub/rel.out (sub only in spec folder)" $v work -userFile sub/rel.out $S
 row "T0 default (no TE flag, violation)"  $v work $S
 row "T1 -generateSpecTE"                  $v work -generateSpecTE $S
 row "S1 -simulate file=rel num=2"         $v work -simulate file=rel,num=2 $S
 if [ $v = 180 ]; then
 row "D1 -dumpTrace json rel.json"         $v work -dumpTrace json rel.json $S
 row "D2 -dumpTrace json sub/rel.json"     $v work -dumpTrace json sub/rel.json $S
 row "D3 -dumpTrace json dumps/rel.json"   $v work -dumpTrace json dumps/rel.json $S
 row "D4 -dumpTrace json absolute"         $v work -dumpTrace json $T/outside/abs.json $S
 row "D5 -dumpTrace tlc rel.tlc"           $v work -dumpTrace tlc rel.tlc $S
 row "E1 -teSpecOutDir te"                 $v work -teSpecOutDir te $S
 row "E2 -teSpecOutDir te/MyTE.tla"        $v work -teSpecOutDir te/MyTE.tla $S
 row "E3 -teSpecOutDir absolute dir"       $v work -teSpecOutDir $T/outside $S
 row "E4 -noGenerateSpecTE"                $v work -noGenerateSpecTE $S
 fi
done
