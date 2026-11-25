Feature: Uninstalling TLA+ tools builds
  Every argument is resolved before anything is removed; a name matching several builds asks which on a
  terminal and removes them all with --yes or without one; removing the pinned build clears the pin, which
  never moves to another build (design 12 V3, 23 C1, C2). No scenario here asks GitHub.

  Scenario: --all --yes removes every build and the pin
    Given the build "rolling" is installed
    And the build "v1.8.0" is installed and pinned
    And the build "v1.7.4" is installed
    When I run "tlaup tool uninstall --all --yes"
    Then the exit code is 0
    And stdout is empty
    And stderr matches the expected file "tool_uninstall/all.txt"
    And the installed builds are:
      | build |
    And no build is pinned

  Scenario: Two named builds with the pinned one first are both removed
    Given the build "v1.7.4" is installed and pinned
    And the build "rolling" is installed
    When I run "tlaup tool uninstall v1.7.4 rolling"
    Then the exit code is 0
    And the installed builds are:
      | build |
    And no build is pinned

  Scenario: Removing a build that is not pinned leaves the pin alone
    Given the build "v1.7.4" is installed and pinned
    And the build "rolling" is installed
    When I run "tlaup tool uninstall rolling"
    Then the exit code is 0
    And stderr is exactly "Removed rolling@bc1b506"
    And the installed builds are:
      | build          |
      | v1.7.4@5a47802 |
    And the pinned build is "v1.7.4"

  Scenario: A build that cannot be removed fails with 5, keeps the pin, and the others go
    # The folder is v1.7.4's build id: its name and the first 12 digits of its jar's SHA-256.
    Given the build "v1.7.4" is installed and pinned
    And the build "rolling" is installed
    And the folder "{tools}/v1.7.4-f98975750260" is read-only
    When I run "tlaup tool uninstall v1.7.4 rolling"
    Then the exit code is 5
    And stderr contains "v1.7.4@5a47802 was not removed: "
    And stderr contains "Removed rolling@bc1b506"
    And the installed builds are:
      | build          |
      | v1.7.4@5a47802 |
    And the pinned build is "v1.7.4"

  Scenario: Removing the pinned build leaves nothing pinned, and tool current then exits 3
    Given the build "v1.7.4" is installed and pinned
    And the build "rolling" is installed
    When I run "tlaup tool uninstall v1.7.4"
    Then the exit code is 0
    And stderr matches the expected file "tool_uninstall/unpinned.txt"
    And no build is pinned
    When I run "tlaup tool current"
    Then the exit code is 3
    And stdout is empty

  # Several builds of one name (V3's table)

  Scenario: On a terminal a wrong answer asks again, and the number chosen is removed
    Given the build "rolling" is installed
    And the build "rolling@1a2b3c4" is installed
    When I run "tlaup tool uninstall rolling" in a terminal 200 by 30 and answer "-1, 7, 2"
    Then the exit code is 0
    And stderr contains "Which build should be removed (a number, or all)? [all]" 3 times
    And the installed builds are:
      | build           |
      | rolling@1a2b3c4 |

  Scenario: On a terminal the answer all removes every build of the name
    Given the build "rolling" is installed
    And the build "rolling@1a2b3c4" is installed
    When I run "tlaup tool uninstall rolling" in a terminal 100 by 30 and answer "all"
    Then the exit code is 0
    And the installed builds are:
      | build |

  Scenario: On a terminal an empty answer is all, the default
    Given the build "rolling" is installed
    And the build "rolling@1a2b3c4" is installed
    When I run "tlaup tool uninstall rolling" in a terminal 100 by 30 and answer ""
    Then the exit code is 0
    And the installed builds are:
      | build |

  Scenario: --yes removes every build of the name without asking
    Given the build "rolling" is installed
    And the build "rolling@1a2b3c4" is installed
    When I run "tlaup tool uninstall rolling --yes"
    Then the exit code is 0
    And stderr does not contain "Which build"
    And the installed builds are:
      | build |

  Scenario: Without a terminal every build of the name is removed
    Given the build "rolling" is installed
    And the build "rolling@1a2b3c4" is installed
    When I run "tlaup tool uninstall rolling"
    Then the exit code is 0
    And stderr does not contain "Which build"
    And the installed builds are:
      | build |

  Scenario: On a terminal with stderr redirected the question could not be seen, so all are removed
    Given the build "rolling" is installed
    And the build "rolling@1a2b3c4" is installed
    When I run "tlaup tool uninstall rolling" in a terminal 100 by 30 with stderr redirected to "{work}/err.txt"
    Then the exit code is 0
    And the file "{work}/err.txt" contains "Removed rolling@1a2b3c4"
    And the installed builds are:
      | build |

  Scenario Outline: A build named by its commit removes that one only: <command>
    Given the build "rolling" is installed
    And the build "rolling@1a2b3c4" is installed
    When I run "<command>"
    Then the exit code is 0
    And the installed builds are:
      | build           |
      | rolling@bc1b506 |

    Examples:
      | command                                   |
      | tlaup tool uninstall rolling@1a2b3c4       |
      | tlaup tool uninstall rolling@1a2b3c4 --yes |

  Scenario: A build named by its commit removes that one only, on a terminal
    Given the build "rolling" is installed
    And the build "rolling@1a2b3c4" is installed
    When I run "tlaup tool uninstall rolling@1a2b3c4" in a terminal 100 by 30
    Then the exit code is 0
    And the terminal does not contain "Which build"
    And the installed builds are:
      | build           |
      | rolling@bc1b506 |

  # --all (V3's second table)

  Scenario: --all on a terminal answered n removes nothing
    Given the build "v1.7.4" is installed and pinned
    When I run "tlaup tool uninstall --all" in a terminal 100 by 30 and answer "n"
    Then the exit code is 0
    And the terminal contains "Remove all 1 installed build (y/n)? [n]"
    And the terminal contains "nothing removed"
    And the installed builds are:
      | build          |
      | v1.7.4@5a47802 |
    And the pinned build is "v1.7.4"

  Scenario: --all without a terminal and without --yes is a usage error
    Given the build "v1.7.4" is installed and pinned
    When I run "tlaup tool uninstall --all"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "error: `--all` asks for confirmation and there is no terminal; add `--yes`"
    And the installed builds are:
      | build          |
      | v1.7.4@5a47802 |

  Scenario Outline: --all with nothing installed says so and exits 0: <command>
    Given no build is installed
    When I run "<command>"
    Then the exit code is 0
    And stderr is exactly "no builds are installed"

    Examples:
      | command                          |
      | tlaup tool uninstall --all       |
      | tlaup tool uninstall --all --yes |

  # The arguments

  Scenario: An argument that matches nothing removes nothing, and names it
    Given the build "v1.8.0" is installed and pinned
    When I run "tlaup tool uninstall v1.8.0 nosuch"
    Then the exit code is 4
    And stdout is empty
    And stderr contains "error: nosuch is not installed"
    And the installed builds are:
      | build          |
      | v1.8.0@bc1b506 |

  Scenario Outline: Neither a version nor --all, or both, is one usage error: <command>
    Given the build "v1.7.4" is installed and pinned
    When I run "<command>"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "error:" 1 times
    And the installed builds are:
      | build          |
      | v1.7.4@5a47802 |

    Examples:
      | command                           |
      | tlaup tool uninstall              |
      | tlaup tool uninstall v1.7.4 --all |

  Scenario Outline: Every form of a version names the same build: <version>
    Given the build "v1.7.4" is installed
    And the build "rolling" is installed and pinned
    When I run "tlaup tool uninstall <version>"
    Then the exit code is 0
    And the installed builds are:
      | build           |
      | rolling@bc1b506 |

    Examples:
      | version        |
      | v1.7.4         |
      | 1.7.4          |
      | stable         |
      | v1.7.4@5a47802 |
