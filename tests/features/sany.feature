Feature: Parsing a spec with SANY
  "tlaup sany SPEC [-- SANY arguments]" runs SANY in the spec's folder on the pinned build, prints each diagnostic once
  on stdout as path:line:col: severity: message with the lines of the spec around it, SANY's banner and progress on
  stderr, and exits 150 when the spec has an error (design 21 S1, decisions D29, D30, D55 and D66). The fake java
  replays the SANY golden captures.

  # S1, step 3 and 6: a good spec, each kind of finding, and the exit code

  Scenario Outline: A good spec gives no diagnostic and exit 0 on <build>
    Given the build "<build>" is installed and pinned
    And a spec "Good" from the golden specs
    And java replays "sany/<golden>/sany-good" with exit code 0
    When I run "tlaup sany Good"
    Then the exit code is 0
    And stdout is empty
    And stderr contains "no errors"
    And java ran "tla2sany.SANY" 1 time

    Examples:
      | build   | golden            |
      | v1.7.4  | v1.7.4            |
      | rolling | 2026.11.15.002146 |

  # Inventory row R20, for sany: the file, the line and the column of each error

  Scenario Outline: Two semantic errors give two lines in the editor form and exit 150 on <build>, whatever SANY's own code
    Given the build "<build>" is installed and pinned
    And a spec "SemErr" from the golden specs
    And java replays "sany/<golden>/sany-semerr" with exit code 0
    When I run "tlaup sany SemErr"
    Then the exit code is 150
    And stdout contains ": error: " 2 times
    And stdout contains "SemErr.tla:4:13: error: Unknown operator: `y'."
    And stdout contains "SemErr.tla:5:22: error: Unknown operator: `Foo'."
    And stderr contains "2 errors, 0 warnings"

    Examples:
      | build   | golden            |
      | v1.7.4  | v1.7.4            |
      | rolling | 2026.11.15.002146 |

  Scenario Outline: A parse error gives one line and exit 150 on <build>
    Given the build "<build>" is installed and pinned
    And a spec "ParseErr" from the golden specs
    And java replays "sany/<golden>/sany-parseerr" with exit code 255
    When I run "tlaup sany ParseErr"
    Then the exit code is 150
    And stdout contains ": error: " 1 times
    And stdout contains "ParseErr.tla:4:9: error: Was expecting"
    And stderr contains "1 error, 0 warnings"

    Examples:
      | build   | golden            |
      | v1.7.4  | v1.7.4            |
      | rolling | 2026.11.15.002146 |

  Scenario: A missing module on v1.7.4 gives one line with no position, and the line that came from SANY's stderr
    Given the build "v1.7.4" is installed and pinned
    And a spec "MissingMod" from the golden specs
    And java replays "sany/v1.7.4/sany-missingmod" with exit code 255
    When I run "tlaup sany MissingMod"
    Then the exit code is 150
    And stdout contains ": error: " 1 times
    And stdout contains "MissingMod.tla: error: Cannot find source file for module NoSuchModule"
    And stdout contains "File does not exist"

  Scenario: A missing module on the rolling build gives its message once, although SANY printed it twice
    Given the build "rolling" is installed and pinned
    And a spec "MissingMod" from the golden specs
    And java replays "sany/2026.11.15.002146/sany-missingmod" with exit code 255
    When I run "tlaup sany MissingMod"
    Then the exit code is 150
    And stdout contains ": error: " 1 times
    And stdout contains "MissingMod.tla: error: Cannot find source file for module NoSuchModule"
    And stdout contains "Cannot find source file for module NoSuchModule" 1 times

  # D55: message 4802 is an error, as TLC refuses such a spec with 150

  Scenario Outline: Message 4802 is an error on <build>, whatever SANY's own code
    Given the build "<build>" is installed and pinned
    And a spec "Warn4802" from the golden specs
    And java replays "sany/<golden>/sany-warn4802" with exit code 0
    When I run "tlaup sany Warn4802"
    Then the exit code is 150
    And stdout contains ": error: " 1 times

    Examples:
      | build   | golden            |
      | v1.7.4  | v1.7.4            |
      | rolling | 2026.11.15.002146 |

  Scenario Outline: The stale-PlusCal warning alone is a warning and exit 0: <case> on <build>
    Given the build "<build>" is installed and pinned
    And a spec "<golden>/<module>" from the golden specs
    And java replays "sany/<golden>/<case>" with exit code 0
    When I run "tlaup sany <module>"
    Then the exit code is 0
    And stdout contains ": warning: " 1 times
    And stdout does not contain ": error: "
    And stderr contains "0 errors, 1 warning"

    Examples:
      | build   | golden            | case           | module         |
      | v1.7.4  | v1.7.4            | sany-stale-alg | PcalStaleAlg   |
      | v1.7.4  | v1.7.4            | sany-stale-tla | PcalStaleTla   |
      | rolling | 2026.11.15.002146 | sany-stale-alg | PcalStaleAlg   |
      | rolling | 2026.11.15.002146 | sany-stale-tla | PcalStaleTla   |

  # SANY's arguments after --, and SANY's own refusal of a grouped flag

  Scenario Outline: A flag after -- reaches SANY and its own text and exit code come back on <build>
    Given the build "<build>" is installed and pinned
    And a spec "Good" from the golden specs
    And java replays "sany/<golden>/sany-grouped-unknown" with exit code 255
    When I run "tlaup sany Good -- -xy"
    Then the exit code is 255
    And java was started with "-xy"
    And stdout contains "<text>: -xy"

    Examples:
      | build   | golden            | text           |
      | v1.7.4  | v1.7.4            | Illegal switch |
      | rolling | 2026.11.15.002146 | Invalid option |

  # S1, step 7: -d would wait for input that tlaup does not give it; nothing else is looked at

  Scenario: -d is refused before anything is started
    Given the build "v1.7.4" is installed and pinned
    And a spec "Good" from the golden specs
    When I run "tlaup sany Good -- -d"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr contains "-d starts SANY's interactive explorer"
    And java was not started

  Scenario: -d with no build installed is a usage error, with no question and no request
    Given no build is installed
    And a spec "Good" from the golden specs
    And GitHub answers from "releases"
    When I run "tlaup sany Good -- -d"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "error:" 1 times
    And 0 requests were sent to GitHub
    And no build is pinned
    And java was not started

  Scenario: -d is refused with a missing spec too, before the spec is looked at
    Given the build "v1.7.4" is installed and pinned
    When I run "tlaup sany NoSuchSpec -- -d"
    Then the exit code is 2
    And stderr contains "error:" 1 times
    And stderr contains "-d starts SANY's interactive explorer"
    And java was not started

  Scenario: A group of flags that holds a d is not -d, and reaches SANY
    Given the build "v1.7.4" is installed and pinned
    And a spec "Good" from the golden specs
    And java replays "sany/v1.7.4/sany-good" with exit code 0
    When I run "tlaup sany Good -- -error-codes"
    Then the exit code is 0
    And java was started with "-error-codes"

  # D30 and D9: banner and progress on stderr, nothing of SANY's lost

  Scenario: The banner and the progress lines of a replay are on stderr, not on stdout
    Given the build "v1.7.4" is installed and pinned
    And a spec "SemErr" from the golden specs
    And java replays "sany/v1.7.4/sany-semerr" with exit code 0
    When I run "tlaup sany SemErr"
    Then stderr contains "SANY2 Version"
    And stderr contains "Semantic processing of module"
    And stdout does not contain "Parsing file"
    And stdout does not contain "SANY2 Version"
    And stdout does not contain "Semantic processing of module"

  # S1, step 2: the working folder is the spec's folder, and the file name is bare

  Scenario: SANY is started in the spec's folder with the bare file name, from another folder
    Given the build "v1.7.4" is installed and pinned
    And a file "specs/SemErr.tla" containing:
      """
      ---- MODULE SemErr ----
      ====
      """
    And java replays "sany/v1.7.4/sany-good" with exit code 0
    And I am in the folder "{work}/elsewhere"
    When I run "tlaup sany ../specs/SemErr"
    Then the exit code is 0
    And java was started with "SemErr.tla"
    And java was started without "../specs/SemErr.tla"
    And java was started in the folder "{work}/specs"

  Scenario: --java-opt is in the command that is run
    Given the build "v1.7.4" is installed and pinned
    And a spec "Good" from the golden specs
    And java replays "sany/v1.7.4/sany-good" with exit code 0
    When I run "tlaup sany Good --java-opt=-Xss8m"
    Then the exit code is 0
    And java was started with "-Xss8m"

  # D66, inventory row R21: the lines of the spec around each diagnostic with a location

  Scenario: Each diagnostic with a location is followed by the lines around it, the marks and the columns
    Given the build "v1.7.4" is installed and pinned
    And a file "SemErr.tla" containing:
      """
      ---- MODULE SemErr ----
      EXTENDS Naturals
      VARIABLE x
      Init == x = y
      Next == x' = x + 1 + Foo(2)
      ====
      """
    And java replays "sany/v1.7.4/sany-semerr" with exit code 0
    And java's output has "<tmp>/q12/work-v1.7.4" replaced by "{work}"
    When I run "tlaup sany SemErr"
    Then the exit code is 150
    And stdout matches the expected file "sany/semerr.txt"

  Scenario: With the file not where SANY said, the editor-form lines stand alone
    Given the build "v1.7.4" is installed and pinned
    And a spec "SemErr" from the golden specs
    And java replays "sany/v1.7.4/sany-semerr" with exit code 0
    When I run "tlaup sany SemErr"
    Then the exit code is 150
    And stdout contains ": error: " 2 times
    And stdout does not contain "Error here"
    And stdout does not contain " | "
    And stderr contains "error:" 0 times

  # R11, the order of the preflight: the same steps as tlc

  Scenario: A missing spec is not found, and java is not started
    Given the build "v1.7.4" is installed and pinned
    When I run "tlaup sany NoSuchSpec"
    Then the exit code is 4
    And stdout is empty
    And stderr contains "error:" 1 times
    And java was not started

  Scenario: With no build installed nothing can be asked in-process, and java is not started
    Given no build is installed
    And a spec "Good" from the golden specs
    And GitHub answers from "releases"
    When I run "tlaup sany Good"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "error:" 1 times
    And 0 requests were sent to GitHub
    And java was not started

  Scenario: With no build installed and a missing spec the spec is reported
    Given no build is installed
    And GitHub answers from "releases"
    When I run "tlaup sany NoSuchSpec"
    Then the exit code is 4
    And 0 requests were sent to GitHub
    And java was not started

  Scenario: Java that is not installed is a setup error, and SANY is not run
    Given the build "v1.7.4" is installed and pinned
    And a spec "Good" from the golden specs
    And java is not installed
    When I run "tlaup sany Good"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "error:" 1 times
    And java did not run "tla2sany.SANY"

  Scenario: An unbalanced quote in TLAUP_JAVA_OPTS is a usage error before the spec is looked at
    Given the build "v1.7.4" is installed and pinned
    And the environment variable "TLAUP_JAVA_OPTS" is "-Dx="a b"
    When I run "tlaup sany NoSuchSpec"
    Then the exit code is 2
    And stderr contains "TLAUP_JAVA_OPTS"
    And java was not started

  Scenario: A bad --auto-install is a usage error before the spec is looked at
    Given no build is installed
    And GitHub answers from "releases"
    When I run "tlaup sany NoSuchSpec --auto-install nonsense"
    Then the exit code is 2
    And stderr contains "error:" 1 times
    And 0 requests were sent to GitHub
    And java was not started
