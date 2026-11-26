Feature: The first run with no tools installed
  With no tools installed, a run asks whether to install the stable release or the rolling build, or takes the
  answer from --auto-install or TLAUP_AUTO_INSTALL, installs it and carries on. The spec is checked first, and
  --show-command never asks or installs (design 12 V9, decision D45). In-process the streams are not terminals,
  so nothing is ever asked.

  Background:
    Given no build is installed
    And a spec "Success" from the golden specs
    And GitHub answers from "releases"

  Scenario: TLAUP_AUTO_INSTALL installs and pins the build, and the run goes on
    Given the environment variable "TLAUP_AUTO_INSTALL" is "rolling"
    And java replays "tlc/2026.11.15.002146/success" with exit code 0
    When I run "tlaup tlc Success --coverage -- -deadlock"
    Then the exit code is 0
    And stderr contains "Installing rolling from "
    And the pinned build is "rolling"
    And java ran "tlc2.TLC" 1 time
    And java was started with "-coverage"
    And java was started with "-deadlock"
    And java was started with "{work}/Success.tla"

  Scenario: --auto-install installs and pins the build, and the run goes on
    Given java replays "tlc/v1.7.4/success" with exit code 0
    When I run "tlaup tlc Success --auto-install stable"
    Then the exit code is 0
    And the pinned build is "v1.7.4"
    And java ran "tlc2.TLC" 1 time

  Scenario Outline: An answer other than stable or rolling is a usage error: <how>
    Given the environment variable "TLAUP_AUTO_INSTALL" is "<variable>"
    When I run "tlaup tlc Success <option>"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "error:" 1 times
    And 0 requests were sent to GitHub
    And java was not started

    Examples:
      | how          | variable | option                 |
      | the option   |          | --auto-install nightly |
      | the variable | nightly  |                        |

  Scenario Outline: A spec that does not exist exits 4 before anything is installed: <variable>
    Given the environment variable "TLAUP_AUTO_INSTALL" is "<variable>"
    When I run "tlaup tlc Nosuch"
    Then the exit code is 4
    And stderr contains "error:" 1 times
    And 0 requests were sent to GitHub
    And the installed builds are:
      | build |

    Examples:
      | variable |
      |          |
      | rolling  |

  Scenario Outline: --show-command with nothing installed exits 3 and installs nothing: <variable>
    Given the environment variable "TLAUP_AUTO_INSTALL" is "<variable>"
    When I run "tlaup tlc Success --show-command"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr contains "no TLA+ tools installed"
    And 0 requests were sent to GitHub
    And the installed builds are:
      | build |

    Examples:
      | variable |
      |          |
      | rolling  |

  Scenario: Nothing installed and no answer exits 3, since nothing can be asked
    When I run "tlaup tlc Success"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "error: no TLA+ tools installed" 1 times
    And stderr contains "TLAUP_AUTO_INSTALL"
    And 0 requests were sent to GitHub

  Scenario: Builds installed and none pinned exits 3 with the names to pin, and no request
    Given the build "v1.7.4" is installed
    And the environment variable "TLAUP_AUTO_INSTALL" is "rolling"
    When I run "tlaup tlc Success"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "hint: run `tlaup tool pin <one of: v1.7.4"
    And 0 requests were sent to GitHub
    And no build is pinned
