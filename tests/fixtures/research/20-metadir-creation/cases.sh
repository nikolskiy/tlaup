#!/bin/bash
# Research 20: does TLC create a missing -metadir? usage: cases.sh <version-label> <jar> <java>
# Everything happens under $W (a private folder); prints one block per case.
lbl=$1; jar=$2; java=$3
W=${W:-$(pwd)/work}/$lbl; rm -rf "$W"; mkdir -p "$W/cwd"
SPEC=${SPEC:-Small}
spec=$(cd "$(dirname "$0")" && pwd)/spec/$SPEC.tla
run() { # label metadir-arg
  l=$1; md=$2
  out=$(cd "$W/cwd" && timeout 120 "$java" -cp "$jar" tlc2.TLC -workers 1 -metadir "$md" "$spec" 2>&1); rc=$?
  echo "### [$lbl] $l: -metadir '$md' (cwd=\$W/cwd) exit=$rc"
  echo "$out" | grep -i "exception\|error\|metadir\|Model checking completed\|permission\|denied\|exist" | cut -c1-260 | head -5
}
tree() { (cd "$W" && find "$@" -printf '%y %p\n' 2>/dev/null | sed 's/^/    /' | sort -k2); }
java -version 2>&1 | head -1 | sed 's/^/# java: /'
mkdir -p "$W/exist"
run A_existing "$W/exist"; tree exist
run B_one_level_missing "$W/b1"; tree b1
run C_three_levels_missing "$W/c1/c2/c3"; tree c1
run D_trailing_slash_missing "$W/d1/"; tree d1
run E_relative_missing "rel1/rel2"; tree cwd
run F_relative_dot_missing "./relx"; tree cwd/relx
touch "$W/afile"
run G_parent_is_file "$W/afile/md"; tree afile
run H_grandparent_is_file "$W/afile/m1/m2"; tree afile
run I_metadir_is_file "$W/afile"; tree afile
mkdir -p "$W/ro"; chmod 555 "$W/ro"
run J_parent_not_writable "$W/ro/md"; tree ro
run K_grandparent_not_writable "$W/ro/m1/m2"; tree ro
chmod 755 "$W/ro"
mkdir -p "$W/real"; ln -s "$W/real" "$W/link"
run L_via_symlink_parent "$W/link/sub"; tree real
ln -s "$W/nowhere" "$W/dangling"
run M_dangling_symlink_parent "$W/dangling/sub"; tree dangling
ln -s "$W/nowhere2" "$W/dangling2"
run N_metadir_dangling_symlink "$W/dangling2"; tree dangling2
