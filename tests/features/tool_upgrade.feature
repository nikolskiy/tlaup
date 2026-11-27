Feature: Upgrading a name to what upstream publishes now
  "tool upgrade" compares the newest installed build of a name with the published one, looked up fresh; a new
  build replaces it, and the pin follows only the build it replaced (design 12 V4, 23 C2).

  Scenario: A build that is what upstream publishes is up to date, after one request despite the cache
    Given the build "rolling" is installed and pinned
    And GitHub answers from "releases"
    And the release list is cached from "releases", 1 minutes old
    When I run "tlaup tool upgrade rolling"
    Then the exit code is 0
    And stdout is empty
    And stderr is exactly "rolling@bc1b506 is up to date"
    And 0 jar downloads were made
    And 1 request was sent to GitHub

  Scenario: No argument upgrades the pinned build's name, and says when it is up to date
    Given the build "v1.7.4" is installed
    And the build "rolling" is installed and pinned
    And GitHub answers from "releases"
    When I run "tlaup tool upgrade"
    Then the exit code is 0
    And stderr is exactly "rolling@bc1b506 is up to date"
    And 1 request was sent to GitHub

  Scenario: A new build replaces the old one, and the pin moves with it
    Given the build "rolling@1a2b3c4" is installed and pinned
    And GitHub answers from "releases"
    When I run "tlaup tool upgrade"
    Then the exit code is 0
    And stderr matches the expected file "tool_upgrade/replaced.txt"
    And 1 jar download was made
    And the installed builds are:
      | build           |
      | rolling@bc1b506 |
    And the pinned build is "rolling"

  Scenario: With two builds of a name only the newer is compared and replaced
    Given the build "rolling@2026.11.01.000000" is installed
    And the build "rolling@2026.11.10.000000" is installed and pinned
    And GitHub answers from "releases"
    When I run "tlaup tool upgrade rolling"
    Then the exit code is 0
    And stderr contains "Removed rolling@2026.11.10.000000"
    And stderr contains "1 older build of rolling is still installed (rolling@2026.11.01.000000)"
    And the installed builds are:
      | build                     |
      | rolling@2026.11.15.002146 |
      | rolling@2026.11.01.000000 |
    And the pinned build is "rolling@2026.11.15.002146"

  Scenario: With the older of two builds pinned the pin stays on it, and the note says so
    Given the build "rolling@2026.11.01.000000" is installed and pinned
    And the build "rolling@2026.11.10.000000" is installed
    And GitHub answers from "releases"
    When I run "tlaup tool upgrade rolling"
    Then the exit code is 0
    And stderr contains "rolling@2026.11.01.000000 is still pinned (tlaup tool pin rolling@2026.11.15.002146)"
    And the pinned build is "rolling@2026.11.01.000000"

  Scenario: Upgrading a name that is not installed installs it
    Given GitHub answers from "releases"
    When I run "tlaup tool upgrade v1.7.4"
    Then the exit code is 0
    And stderr contains "v1.7.4 was not installed; installed v1.7.4@5a47802"
    And the installed builds are:
      | build          |
      | v1.7.4@5a47802 |
    And the pinned build is "v1.7.4"

  Scenario Outline: No argument with nothing pinned exits 3, <what>
    Given <given>
    And GitHub answers from "releases"
    When I run "tlaup tool upgrade"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "<error>"
    And 0 requests were sent to GitHub

    Examples:
      | what                   | given                           | error                          |
      | with a build           | the build "v1.7.4" is installed | error: no version pinned       |
      | with nothing installed | no build is installed           | error: no TLA+ tools installed |

  Scenario Outline: A version that names one build is a usage error, before any request: <version>
    Given the build "v1.7.4" is installed and pinned
    And the build "rolling" is installed
    And GitHub answers from "releases"
    When I run "tlaup tool upgrade <version>"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "error:" 1 times
    And 0 requests were sent to GitHub

    Examples:
      | version           |
      | 2026.11.15.002146 |
      | rolling@bc1b506   |
      | v1.7.4@5a47802    |

  Scenario: stable moves to a newer stable release beside the old one, and the pin moves to it
    Given the build "v1.7.4" is installed and pinned
    And GitHub answers from "stable-v1.8.0"
    When I run "tlaup tool upgrade stable"
    Then the exit code is 0
    And stderr matches the expected file "tool_upgrade/stable.txt"
    And the installed builds are:
      | build          |
      | v1.8.0@bc1b506 |
      | v1.7.4@5a47802 |
    And the pinned build is "v1.8.0"
