#!/bin/bash
# prints the cell list: version java locale option extra
for v in 174 180; do for j in 11 21 25; do
  for l in C POSIX Cutf8; do echo $v $j $l none $([ $l != POSIX ] && echo 1 || echo 0); done
  for o in fileenc stdout sunstdout all latin1; do echo $v $j C $o 0; done
done; done
echo 174 25 enUS none 0; echo 180 25 enUS none 0; echo 174 11 enUS none 0; echo 180 11 enUS none 0
