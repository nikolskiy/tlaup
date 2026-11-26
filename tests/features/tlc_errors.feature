Feature: What tlaup tlc checks before it starts TLC
  One preflight checks, in this order, the command line, the spec, a named cfg, the tools build and Java, and
  stops at the first problem with one error: line on stderr, nothing on stdout, the code of 02 X1 and no start of
  TLC (design 11 R11, decision D45, 23 C1). In-process, nothing can be asked.

  Background:
    Given a spec "Success" from the golden specs

  # R11, step 0: the command line and the environment

  Scenario Outline: A tlaup option and the same flag after -- cannot be used together: <options>
    Given the build "v1.7.4" is installed and pinned
    When I run "tlaup tlc Success <options>"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr contains "cannot be used together"
    And java was not started

    Examples:
      | options                    |
      | --workers 2 -- -workers 4  |
      | --coverage -- -coverage 1  |
      | --cfg a -- -config b       |

  Scenario Outline: --workers takes auto or a positive integer, not <value>
    Given the build "v1.7.4" is installed and pinned
    When I run "tlaup tlc Success --workers <value>"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr contains "--workers must be auto or a positive integer"
    And java was not started

    Examples:
      | value |
      | 0     |
      | x     |
      | +3    |

  Scenario: An unbalanced quote in TLAUP_JAVA_OPTS is a usage error that names the variable
    Given the build "v1.7.4" is installed and pinned
    And the environment variable "TLAUP_JAVA_OPTS" is "-Dx="a b"
    When I run "tlaup tlc Success"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr contains "TLAUP_JAVA_OPTS"
    And java was not started

  # R11, step 1: the spec (R5)

  Scenario: A spec that does not exist exits 4 and names a path that was tried
    Given the build "v1.7.4" is installed and pinned
    When I run "tlaup tlc Nosuch"
    Then the exit code is 4
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr contains "{work}/Nosuch.tla"
    And java was not started

  Scenario: The current folder is not a spec
    Given the build "v1.7.4" is installed and pinned
    When I run "tlaup tlc ."
    Then the exit code is 2
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr does not contain "Traceback"
    And java was not started

  Scenario: A file that is not a spec is not passed to TLC
    Given the build "v1.7.4" is installed and pinned
    When I run "tlaup tlc Success.cfg"
    Then the exit code is 4
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr contains "hint: did you mean Success.tla?"
    And java was not started

  Scenario: A folder alone is not a spec
    Given the build "v1.7.4" is installed and pinned
    And a file "proj/Other.tla" containing:
      """
      ---- MODULE Other ----
      ====
      """
    When I run "tlaup tlc proj"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "error:" 1 times
    And java was not started

  # R11, step 2: the cfg

  Scenario: A --cfg that does not exist exits 4 with the paths tried
    Given the build "v1.7.4" is installed and pinned
    When I run "tlaup tlc Success --cfg nosuch"
    Then the exit code is 4
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr contains "nosuch.cfg"
    And java was not started

  Scenario: With no --cfg and no cfg beside the spec, TLC is started and its code passes through
    Given the build "v1.7.4" is installed and pinned
    And a spec "NoCfg" from the golden specs
    And java replays "tlc/v1.7.4/tool-nocfg" with exit code 255
    When I run "tlaup tlc NoCfg"
    Then the exit code is 255
    And java ran "tlc2.TLC" 1 time

  # R11, step 3: the tools build

  Scenario: Nothing installed, and nothing can be asked, exits 3
    Given no build is installed
    When I run "tlaup tlc Success"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr contains "TLAUP_AUTO_INSTALL"
    And java was not started

  Scenario: Builds installed and none pinned exits 3 and names tool pin
    Given the build "v1.7.4" is installed
    When I run "tlaup tlc Success"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr contains "hint: run `tlaup tool pin"
    And java was not started

  Scenario: A pin that names a build that is gone exits 3 and names a command
    Given a file "{tools}/pin" containing:
      """
      v1.7.4-0123456789ab
      """
    When I run "tlaup tlc Success"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr contains "hint: run `tlaup tool"
    And java was not started

  # R11, step 4: Java (inventory row J3)

  Scenario Outline: A Java that cannot run TLC exits 3: <java>
    Given the build "v1.7.4" is installed and pinned
    And <java>
    When I run "tlaup tlc Success"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "error:" 1 times
    And java did not run "tlc2.TLC"

    Examples:
      | java                                                                                          |
      | java is not installed                                                                         |
      | java is not executable                                                                        |
      | java is version "1.8.0_202"                                                                   |
      | java answers its version check with "Unable to locate a Java Runtime." on stderr and exit code 1 |

  # R11, the order of the checks

  Scenario: With nothing installed a missing spec exits 4 before anything is asked of GitHub
    Given no build is installed
    And GitHub answers from "releases"
    And the environment variable "TLAUP_AUTO_INSTALL" is "rolling"
    When I run "tlaup tlc Nosuch"
    Then the exit code is 4
    And stdout is empty
    And stderr contains "error:" 1 times
    And 0 requests were sent to GitHub
    And no build is pinned

  Scenario: With nothing installed conflicting -workers exits 2 and nothing is asked
    Given no build is installed
    When I run "tlaup tlc Success --workers 2 -- -workers 4"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr does not contain "Which build"
    And java was not started

  # R11 and inventory row R12: --show-command goes through the same checks, with the same message

  Scenario Outline: <what> stops a run and --show-command alike: <flags>
    Given the build "v1.7.4" is <state>
    And java is version "<java>"
    When I run "tlaup tlc <command> <flags>"
    Then the exit code is <code>
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr contains "<message>"
    And java did not run "tlc2.TLC"

    Examples:
      | what            | state                | java      | command              | flags          | code | message           |
      | a missing spec  | installed            | 21.0.2    | Nosuch               |                | 4    | Nosuch            |
      | a missing spec  | installed            | 21.0.2    | Nosuch               | --show-command | 4    | Nosuch            |
      | a missing cfg   | installed and pinned | 21.0.2    | Success --cfg nosuch |                | 4    | nosuch.cfg        |
      | a missing cfg   | installed and pinned | 21.0.2    | Success --cfg nosuch | --show-command | 4    | nosuch.cfg        |
      | no pinned build | installed            | 21.0.2    | Success              |                | 3    | no version pinned |
      | no pinned build | installed            | 21.0.2    | Success              | --show-command | 3    | no version pinned |
      | an old Java     | installed and pinned | 1.8.0_202 | Success              |                | 3    | is version 8      |
      | an old Java     | installed and pinned | 1.8.0_202 | Success              | --show-command | 3    | is version 8      |

  # T5 and 02 X1 rule 7: Typer's own usage errors

  Scenario: A mistyped option is Typer's usage error, not an error: line
    Given the build "v1.7.4" is installed and pinned
    When I run "tlaup tlc Success --coverge"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "No such option"
    And stderr contains "Usage:"
    And stderr does not contain "error:"
    And java was not started

  Scenario: A missing SPEC is Typer's usage error, not an error: line
    Given the build "v1.7.4" is installed and pinned
    When I run "tlaup tlc"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "Missing argument"
    And stderr contains "Usage:"
    And stderr does not contain "error:"
    And java was not started

  # C1: what is left of the removed options

  Scenario Outline: tlaup tlc <option> is gone
    Given the build "v1.7.4" is installed and pinned
    When I run "tlaup tlc <option>"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "No such option"
    And java was not started

    Examples:
      | option    |
      | --cleanup |
      | --version |
