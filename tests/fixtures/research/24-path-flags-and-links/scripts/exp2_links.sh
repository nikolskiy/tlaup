#!/bin/bash
: "${TMP_ROOT:?set TMP_ROOT to the scratch root that holds jars/ and q24/}"
# Part 2: symbolic links. Run after mklayout.sh. cwd = work/ unless stated. Both versions.
Q=$TMP_ROOT/q24; T=$Q/t
r() { # label ver cwd args...
  local label=$1; shift; echo "--- $label"; "$Q/run.sh" "$@" | sed 's/^/    /'; }
relcfg() { python3 -I -c 'import os,sys; spec,cfg=sys.argv[1:3]; print(os.path.relpath(os.path.realpath(cfg), os.path.realpath(os.path.dirname(spec))))' "$1" "$2"; }
for v in 174 180; do
 echo "######## version $v"
 echo "== L: folder link  (L/lnk -> ../real/proj; decoys: L/Helper.tla, L/out.cfg)"
 r "L1 spec via folder link, default cfg"                     $v work $T/L/lnk/Spec.tla
 r "L2 spec via folder link, -config ../out.cfg (OS: real/out.cfg=4, lexical: L/out.cfg=44)"  $v work -config ../out.cfg $T/L/lnk/Spec.tla
 r "L3 spec via folder link, -config sub/a.cfg (2)"           $v work -config sub/a.cfg $T/L/lnk/Spec.tla
 r "L4 spec via folder link with .. in spec path: L/lnk/../proj/Spec.tla (OS ok, lexical L/proj missing)" $v work $T/L/lnk/../proj/Spec.tla
 r "L5 control: real path, -config ../out.cfg (4)"            $v work -config ../out.cfg $T/real/proj/Spec.tla
 r "L6 control: real path, -config ../other/o.cfg (5)"        $v work -config ../other/o.cfg $T/real/proj/Spec.tla
 r "L7 control: real path, -config ../../outside/o.cfg (6)"   $v work -config ../../outside/o.cfg $T/real/proj/Spec.tla
 echo "== L2: deeper link  (L2/lnk -> ../deep/a/b; cfgs: b/Spec.cfg=11, a/out.cfg=12, deep/out.cfg=13, L2/out.cfg=99)"
 r "M1 default cfg"                                           $v work $T/L2/lnk/Spec.tla
 r "M2 -config ../out.cfg (OS 12, lexical 99)"                $v work -config ../out.cfg $T/L2/lnk/Spec.tla
 r "M3 -config ../../out.cfg (OS 13, lexical: <T>/out.cfg missing)" $v work -config ../../out.cfg $T/L2/lnk/Spec.tla
 r "M4 -config ../../../L2/out.cfg (OS walk from deep/a/b gives <T>/L2/out.cfg = 99)" $v work -config ../../../L2/out.cfg $T/L2/lnk/Spec.tla
 r "M5 spec L2/lnk/../b/Spec.tla (OS ok, lexical L2/b missing)" $v work $T/L2/lnk/../b/Spec.tla
 echo "== F: file link  (Lf/Spec.tla -> ../real/proj/Spec.tla; beside link: Lf/Helper.tla marker helper-beside-file-link, Lf/Spec.cfg=77; beside target: helper-real-proj, Spec.cfg=1)"
 r "F1 abs spec = file link, default cfg"                      $v work $T/Lf/Spec.tla
 r "F2 abs spec = file link, -config Spec.cfg"                 $v work -config Spec.cfg $T/Lf/Spec.tla
 r "F3 relative spec = file link, cwd Lf"                      $v Lf Spec.tla
 r "F4 relative spec = file link, cwd work"                    $v work ../Lf/Spec.tla
 r "F5 relative bare name, cwd Lf (control)"                   $v Lf Spec
 echo "== R4: tlaup's relative -config (relpath(realpath(cfg), realpath(spec.parent))) fed to TLC, abs spec as typed"
 rr() { # label ver spec cfg expectedN
   local label=$1 ver=$2 spec=$3 cfg=$4; local rel; rel=$(relcfg "$spec" "$cfg"); echo "--- $label"; echo "    validated cfg: $(basename "$cfg") = $(grep -o 'N = [0-9]*' "$cfg") ; relative -config computed: $rel"; "$Q/run.sh" $ver work -config "$rel" "$spec" | sed 's/^/    /'; }
 rr "R1 spec L/lnk, cfg \$T/L/lnk/../out.cfg (file: real/out.cfg=4)"   $v $T/L/lnk/Spec.tla $T/L/lnk/../out.cfg
 rr "R2 spec L/lnk, cfg \$T/L/out.cfg (44)"                            $v $T/L/lnk/Spec.tla $T/L/out.cfg
 rr "R3 spec L2/lnk, cfg \$T/L2/lnk/../out.cfg (12)"                   $v $T/L2/lnk/Spec.tla $T/L2/lnk/../out.cfg
 rr "R4 spec L2/lnk, cfg \$T/L2/lnk/../../out.cfg (13)"                $v $T/L2/lnk/Spec.tla $T/L2/lnk/../../out.cfg
 rr "R5 spec L2/lnk, cfg \$T/L2/out.cfg (99)"                          $v $T/L2/lnk/Spec.tla $T/L2/out.cfg
 rr "R6 spec L2/lnk, cfg \$T/work/out.cfg (55)"                        $v $T/L2/lnk/Spec.tla $T/work/out.cfg
 rr "R7 spec L2/lnk, cfg \$T/outside/o.cfg (6)"                        $v $T/L2/lnk/Spec.tla $T/outside/o.cfg
 rr "R8 spec L/lnk, cfg \$T/real/proj/sub/a.cfg (2), through the real path" $v $T/L/lnk/Spec.tla $T/real/proj/sub/a.cfg
 rr "R9 spec file link Lf/Spec.tla, cfg \$T/real/out.cfg (4)"           $v $T/Lf/Spec.tla $T/real/out.cfg
 rr "R10 no link, spec real/proj, cfg \$T/outside/o.cfg (6)"            $v $T/real/proj/Spec.tla $T/outside/o.cfg
done
