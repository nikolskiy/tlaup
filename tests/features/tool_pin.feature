Feature: Pinning a build, and showing what is pinned
  "tool pin" pins an installed build and asks which only on a terminal; "tool current" shows the pinned build
  and its jar without Java; "tool path" prints a build's jar and never asks; "tool dir" prints the tools folder
  (design 12 V4, 02 X3, 23 C1, C2).

  Scenario: A tag can be typed without the v
    Given the build "v1.7.4" is installed
    And the build "rolling" is installed and pinned
    When I run "tlaup tool pin 1.7.4"
    Then the exit code is 0
    And stdout is empty
    And stderr is exactly "Pinned v1.7.4@5a47802"
    And the pinned build is "v1.7.4"

  Scenario: tag@commit pins one of several builds of a name
    Given the build "rolling" is installed and pinned
    And the build "rolling@1a2b3c4" is installed
    When I run "tlaup tool pin rolling@1a2b3c4"
    Then the exit code is 0
    And the pinned build is "rolling@1a2b3c4"

  Scenario: A name matching several builds without a terminal is a usage error listing them
    Given the build "rolling" is installed and pinned
    And the build "rolling@1a2b3c4" is installed
    When I run "tlaup tool pin rolling"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr contains "rolling@1a2b3c4, rolling@bc1b506"
    And the pinned build is "rolling@bc1b506"

  Scenario: A version that is not installed is not found, and the hint says how to install it
    Given the build "v1.7.4" is installed and pinned
    When I run "tlaup tool pin v1.8.0"
    Then the exit code is 4
    And stdout is empty
    And stderr contains "error: v1.8.0 is not installed"
    And stderr contains "tlaup tool install v1.8.0"
    And the pinned build is "v1.7.4"

  Scenario: On a terminal a name matching several builds asks which, and the answer is pinned
    Given the build "rolling" is installed and pinned
    And the build "rolling@1a2b3c4" is installed
    When I run "tlaup tool pin rolling" in a terminal 100 by 30 and answer "1"
    Then the exit code is 0
    And the terminal contains "Which build should be pinned?"
    And the terminal contains "1. rolling@1a2b3c4"
    And the pinned build is "rolling@1a2b3c4"

  Scenario: On a terminal with stderr redirected the question cannot be seen, so it is a usage error
    Given the build "rolling" is installed and pinned
    And the build "rolling@1a2b3c4" is installed
    When I run "tlaup tool pin rolling" in a terminal 100 by 30 with stderr redirected to "{work}/err.txt"
    Then the exit code is 2
    And the file "{work}/err.txt" contains "error: rolling matches 2 installed builds"
    And the pinned build is "rolling@bc1b506"

  Scenario Outline: Every form of a version pins the same build: <version>
    Given the build "v1.7.4" is installed
    And the build "rolling" is installed and pinned
    When I run "tlaup tool pin <version>"
    Then the exit code is 0
    And the pinned build is "v1.7.4@5a47802"

    Examples:
      | version        |
      | v1.7.4         |
      | 1.7.4          |
      | stable         |
      | v1.7.4@5a47802 |

  # tool current, tool dir

  Scenario: tool current prints the pinned build with its build time, and its jar
    Given the build "rolling" is installed and pinned
    When I run "tlaup tool current"
    Then the exit code is 0
    And stderr is empty
    And stdout contains "rolling@bc1b506 (2026.11.15.002146)"
    And stdout contains "{tools}/"
    And stdout contains "/tla2tools.jar"

  Scenario: tool current with a build with no build time prints the build alone
    Given the build "v1.7.4" is installed and pinned
    When I run "tlaup tool current"
    Then the exit code is 0
    And stdout contains "v1.7.4@5a47802"
    And stdout does not contain "("

  Scenario Outline: tool current with nothing pinned exits 3, <what>
    Given <given>
    When I run "tlaup tool current"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "<error>"

    Examples:
      | what                  | given                          | error                         |
      | with a build          | the build "v1.7.4" is installed | error: no version pinned      |
      | with nothing installed | no build is installed          | error: no TLA+ tools installed |

  Scenario: tool current with the pinned build's folder removed exits 3
    Given the build "v1.7.4" is installed and pinned
    And no build is installed
    When I run "tlaup tool current"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "error: the pinned build is missing"

  Scenario: tool dir prints the tools folder and nothing else
    Given the build "v1.7.4" is installed and pinned
    When I run "tlaup tool dir"
    Then the exit code is 0
    And stdout is exactly "{tools}"
    And stderr is empty

  # tool path (inventory row T29)

  Scenario: tool path with no version prints the pinned build's jar and nothing else
    Given the build "v1.7.4" is installed
    And the build "rolling" is installed and pinned
    When I run "tlaup tool path"
    Then the exit code is 0
    And stdout is exactly "{tools}/rolling/tla2tools.jar"
    And stderr is empty

  Scenario Outline: Every form of a version gives the same jar: <version>
    Given the build "v1.7.4" is installed
    And the build "rolling" is installed and pinned
    When I run "tlaup tool path <version>"
    Then the exit code is 0
    And stdout is exactly "{tools}/v1.7.4/tla2tools.jar"
    And stderr is empty

    Examples:
      | version        |
      | v1.7.4         |
      | 1.7.4          |
      | stable         |
      | v1.7.4@5a47802 |

  Scenario: tool path with a version that is not installed is not found
    Given the build "v1.7.4" is installed and pinned
    When I run "tlaup tool path v1.8.0"
    Then the exit code is 4
    And stdout is empty
    And stderr contains "error: v1.8.0 is not installed"

  Scenario: tool path with a name matching several builds exits 2 and lists them
    Given the build "rolling" is installed and pinned
    And the build "rolling@1a2b3c4" is installed
    When I run "tlaup tool path rolling"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr contains "rolling@1a2b3c4, rolling@bc1b506"

  Scenario: tool path never asks, on a terminal either
    Given the build "rolling" is installed and pinned
    And the build "rolling@1a2b3c4" is installed
    When I run "tlaup tool path rolling" in a terminal 100 by 30
    Then the exit code is 2
    And the terminal contains "rolling@1a2b3c4, rolling@bc1b506"
    And the terminal does not contain "Which build"

  Scenario Outline: tool path with nothing pinned exits 3, <what>
    Given <given>
    When I run "tlaup tool path"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "<error>"

    Examples:
      | what                       | given                          | error                              |
      | with a build               | the build "v1.7.4" is installed | error: no version pinned           |
      | with nothing installed     | no build is installed          | error: no TLA+ tools installed     |

  Scenario: tool path with the pinned build's folder removed exits 3
    Given the build "v1.7.4" is installed and pinned
    And no build is installed
    When I run "tlaup tool path"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "error: the pinned build is missing"

  Scenario: tool path on a fresh home reads no settings and writes no config file (14 F1)
    Given no build is installed
    When I run "tlaup tool path"
    Then the exit code is 3
    And the file "{config}/config.yaml" does not exist
