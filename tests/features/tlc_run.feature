Feature: Running TLC
  "tlaup tlc SPEC" checks the spec, the cfg, the build and Java, builds one Java command, runs TLC in its own run
  folder and shows TLC's output: results on stdout, progress and tlaup's own lines on stderr. The exit code is
  TLC's (design 11 R1 to R8, 20 G1, 02 X1 and X2, 13 J1 to J3). The fake java replays the golden captures.

  # X1, inventory row R1: TLC's exit code passes through

  # Every case of both builds' cases.toml with a recorded exit code. json-live, json-stut and dump-trace-live are
  # left out: their captures recorded no exit code, so there is none to pass through. The plain/ captures are
  # replayed by tlc_raw.feature (39b).

  Scenario Outline: The exit code of <case> passes through
    Given the build "<build>" is installed and pinned
    And a spec "<spec>" from the golden specs
    And java replays "<case>" with exit code <code>
    When I run "tlaup tlc <name>"
    Then the exit code is <code>
    And java was started with "-tool"

    Examples:
      | build   | case                                                             | spec                                | name          | code |
      | v1.7.4  | tlc/v1.7.4/alias-violation                                       | Alias                               | Alias         | 151  |
      | v1.7.4  | tlc/v1.7.4/alias-violation-difftrace                             | Alias                               | Alias         | 151  |
      | v1.7.4  | tlc/v1.7.4/assertion-failure                                     | Assertion                           | Assertion     | 14   |
      | v1.7.4  | tlc/v1.7.4/big-states                                            | Big                                 | Big           | 0    |
      | v1.7.4  | tlc/v1.7.4/checkpoint-recover                                    | Slow                                | Slow          | 0    |
      | v1.7.4  | tlc/v1.7.4/checkpoint-recover-missing                            | Slow                                | Slow          | 255  |
      | v1.7.4  | tlc/v1.7.4/checkpoint-run                                        | Slow                                | Slow          | 143  |
      | v1.7.4  | tlc/v1.7.4/coverage                                              | Success                             | Success       | 0    |
      | v1.7.4  | tlc/v1.7.4/deadlock                                              | Deadlock                            | Deadlock      | 11   |
      | v1.7.4  | tlc/v1.7.4/deadlock-flag                                         | Deadlock                            | Deadlock      | 0    |
      | v1.7.4  | tlc/v1.7.4/deadlock-flag-multierror                              | MultiError                          | MultiError    | 0    |
      | v1.7.4  | tlc/v1.7.4/dfid-deadlock                                         | Deadlock                            | Deadlock      | 0    |
      | v1.7.4  | tlc/v1.7.4/dfid-success                                          | Success                             | Success       | 0    |
      | v1.7.4  | tlc/v1.7.4/dfid-success-deep                                     | Success                             | Success       | 0    |
      | v1.7.4  | tlc/v1.7.4/dfid-violation                                        | Violation                           | Violation     | 0    |
      | v1.7.4  | tlc/v1.7.4/dfid-violation-deep                                   | Violation                           | Violation     | 12   |
      | v1.7.4  | tlc/v1.7.4/difftrace-deadlock                                    | Deadlock                            | Deadlock      | 11   |
      | v1.7.4  | tlc/v1.7.4/difftrace-liveness                                    | DiffLive                            | DiffLive      | 13   |
      | v1.7.4  | tlc/v1.7.4/difftrace-liveness-nodiff                             | DiffLive                            | DiffLive      | 13   |
      | v1.7.4  | tlc/v1.7.4/difftrace-liveness-q1-back-to-state                   | LiveBack                            | LiveBack      | 13   |
      | v1.7.4  | tlc/v1.7.4/difftrace-liveness-q1-stuttering                      | LiveStutter                         | LiveStutter   | 13   |
      | v1.7.4  | tlc/v1.7.4/difftrace-q1-violation                                | Violation                           | Violation     | 12   |
      | v1.7.4  | tlc/v1.7.4/difftrace-violation                                   | Diff                                | Diff          | 12   |
      | v1.7.4  | tlc/v1.7.4/difftrace-violation-nodiff                            | Diff                                | Diff          | 12   |
      | v1.7.4  | tlc/v1.7.4/difftrace-workers-4                                   | Diff                                | Diff          | 12   |
      | v1.7.4  | tlc/v1.7.4/generate-deadlock                                     | Deadlock                            | Deadlock      | 1    |
      | v1.7.4  | tlc/v1.7.4/generate-success                                      | Success                             | Success       | 1    |
      | v1.7.4  | tlc/v1.7.4/generate-success-num                                  | Success                             | Success       | 1    |
      | v1.7.4  | tlc/v1.7.4/generate-violation                                    | Violation                           | Violation     | 1    |
      | v1.7.4  | tlc/v1.7.4/generate-violation-num                                | Violation                           | Violation     | 1    |
      | v1.7.4  | tlc/v1.7.4/generateSpecTE-violation                              | Violation                           | Violation     | 12   |
      | v1.7.4  | tlc/v1.7.4/java-override-exception                               | Boom                                | Boom          | 75   |
      | v1.7.4  | tlc/v1.7.4/java-override-stack-trace                             | BoomTrace                           | BoomTrace     | 75   |
      | v1.7.4  | tlc/v1.7.4/liveness-back-to-state                                | LiveBack                            | LiveBack      | 13   |
      | v1.7.4  | tlc/v1.7.4/liveness-stuttering                                   | LiveStutter                         | LiveStutter   | 13   |
      | v1.7.4  | tlc/v1.7.4/multi-error-continue                                  | MultiError                          | MultiError    | 11   |
      | v1.7.4  | tlc/v1.7.4/noGenerateSpecTE-violation                            | Violation                           | Violation     | 1    |
      | v1.7.4  | tlc/v1.7.4/override-annot_module_missing                         | overrides/annot_module_missing/spec | spec          | 0    |
      | v1.7.4  | tlc/v1.7.4/override-annot_op_missing                             | overrides/annot_op_missing/spec     | spec          | 0    |
      | v1.7.4  | tlc/v1.7.4/override-arity_java_fewer                             | overrides/arity_java_fewer/spec     | spec          | 0    |
      | v1.7.4  | tlc/v1.7.4/override-class-too-new-index                          | Ok                                  | Ok            | 255  |
      | v1.7.4  | tlc/v1.7.4/override-class-too-new-listed                         | Ok                                  | Ok            | 255  |
      | v1.7.4  | tlc/v1.7.4/override-ctor_private                                 | overrides/ctor_private/spec         | spec          | 255  |
      | v1.7.4  | tlc/v1.7.4/override-ctor_throws                                  | overrides/ctor_throws/spec          | spec          | 255  |
      | v1.7.4  | tlc/v1.7.4/override-eval_throws_runtime                          | overrides/eval_throws_runtime/spec  | spec          | 75   |
      | v1.7.4  | tlc/v1.7.4/override-legacy_ok                                    | overrides/legacy_ok/spec            | spec          | 0    |
      | v1.7.4  | tlc/v1.7.4/override-method_not_public                            | overrides/method_not_public/spec    | spec          | 255  |
      | v1.7.4  | tlc/v1.7.4/override-ok_warn_true                                 | overrides/ok_warn_true/spec         | spec          | 0    |
      | v1.7.4  | tlc/v1.7.4/override-static_init_throws                           | overrides/static_init_throws/spec   | spec          | 255  |
      | v1.7.4  | tlc/v1.7.4/params-instance-exists-violation                      | Params                              | Params        | 12   |
      | v1.7.4  | tlc/v1.7.4/params-instance-exists-violation-difftrace            | Params                              | Params        | 12   |
      | v1.7.4  | tlc/v1.7.4/params-step-violation                                 | Params                              | Params        | 12   |
      | v1.7.4  | tlc/v1.7.4/params-step-violation-difftrace                       | Params                              | Params        | 12   |
      | v1.7.4  | tlc/v1.7.4/params-violation                                      | Params                              | Params        | 12   |
      | v1.7.4  | tlc/v1.7.4/params-violation-difftrace                            | Params                              | Params        | 12   |
      | v1.7.4  | tlc/v1.7.4/parse-error                                           | ParseError                          | ParseError    | 150  |
      | v1.7.4  | tlc/v1.7.4/postcondition-false                                   | Post                                | Post          | 255  |
      | v1.7.4  | tlc/v1.7.4/print-marker                                          | PrintMarker                         | PrintMarker   | 11   |
      | v1.7.4  | tlc/v1.7.4/print-output                                          | Print                               | Print         | 11   |
      | v1.7.4  | tlc/v1.7.4/sany-semantic-error                                   | SanyError                           | SanyError     | 150  |
      | v1.7.4  | tlc/v1.7.4/simulate                                              | Success                             | Success       | 0    |
      | v1.7.4  | tlc/v1.7.4/simulate-deadlock                                     | Deadlock                            | Deadlock      | 11   |
      | v1.7.4  | tlc/v1.7.4/simulate-liveness                                     | LiveBack                            | LiveBack      | 13   |
      | v1.7.4  | tlc/v1.7.4/simulate-violation                                    | Violation                           | Violation     | 12   |
      | v1.7.4  | tlc/v1.7.4/simulate-violation-diff                               | Diff                                | Diff          | 12   |
      | v1.7.4  | tlc/v1.7.4/stack-overflow                                        | Stack                               | Stack         | 75   |
      | v1.7.4  | tlc/v1.7.4/stale-alg-tool                                        | v1.7.4/PcalStaleAlg                 | PcalStaleAlg  | 0    |
      | v1.7.4  | tlc/v1.7.4/stale-both-tool                                       | v1.7.4/PcalStaleBoth                | PcalStaleBoth | 0    |
      | v1.7.4  | tlc/v1.7.4/stale-tla-tool                                        | v1.7.4/PcalStaleTla                 | PcalStaleTla  | 0    |
      | v1.7.4  | tlc/v1.7.4/success                                               | Success                             | Success       | 0    |
      | v1.7.4  | tlc/v1.7.4/tool-act                                              | Act                                 | Act           | 13   |
      | v1.7.4  | tlc/v1.7.4/tool-asrt                                             | Asrt                                | Asrt          | 14   |
      | v1.7.4  | tlc/v1.7.4/tool-assum                                            | Assum                               | Assum         | 10   |
      | v1.7.4  | tlc/v1.7.4/tool-badcfg                                           | BadCfg                              | BadCfg        | 151  |
      | v1.7.4  | tlc/v1.7.4/tool-cfg-missing                                      | Ok                                  | Ok            | 255  |
      | v1.7.4  | tlc/v1.7.4/tool-cfgsyn                                           | CfgSyn                              | CfgSyn        | 255  |
      | v1.7.4  | tlc/v1.7.4/tool-eval                                             | Eval                                | Eval          | 75   |
      | v1.7.4  | tlc/v1.7.4/tool-help                                             | Ok                                  | Ok            | 1    |
      | v1.7.4  | tlc/v1.7.4/tool-missing-module                                   | MissMod                             | MissMod       | 150  |
      | v1.7.4  | tlc/v1.7.4/tool-name-mismatch                                    | Mismatch                            | Mismatch      | 150  |
      | v1.7.4  | tlc/v1.7.4/tool-nexteval                                         | NextEval                            | NextEval      | 255  |
      | v1.7.4  | tlc/v1.7.4/tool-noargs                                           | Ok                                  | Ok            | 1    |
      | v1.7.4  | tlc/v1.7.4/tool-nocfg                                            | NoCfg                               | NoCfg         | 255  |
      | v1.7.4  | tlc/v1.7.4/tool-nospecfile                                       | Ok                                  | Ok            | 255  |
      | v1.7.4  | tlc/v1.7.4/tool-oom                                              | Oom                                 | Oom           | 75   |
      | v1.7.4  | tlc/v1.7.4/tool-workers-bad                                      | Ok                                  | Ok            | 1    |
      | v1.7.4  | tlc/v1.7.4/version-bad-option                                    | Ok                                  | Ok            | 1    |
      | v1.7.4  | tlc/v1.7.4/violation                                             | Violation                           | Violation     | 12   |
      | v1.7.4  | tlc/v1.7.4/warn4802-tool                                         | Warn4802                            | Warn4802      | 150  |
      | v1.7.4  | tlc/v1.7.4/warnstutter-tool                                      | WarnStutter                         | WarnStutter   | 150  |
      | v1.7.4  | tlc/v1.7.4/workers-4                                             | Success                             | Success       | 0    |
      | rolling | tlc/2026.11.15.002146/alias-violation                            | Alias                               | Alias         | 12   |
      | rolling | tlc/2026.11.15.002146/alias-violation-difftrace                  | Alias                               | Alias         | 12   |
      | rolling | tlc/2026.11.15.002146/assertion-failure                          | Assertion                           | Assertion     | 14   |
      | rolling | tlc/2026.11.15.002146/big-states                                 | Big                                 | Big           | 0    |
      | rolling | tlc/2026.11.15.002146/checkpoint-recover                         | Slow                                | Slow          | 0    |
      | rolling | tlc/2026.11.15.002146/checkpoint-recover-missing                 | Slow                                | Slow          | 255  |
      | rolling | tlc/2026.11.15.002146/checkpoint-run                             | Slow                                | Slow          | 143  |
      | rolling | tlc/2026.11.15.002146/coverage                                   | Success                             | Success       | 0    |
      | rolling | tlc/2026.11.15.002146/deadlock                                   | Deadlock                            | Deadlock      | 11   |
      | rolling | tlc/2026.11.15.002146/deadlock-flag                              | Deadlock                            | Deadlock      | 0    |
      | rolling | tlc/2026.11.15.002146/deadlock-flag-multierror                   | MultiError                          | MultiError    | 0    |
      | rolling | tlc/2026.11.15.002146/dfid-deadlock                              | Deadlock                            | Deadlock      | 0    |
      | rolling | tlc/2026.11.15.002146/dfid-success                               | Success                             | Success       | 0    |
      | rolling | tlc/2026.11.15.002146/dfid-success-deep                          | Success                             | Success       | 0    |
      | rolling | tlc/2026.11.15.002146/dfid-violation                             | Violation                           | Violation     | 0    |
      | rolling | tlc/2026.11.15.002146/dfid-violation-deep                        | Violation                           | Violation     | 12   |
      | rolling | tlc/2026.11.15.002146/difftrace-deadlock                         | Deadlock                            | Deadlock      | 11   |
      | rolling | tlc/2026.11.15.002146/difftrace-liveness                         | DiffLive                            | DiffLive      | 13   |
      | rolling | tlc/2026.11.15.002146/difftrace-liveness-nodiff                  | DiffLive                            | DiffLive      | 13   |
      | rolling | tlc/2026.11.15.002146/difftrace-liveness-q1-back-to-state        | LiveBack                            | LiveBack      | 13   |
      | rolling | tlc/2026.11.15.002146/difftrace-liveness-q1-stuttering           | LiveStutter                         | LiveStutter   | 13   |
      | rolling | tlc/2026.11.15.002146/difftrace-q1-violation                     | Violation                           | Violation     | 12   |
      | rolling | tlc/2026.11.15.002146/difftrace-violation                        | Diff                                | Diff          | 12   |
      | rolling | tlc/2026.11.15.002146/difftrace-violation-nodiff                 | Diff                                | Diff          | 12   |
      | rolling | tlc/2026.11.15.002146/difftrace-workers-4                        | Diff                                | Diff          | 12   |
      | rolling | tlc/2026.11.15.002146/generate-deadlock                          | Deadlock                            | Deadlock      | 11   |
      | rolling | tlc/2026.11.15.002146/generate-success                           | Success                             | Success       | 137  |
      | rolling | tlc/2026.11.15.002146/generate-success-num                       | Success                             | Success       | 0    |
      | rolling | tlc/2026.11.15.002146/generate-violation                         | Violation                           | Violation     | 12   |
      | rolling | tlc/2026.11.15.002146/generate-violation-num                     | Violation                           | Violation     | 12   |
      | rolling | tlc/2026.11.15.002146/generateSpecTE-violation                   | Violation                           | Violation     | 12   |
      | rolling | tlc/2026.11.15.002146/java-override-exception                    | Boom                                | Boom          | 75   |
      | rolling | tlc/2026.11.15.002146/java-override-stack-trace                  | BoomTrace                           | BoomTrace     | 75   |
      | rolling | tlc/2026.11.15.002146/liveness-back-to-state                     | LiveBack                            | LiveBack      | 13   |
      | rolling | tlc/2026.11.15.002146/liveness-stuttering                        | LiveStutter                         | LiveStutter   | 13   |
      | rolling | tlc/2026.11.15.002146/multi-error-continue                       | MultiError                          | MultiError    | 11   |
      | rolling | tlc/2026.11.15.002146/noGenerateSpecTE-violation                 | Violation                           | Violation     | 12   |
      | rolling | tlc/2026.11.15.002146/override-annot_module_missing              | overrides/annot_module_missing/spec | spec          | 0    |
      | rolling | tlc/2026.11.15.002146/override-annot_op_missing                  | overrides/annot_op_missing/spec     | spec          | 0    |
      | rolling | tlc/2026.11.15.002146/override-arity_java_fewer                  | overrides/arity_java_fewer/spec     | spec          | 0    |
      | rolling | tlc/2026.11.15.002146/override-class-too-new-index               | Ok                                  | Ok            | 255  |
      | rolling | tlc/2026.11.15.002146/override-class-too-new-listed              | Ok                                  | Ok            | 255  |
      | rolling | tlc/2026.11.15.002146/override-ctor_private                      | overrides/ctor_private/spec         | spec          | 255  |
      | rolling | tlc/2026.11.15.002146/override-ctor_throws                       | overrides/ctor_throws/spec          | spec          | 255  |
      | rolling | tlc/2026.11.15.002146/override-eval_throws_runtime               | overrides/eval_throws_runtime/spec  | spec          | 75   |
      | rolling | tlc/2026.11.15.002146/override-legacy_ok                         | overrides/legacy_ok/spec            | spec          | 0    |
      | rolling | tlc/2026.11.15.002146/override-method_not_public                 | overrides/method_not_public/spec    | spec          | 255  |
      | rolling | tlc/2026.11.15.002146/override-ok_warn_true                      | overrides/ok_warn_true/spec         | spec          | 0    |
      | rolling | tlc/2026.11.15.002146/override-static_init_throws                | overrides/static_init_throws/spec   | spec          | 255  |
      | rolling | tlc/2026.11.15.002146/params-instance-exists-violation           | Params                              | Params        | 12   |
      | rolling | tlc/2026.11.15.002146/params-instance-exists-violation-difftrace | Params                              | Params        | 12   |
      | rolling | tlc/2026.11.15.002146/params-step-violation                      | Params                              | Params        | 12   |
      | rolling | tlc/2026.11.15.002146/params-step-violation-difftrace            | Params                              | Params        | 12   |
      | rolling | tlc/2026.11.15.002146/params-violation                           | Params                              | Params        | 12   |
      | rolling | tlc/2026.11.15.002146/params-violation-difftrace                 | Params                              | Params        | 12   |
      | rolling | tlc/2026.11.15.002146/parse-error                                | ParseError                          | ParseError    | 150  |
      | rolling | tlc/2026.11.15.002146/postcondition-false                        | Post                                | Post          | 10   |
      | rolling | tlc/2026.11.15.002146/print-marker                               | PrintMarker                         | PrintMarker   | 11   |
      | rolling | tlc/2026.11.15.002146/print-output                               | Print                               | Print         | 11   |
      | rolling | tlc/2026.11.15.002146/sany-semantic-error                        | SanyError                           | SanyError     | 150  |
      | rolling | tlc/2026.11.15.002146/simulate                                   | Success                             | Success       | 0    |
      | rolling | tlc/2026.11.15.002146/simulate-deadlock                          | Deadlock                            | Deadlock      | 11   |
      | rolling | tlc/2026.11.15.002146/simulate-liveness                          | LiveBack                            | LiveBack      | 13   |
      | rolling | tlc/2026.11.15.002146/simulate-violation                         | Violation                           | Violation     | 12   |
      | rolling | tlc/2026.11.15.002146/simulate-violation-diff                    | Diff                                | Diff          | 12   |
      | rolling | tlc/2026.11.15.002146/stack-overflow                             | Stack                               | Stack         | 255  |
      | rolling | tlc/2026.11.15.002146/stale-alg-tool                             | 2026.11.15.002146/PcalStaleAlg      | PcalStaleAlg  | 0    |
      | rolling | tlc/2026.11.15.002146/stale-both-tool                            | 2026.11.15.002146/PcalStaleBoth     | PcalStaleBoth | 0    |
      | rolling | tlc/2026.11.15.002146/stale-tla-tool                             | 2026.11.15.002146/PcalStaleTla      | PcalStaleTla  | 0    |
      | rolling | tlc/2026.11.15.002146/success                                    | Success                             | Success       | 0    |
      | rolling | tlc/2026.11.15.002146/tool-act                                   | Act                                 | Act           | 13   |
      | rolling | tlc/2026.11.15.002146/tool-asrt                                  | Asrt                                | Asrt          | 14   |
      | rolling | tlc/2026.11.15.002146/tool-assum                                 | Assum                               | Assum         | 10   |
      | rolling | tlc/2026.11.15.002146/tool-badcfg                                | BadCfg                              | BadCfg        | 151  |
      | rolling | tlc/2026.11.15.002146/tool-cfg-missing                           | Ok                                  | Ok            | 151  |
      | rolling | tlc/2026.11.15.002146/tool-cfgsyn                                | CfgSyn                              | CfgSyn        | 151  |
      | rolling | tlc/2026.11.15.002146/tool-eval                                  | Eval                                | Eval          | 75   |
      | rolling | tlc/2026.11.15.002146/tool-help                                  | Ok                                  | Ok            | 1    |
      | rolling | tlc/2026.11.15.002146/tool-missing-module                        | MissMod                             | MissMod       | 150  |
      | rolling | tlc/2026.11.15.002146/tool-name-mismatch                         | Mismatch                            | Mismatch      | 150  |
      | rolling | tlc/2026.11.15.002146/tool-nexteval                              | NextEval                            | NextEval      | 255  |
      | rolling | tlc/2026.11.15.002146/tool-noargs                                | Ok                                  | Ok            | 1    |
      | rolling | tlc/2026.11.15.002146/tool-nocfg                                 | NoCfg                               | NoCfg         | 151  |
      | rolling | tlc/2026.11.15.002146/tool-nospecfile                            | Ok                                  | Ok            | 151  |
      | rolling | tlc/2026.11.15.002146/tool-oom                                   | Oom                                 | Oom           | 75   |
      | rolling | tlc/2026.11.15.002146/tool-workers-bad                           | Ok                                  | Ok            | 1    |
      | rolling | tlc/2026.11.15.002146/version-bad-option                         | Ok                                  | Ok            | 1    |
      | rolling | tlc/2026.11.15.002146/violation                                  | Violation                           | Violation     | 12   |
      | rolling | tlc/2026.11.15.002146/warn4802-tool                              | Warn4802                            | Warn4802      | 150  |
      | rolling | tlc/2026.11.15.002146/warnstutter-tool                           | WarnStutter                         | WarnStutter   | 150  |
      | rolling | tlc/2026.11.15.002146/workers-4                                  | Success                             | Success       | 0    |

  # X1 and X2: a violation, its output and its streams

  Scenario: A violated invariant shows its message and its full trace on stdout
    Given the build "v1.7.4" is installed and pinned
    And a spec "Violation" from the golden specs
    And java replays "tlc/v1.7.4/violation" with exit code 12
    And java's output has "<tmp>/q01/run" replaced by "{work}"
    When I run "tlaup tlc Violation"
    Then the exit code is 12
    And stdout contains "Invariant Small is violated."
    And stdout matches the expected file "tlc_run/violation.txt"
    And stderr matches the expected file "tlc_run/violation.stderr.txt"
    And java was started with "-tool"

  # P3: the exit code and the verdict disagree

  Scenario: A run that exits 0 with two errors warns on stderr and still exits 0
    Given the build "v1.7.4" is installed and pinned
    And a spec "MultiError" from the golden specs
    And java replays "tlc/v1.7.4/deadlock-flag-multierror" with exit code 0
    When I run "tlaup tlc MultiError -- -deadlock -continue"
    Then the exit code is 0
    And stderr contains "warning: TLC exited with 0, but its output reports 2 errors" 1 times
    And stdout does not contain "warning:"

  # R3: output that is not UTF-8

  Scenario: Bytes that are not UTF-8 do not stop the run, and the lines around them are intact
    Given the build "v1.7.4" is installed and pinned
    And a spec "Violation" from the golden specs
    And java replays "synthetic/invalid-utf8" with exit code 12
    When I run "tlaup tlc Violation"
    Then the exit code is 12
    And stdout contains "Invariant Small is violated."
    And stdout contains "a d�lib"
    And stdout contains "Result: errors found"
    And stderr does not contain "Traceback"

  # R4: the cfg, the spec and the folder TLC runs in

  Scenario: A --cfg outside the project is passed relative to the spec's folder, and a decoy is not read
    Given the build "v1.7.4" is installed and pinned
    And a file "proj/Violation.tla" containing:
      """
      ---- MODULE Violation ----
      ====
      """
    And a file "proj/out.cfg" containing:
      """
      INVARIANT Decoy
      """
    And a file "outside/out.cfg" containing:
      """
      INVARIANT Small
      """
    And java replays "tlc/v1.7.4/violation" with exit code 12
    When I run "tlaup tlc proj/Violation --cfg outside/out.cfg"
    Then the exit code is 12
    And java was started with "-config"
    And java was started with "../outside/out.cfg"
    And java was started without "out.cfg"
    And java was started with "{work}/proj/Violation.tla"
    And java was started in the folder "{work}"

  # R5: spec names

  Scenario: A spec name with a dot is looked up as itself
    Given the build "v1.7.4" is installed and pinned
    And a file "Foo.v2.tla" containing:
      """
      ---- MODULE Foo ----
      ====
      """
    And java replays "tlc/v1.7.4/success" with exit code 0
    When I run "tlaup tlc Foo.v2"
    Then the exit code is 0
    And java was started with "{work}/Foo.v2.tla"

  # R6: run folders

  Scenario: A run that succeeds leaves no run folder and no lock file
    Given the build "v1.7.4" is installed and pinned
    And a spec "Success" from the golden specs
    And java replays "tlc/v1.7.4/success" with exit code 0
    When I run "tlaup tlc Success"
    Then the exit code is 0
    And the cache holds no run folders
    And the cache holds no lock files

  Scenario: A run that fails leaves no run folder and no lock file
    Given the build "v1.7.4" is installed and pinned
    And a spec "Violation" from the golden specs
    And java replays "tlc/v1.7.4/violation" with exit code 12
    When I run "tlaup tlc Violation"
    Then the exit code is 12
    And the cache holds no run folders
    And the cache holds no lock files

  Scenario: Under --keep a crash after a complete checkpoint keeps the run folder and says how to resume
    Given the build "v1.7.4" is installed and pinned
    And a spec "Slow" from the golden specs
    And java replays "tlc/v1.7.4/checkpoint-run" with exit code 255
    And java writes "queue.chkpt, vars.chkpt" into its metadir
    When I run "tlaup tlc Slow --keep --cfg Slow.cfg -- -checkpoint 1"
    Then the exit code is 255
    And the cache holds 1 run folder
    And stderr contains "Checkpoint kept (" 1 times
    And stderr contains "TLC crashed (exit 255)"
    And stderr contains "): {kept}"
    And stderr contains "Resume with: tlaup tlc {work}/Slow.tla --cfg {work}/Slow.cfg --keep"
    And stderr contains "-checkpoint 1"
    And stderr contains "-fp "
    And stderr contains "-seed "
    And stderr contains "-recover {kept}/"
    And stdout does not contain "Checkpoint kept"

  Scenario: Under --keep a violation leaves nothing
    Given the build "v1.7.4" is installed and pinned
    And a spec "Violation" from the golden specs
    And java replays "tlc/v1.7.4/violation" with exit code 12
    And java writes "queue.chkpt, vars.chkpt" into its metadir
    When I run "tlaup tlc Violation --keep"
    Then the exit code is 12
    And the cache holds no run folders
    And stderr does not contain "Checkpoint kept"

  Scenario: Without --keep a crash leaves nothing, and the result line names --keep
    Given the build "v1.7.4" is installed and pinned
    And a spec "Slow" from the golden specs
    And java replays "tlc/v1.7.4/checkpoint-run" with exit code 255
    And java writes "queue.chkpt, vars.chkpt" into its metadir
    When I run "tlaup tlc Slow"
    Then the exit code is 255
    And the cache holds no run folders
    And the cache holds no lock files
    And stdout contains "a checkpoint was not kept (use --keep to keep one)" 1 times
    And stderr does not contain "Checkpoint kept"

  Scenario: The setting tlc.keep keeps the run folder without the flag
    Given the build "v1.7.4" is installed and pinned
    And a spec "Slow" from the golden specs
    And the environment variable "TLAUP_TLC_KEEP" is "1"
    And java replays "tlc/v1.7.4/checkpoint-run" with exit code 255
    And java writes "queue.chkpt, vars.chkpt" into its metadir
    When I run "tlaup tlc Slow"
    Then the exit code is 255
    And the cache holds 1 run folder
    And stderr contains "Checkpoint kept (" 1 times

  Scenario Outline: Under --keep an incomplete checkpoint leaves nothing: <files>
    Given the build "v1.7.4" is installed and pinned
    And a spec "Slow" from the golden specs
    And java replays "tlc/v1.7.4/checkpoint-run" with exit code 255
    And java writes "<files>" into its metadir
    When I run "tlaup tlc Slow --keep"
    Then the exit code is 255
    And the cache holds no run folders
    And stdout contains "the checkpoint was incomplete, nothing to resume" 1 times

    Examples:
      | files                         |
      | queue.chkpt, queue.tmp        |
      | queue.chkpt, settings.tmp.chkpt |

  Scenario: tlaup passes -fp and -seed when the arguments have neither
    Given the build "v1.7.4" is installed and pinned
    And a spec "Success" from the golden specs
    And java replays "tlc/v1.7.4/success" with exit code 0
    When I run "tlaup tlc Success"
    Then the exit code is 0
    And java was started with "-fp"
    And java was started with "-seed"

  Scenario: tlaup passes only its own -seed when the arguments have -fp
    Given the build "v1.7.4" is installed and pinned
    And a spec "Success" from the golden specs
    And java replays "tlc/v1.7.4/success" with exit code 0
    When I run "tlaup tlc Success --show-command -- -fp 3"
    Then stdout contains " -fp " 1 times
    And stdout contains " -fp 3 " 1 times
    And stdout contains " -seed " 1 times
    When I run "tlaup tlc Success -- -fp 3"
    Then the exit code is 0
    And java was started with "-seed"
    And java was started with "3"

  Scenario: Runs of two specs whose names start the same way do not disturb each other
    Given the build "v1.7.4" is installed and pinned
    And a file "Foo.tla" containing:
      """
      ---- MODULE Foo ----
      ====
      """
    And a file "Foo_bar.tla" containing:
      """
      ---- MODULE Foo_bar ----
      ====
      """
    And java replays "tlc/v1.7.4/checkpoint-run" with exit code 255
    And java writes "queue.chkpt, vars.chkpt" into its metadir
    When I run "tlaup tlc Foo_bar --keep"
    Then the cache holds 1 run folder
    Given java replays "tlc/v1.7.4/success" with exit code 0
    When I run "tlaup tlc Foo"
    Then the exit code is 0
    And the cache holds 1 run folder
    And the file "{kept}/run.json" contains "Foo_bar.tla"

  Scenario: With a kept folder in the cache every run reminds once, and --show-command does not
    Given the build "v1.7.4" is installed and pinned
    And a spec "Slow" from the golden specs
    And java replays "tlc/v1.7.4/checkpoint-run" with exit code 255
    And java writes "queue.chkpt, vars.chkpt" into its metadir
    When I run "tlaup tlc Slow --keep"
    Then the cache holds 1 run folder
    Given java replays "tlc/v1.7.4/success" with exit code 0
    When I run "tlaup tlc Slow"
    Then the exit code is 0
    And stderr contains "1 kept run folder holds " 1 times
    And stderr contains " (tlaup cache list)" 1 times
    When I run "tlaup tlc Slow --show-command"
    Then the exit code is 0
    And stderr does not contain "kept run folder"

  Scenario: Resuming a kept run passes its -fp and -seed and removes the folder when TLC finishes
    Given the build "v1.7.4" is installed and pinned
    And a spec "Slow" from the golden specs
    And java replays "tlc/v1.7.4/checkpoint-run" with exit code 255
    And java writes "queue.chkpt, vars.chkpt" into its metadir
    When I run "tlaup tlc Slow --keep -- -fp 3 -seed 7"
    Then the cache holds 1 run folder
    Given java replays "tlc/v1.7.4/checkpoint-recover" with exit code 0
    When I run "tlaup tlc Slow -- -recover {kept}/checkpoint"
    Then the exit code is 0
    # That the resumed start itself has the kept -fp and -seed is checked on the last start alone, by
    # test_the_drawn_fp_and_seed_are_recorded_repeated_and_passed_on_resume in tests/unit/cmd/test_tlc_command.py.
    And the cache holds no run folders
    And the cache holds no lock files

  Scenario: A resumed run that crashes again stays kept, and its resume command has one -recover
    Given the build "v1.7.4" is installed and pinned
    And a spec "Slow" from the golden specs
    And java replays "tlc/v1.7.4/checkpoint-run" with exit code 255
    And java writes "queue.chkpt, vars.chkpt" into its metadir
    When I run "tlaup tlc Slow --keep"
    Then the cache holds 1 run folder
    Given java replays "tlc/v1.7.4/checkpoint-recover" with exit code 255
    And java writes "queue.chkpt, vars.chkpt" into its metadir
    When I run "tlaup tlc Slow -- -recover {kept}/checkpoint"
    Then the exit code is 255
    And the cache holds 1 run folder
    And stderr contains "Checkpoint kept (" 1 times
    And stderr contains "-recover" 1 times

  Scenario: Resuming with a -metadir of one's own still removes the kept folder and makes none
    Given the build "v1.7.4" is installed and pinned
    And a spec "Slow" from the golden specs
    And java replays "tlc/v1.7.4/checkpoint-run" with exit code 255
    And java writes "queue.chkpt, vars.chkpt" into its metadir
    When I run "tlaup tlc Slow --keep"
    Then the cache holds 1 run folder
    Given java replays "tlc/v1.7.4/checkpoint-recover" with exit code 0
    When I run "tlaup tlc Slow -- -metadir {work}/m -recover {kept}/checkpoint"
    Then the exit code is 0
    And the cache holds no run folders
    And java was started with "{work}/m"

  Scenario: Adding a module leaves a kept run folder alone
    Given the build "v1.7.4" is installed and pinned
    And a spec "Slow" from the golden specs
    And java replays "tlc/v1.7.4/checkpoint-run" with exit code 255
    And java writes "queue.chkpt, vars.chkpt" into its metadir
    When I run "tlaup tlc Slow --keep"
    Then the cache holds 1 run folder
    Given a module source "TlaOnly" from the fake sources
    When I run "tlaup module add TlaOnly"
    Then the exit code is 0
    And the cache holds 1 run folder

  # R7 (with 35) and C6 (with 33): relative module paths and the run folder under the cache

  Scenario: Relative module paths in the config are read from the folder tlaup runs in
    Given the build "v1.7.4" is installed and pinned
    And I am in the folder "{work}/proj"
    And a spec "Success" from the golden specs
    And I am in the folder "{work}"
    And the config file contains:
      """
      module_path: mods
      module_lib_path: jars
      """
    And a file "mods/Extra.tla" containing:
      """
      ---- MODULE Extra ----
      ====
      """
    And a file "jars/extra.jar" containing:
      """
      not read
      """
    And java replays "tlc/v1.7.4/success" with exit code 0
    When I run "tlaup tlc proj/Success -- -fp 3 -seed 7"
    Then the exit code is 0
    And the java command matches the expected file "tlc_run/module-path-relative.txt"

  # R7: override classes and the pinned build

  Scenario: A registered override class v1.7.4 will not load is warned about, and Java still starts
    Given the build "v1.7.4" is installed and pinned
    And a module source "Queue" from the fake sources
    When I run "tlaup module add Queue"
    Given a spec "Success" from the golden specs
    And java replays "tlc/v1.7.4/success" with exit code 0
    When I run "tlaup tlc Success"
    Then the exit code is 0
    And stderr contains "warning: " 1 times
    And stderr contains "tlc2.overrides.DirectOverrides (module Queue) will not load"
    And java ran "tlc2.TLC" 1 time

  Scenario: On a rolling build a registered class and a project's TLCOverrides are both named, with no warning
    Given the build "rolling" is installed and pinned
    And a module source "Queue" from the fake sources
    When I run "tlaup module add Queue"
    Given a spec "Success" from the golden specs
    And a file "classes/tlc2/overrides/TLCOverrides.class" containing:
      """
      not a class file
      """
    And java replays "tlc/2026.11.15.002146/success" with exit code 0
    When I run "tlaup tlc Success"
    Then the exit code is 0
    And stderr does not contain "warning:"
    And java was started with "-Dtlc2.overrides.TLCOverrides=tlc2.overrides.TLCOverrides:tlc2.overrides.DirectOverrides"

  # M20: two registered modules on a rolling build

  Scenario: Two registered modules' override classes are named in one property, in the registry's order
    Given the build "rolling" is installed and pinned
    And a module source "Queue" from the fake sources
    And a module source "Stack" from the fake sources
    When I run "tlaup module add Stack"
    And I run "tlaup module add Queue"
    Given a spec "Success" from the golden specs
    And java replays "tlc/2026.11.15.002146/success" with exit code 0
    When I run "tlaup tlc Success"
    Then the exit code is 0
    And java was started with "-Dtlc2.overrides.TLCOverrides=tlc2.overrides.DirectOverrides:tlc2.overrides.InheritedOverrides"

  # R8: TLC's own arguments and workers

  Scenario: Arguments after -- reach TLC before the spec, with one -workers
    Given the build "v1.7.4" is installed and pinned
    And a spec "Success" from the golden specs
    And java replays "tlc/v1.7.4/success" with exit code 0
    When I run "tlaup tlc Success -- -workers 4 -deadlock -fp 3 -seed 7"
    Then the exit code is 0
    And the java command matches the expected file "tlc_run/workers-after-dashes.txt"

  Scenario: --workers auto is passed as -workers auto
    Given the build "v1.7.4" is installed and pinned
    And a spec "Success" from the golden specs
    And java replays "tlc/v1.7.4/success" with exit code 0
    When I run "tlaup tlc Success --workers 2"
    Then java was started with "2"
    Given java replays "tlc/v1.7.4/success" with exit code 0
    When I run "tlaup tlc Success --workers auto"
    Then the exit code is 0
    And java was started with "auto"

  Scenario: With nothing given TLC runs with -workers auto from the setting
    Given the build "v1.7.4" is installed and pinned
    And a spec "Success" from the golden specs
    And java replays "tlc/v1.7.4/success" with exit code 0
    When I run "tlaup tlc Success"
    Then the exit code is 0
    And java was started with "-workers"
    And java was started with "auto"

  # J1: Java options

  Scenario Outline: Java options come from the settings, then TLAUP_JAVA_OPTS, then --java-opt: <form>
    Given the build "v1.7.4" is installed and pinned
    And a spec "Success" from the golden specs
    And the environment variable "TLAUP_JAVA_OPTS" is "-Xmx2g -Dx="a b""
    And the environment variable "JAVA_OPTS" is "-Xmx1g"
    And java replays "tlc/v1.7.4/success" with exit code 0
    When I run "tlaup tlc Success <form> -- -fp 3 -seed 7"
    Then the exit code is 0
    And the java command matches the expected file "tlc_run/java-opts.txt"
    And java was started without "-Xmx1g"

    Examples:
      | form              |
      | --java-opt=-Xss8m |
      | --java-opt -Xss8m |

  # J2, handed over by 20: JAVA_HOME first

  Scenario: java is taken from JAVA_HOME although another is on PATH
    Given the build "v1.7.4" is installed and pinned
    And a spec "Success" from the golden specs
    And JAVA_HOME is a JDK of version "21.0.2"
    And java replays "tlc/v1.7.4/success" with exit code 0
    When I run "tlaup tlc Success"
    Then the exit code is 0
    And java ran from JAVA_HOME

  Scenario: An empty JAVA_HOME gives one warning and java is taken from PATH
    Given the build "v1.7.4" is installed and pinned
    And a spec "Success" from the golden specs
    And JAVA_HOME is an empty folder
    And java replays "tlc/v1.7.4/success" with exit code 0
    When I run "tlaup tlc Success"
    Then the exit code is 0
    And stderr contains "warning:" 1 times
    And java ran from PATH

  # J3, handed over by 20; inventory row R2: one version check, before the run

  Scenario: A run starts java twice: the version check first, then TLC, never TLC's own -version
    Given the build "v1.7.4" is installed and pinned
    And a spec "Success" from the golden specs
    And java replays "tlc/v1.7.4/success" with exit code 0
    When I run "tlaup tlc Success"
    Then the exit code is 0
    And java was started 2 times
    And java ran "-version" 1 time
    And java ran "tlc2.TLC" 1 time

  Scenario: A version check that does not give a version warns, and the run goes on (inventory row J2)
    Given the build "v1.7.4" is installed and pinned
    And a spec "Success" from the golden specs
    And java answers its version check with "some text that is not a version" on stderr and exit code 0
    And java replays "tlc/v1.7.4/success" with exit code 0
    When I run "tlaup tlc Success"
    Then the exit code is 0
    And stderr contains "warning:" 1 times
    And java ran "tlc2.TLC" 1 time

  # F4, handed over by 44: a broken config file

  Scenario: With a value of the wrong type in the config file, tlc exits 3 and names the key
    Given the build "v1.7.4" is installed and pinned
    And a spec "Success" from the golden specs
    And the config file contains:
      """
      tlc:
        refresh_interval: fast
      """
    When I run "tlaup tlc Success"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "tlc.refresh_interval"
    And stderr does not contain "Traceback"
    And java was not started
