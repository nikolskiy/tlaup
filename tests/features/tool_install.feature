Feature: Installing TLA+ tools builds
  "tool install" looks the release up fresh, downloads and checks its jar, and adds it to the store; "already
  there" is the same name and the same bytes, and the first build installed is pinned (design 12 V12, V5, V7,
  02 X3, 23 C2, 13 J3, 14 F3). The request counts cover the last run, the jar's download included.

  # V12's table, row by row

  Scenario: A name with no build installed is downloaded, installed and pinned
    Given GitHub answers from "releases"
    When I run "tlaup tool install v1.7.4"
    Then the exit code is 0
    And stdout is empty
    And stderr matches the expected file "tool_install/first.txt"
    And the installed builds are:
      | build          |
      | v1.7.4@5a47802 |
    And the pinned build is "v1.7.4"
    And 2 requests were sent to GitHub
    And 1 jar download was made

  Scenario: A build that is what upstream publishes is already installed, and nothing is downloaded
    Given the build "v1.7.4" is installed and pinned
    And GitHub answers from "releases"
    When I run "tlaup tool install v1.7.4"
    Then the exit code is 0
    And stderr is exactly "v1.7.4@5a47802 is already installed (use --force to download it again)"
    And the installed builds are:
      | build          |
      | v1.7.4@5a47802 |
    And 1 request was sent to GitHub
    And 0 jar downloads were made

  Scenario: A moving tag that upstream rebuilt is installed beside the older build, and the pin stays
    Given the build "rolling@1a2b3c4" is installed and pinned
    And GitHub answers from "releases"
    When I run "tlaup tool install rolling"
    Then the exit code is 0
    And stderr matches the expected file "tool_install/moving-tag.txt"
    And the installed builds are:
      | build           |
      | rolling@bc1b506 |
      | rolling@1a2b3c4 |
    And the pinned build is "rolling@1a2b3c4"
    And 1 jar download was made

  Scenario: A rebuilt moving tag with the pin on another name names both builds and the pinned one
    Given the build "v1.7.4" is installed and pinned
    And the build "rolling@1a2b3c4" is installed
    And GitHub answers from "releases"
    When I run "tlaup tool install rolling"
    Then the exit code is 0
    And stderr is exactly "rolling@bc1b506 installed beside rolling@1a2b3c4; v1.7.4@5a47802 is pinned"
    And the pinned build is "v1.7.4"

  Scenario: The same file uploaded again is downloaded once, and then recognised
    Given the build "v1.7.4" is installed and pinned
    And GitHub answers from "reuploaded"
    When I run "tlaup tool install v1.7.4"
    Then the exit code is 0
    And stderr is exactly "v1.7.4@5a47802 is already installed (use --force to download it again)"
    And 1 jar download was made
    And the installed builds are:
      | build          |
      | v1.7.4@5a47802 |
    When I run "tlaup tool install v1.7.4"
    Then the exit code is 0
    And 0 jar downloads were made
    And 1 request was sent to GitHub

  Scenario: --force downloads an installed build again and repairs it in place
    Given the build "v1.7.4" is installed and pinned
    And GitHub answers from "releases"
    When I run "tlaup tool install --force v1.7.4"
    Then the exit code is 0
    And stderr is exactly "Reinstalled v1.7.4@5a47802"
    And 1 jar download was made
    And the installed builds are:
      | build          |
      | v1.7.4@5a47802 |
    And the pinned build is "v1.7.4"

  Scenario: --force repairs a build whose jar was cut short
    Given the build "v1.7.4" is installed and pinned
    And the jar of the build "v1.7.4" is truncated
    And GitHub answers from "releases"
    When I run "tlaup tool install --force v1.7.4"
    Then the exit code is 0
    And stderr is exactly "Reinstalled v1.7.4@5a47802"
    And 1 jar download was made
    And the installed builds are:
      | build          |
      | v1.7.4@5a47802 |
    When I run "tlaup tool install v1.7.4"
    Then stderr is exactly "v1.7.4@5a47802 is already installed (use --force to download it again)"

  Scenario: --force whose download fails leaves the installed build as it was, and pinned
    Given the build "v1.7.4" is installed and pinned
    And GitHub answers from "releases"
    And GitHub answers 403 to "https://github.com/tlaplus/tlaplus/releases/download/v1.7.4/tla2tools.jar"
    When I run "tlaup tool install --force v1.7.4"
    Then the exit code is 5
    And stderr contains "error:" 1 times
    And the installed builds are:
      | build          |
      | v1.7.4@5a47802 |
    And the pinned build is "v1.7.4"

  Scenario: A build named by its commit that is installed needs no request
    Given the build "v1.7.4" is installed and pinned
    And GitHub answers from "releases"
    When I run "tlaup tool install v1.7.4@5a47802"
    Then the exit code is 0
    And stderr is exactly "v1.7.4@5a47802 is already installed (use --force to download it again)"
    And 0 requests were sent to GitHub

  Scenario: A commit prefix matching two installed builds names both and sends no request
    Given the build "rolling" is installed and pinned
    And the build "rolling@bc1b5061" is installed
    And GitHub answers from "releases"
    When I run "tlaup tool install rolling@bc1b506"
    Then the exit code is 0
    And stderr is exactly "rolling@bc1b5061 and rolling@bc1b506b are already installed"
    And 0 requests were sent to GitHub

  Scenario: The same prefix with --force is a usage error listing the candidates
    Given the build "rolling" is installed and pinned
    And the build "rolling@bc1b5061" is installed
    And GitHub answers from "releases"
    When I run "tlaup tool install --force rolling@bc1b506"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr contains "rolling@bc1b5061, rolling@bc1b506b"
    And 0 requests were sent to GitHub

  Scenario: --force on a named build that upstream still publishes repairs it
    Given the build "v1.7.4" is installed and pinned
    And GitHub answers from "releases"
    When I run "tlaup tool install --force v1.7.4@5a47802"
    Then the exit code is 0
    And stderr is exactly "Reinstalled v1.7.4@5a47802"
    And 1 jar download was made

  Scenario: --force on a named build that upstream no longer publishes changes nothing
    Given the build "v1.7.4@1234567" is installed and pinned
    And GitHub answers from "releases"
    When I run "tlaup tool install --force v1.7.4@1234567"
    Then the exit code is 4
    And stderr contains "error:" 1 times
    And stderr contains "cannot be downloaded again"
    And the installed builds are:
      | build          |
      | v1.7.4@1234567 |
    And the pinned build is "v1.7.4@1234567"

  Scenario: A build named by a commit that upstream does not publish is not installed
    Given GitHub answers from "releases"
    When I run "tlaup tool install rolling@1a2b3c4"
    Then the exit code is 4
    And stderr contains "rolling is rolling@bc1b506 now"
    And the installed builds are:
      | build |

  Scenario: A build named by its digest that is not installed is not looked up
    Given GitHub answers from "releases"
    When I run "tlaup tool install rolling@sha256:888fd447a34f"
    Then the exit code is 4
    And 0 requests were sent to GitHub

  Scenario: A build time installed under two names names both
    Given the build "rolling" is installed and pinned
    And the build "v1.8.0" is installed
    And GitHub answers from "releases"
    When I run "tlaup tool install 2026.11.15.002146"
    Then the exit code is 0
    And stderr is exactly "rolling@bc1b506 and v1.8.0@bc1b506 are already installed"
    And 0 requests were sent to GitHub

  Scenario: A build time that is not installed cannot be fetched
    Given GitHub answers from "releases"
    When I run "tlaup tool install 2026.11.15.002146"
    Then the exit code is 4
    And 0 requests were sent to GitHub

  Scenario: --force with a build time is a usage error
    Given the build "rolling" is installed and pinned
    And GitHub answers from "releases"
    When I run "tlaup tool install --force 2026.11.15.002146"
    Then the exit code is 2
    And stderr contains "error:" 1 times
    And 0 requests were sent to GitHub

  Scenario: stable is the highest-numbered release that is not a prerelease
    Given GitHub answers from "releases"
    When I run "tlaup tool install stable"
    Then the exit code is 0
    And the installed builds are:
      | build          |
      | v1.7.4@5a47802 |
    And 2 requests were sent to GitHub

  # Two names, one jar; twice; the pin

  Scenario: rolling and v1.8.0 holding one jar are two builds, and either can be pinned
    Given the build "rolling" is installed and pinned
    And GitHub answers from "releases"
    When I run "tlaup tool install v1.8.0"
    Then the exit code is 0
    And the installed builds are:
      | build           |
      | rolling@bc1b506 |
      | v1.8.0@bc1b506  |
    When I run "tlaup tool pin v1.8.0"
    Then the exit code is 0
    And the pinned build is "v1.8.0"

  Scenario: The second install of a release makes one request and no download
    Given GitHub answers from "releases"
    When I run "tlaup tool install v1.7.4"
    And I run "tlaup tool install v1.7.4"
    Then the exit code is 0
    And 0 jar downloads were made
    And 1 request was sent to GitHub

  Scenario: The second install with GitHub unreachable still succeeds, with one warning
    Given GitHub answers from "releases"
    When I run "tlaup tool install v1.7.4"
    Given GitHub is unreachable
    When I run "tlaup tool install v1.7.4"
    Then the exit code is 0
    And stderr contains "warning: could not check GitHub for a newer build of v1.7.4: " 1 times
    And stderr contains "warning:" 1 times
    And 0 jar downloads were made

  Scenario: The first build installed is pinned, the second is not
    Given GitHub answers from "releases"
    When I run "tlaup tool install v1.7.4"
    Then stderr contains "Pinned v1.7.4@5a47802"
    When I run "tlaup tool install rolling"
    Then the exit code is 0
    And stderr is exactly "Installed rolling@bc1b506"
    And the pinned build is "v1.7.4"

  # No version

  Scenario: No version with TLAUP_AUTO_INSTALL set installs that build without asking
    Given the environment variable "TLAUP_AUTO_INSTALL" is "stable"
    And GitHub answers from "releases"
    When I run "tlaup tool install"
    Then the exit code is 0
    And stderr does not contain "Which build"
    And the pinned build is "v1.7.4"

  Scenario: No version, no terminal and no TLAUP_AUTO_INSTALL is a usage error
    Given GitHub answers from "releases"
    When I run "tlaup tool install"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr contains "TLAUP_AUTO_INSTALL"
    And 0 requests were sent to GitHub
    And the installed builds are:
      | build |

  Scenario Outline: A command-line usage error exits 2 before the settings are read: <command>
    Given the build "rolling" is installed and pinned
    And the config file contains:
      """
      tool: [this is not a section
      """
    When I run "<command>"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "error:" 1 times

    Examples:
      | command                                   |
      | tlaup tool install                        |
      | tlaup tool install --force 2026.11.15.002146 |
      | tlaup tool upgrade 2026.11.15.002146      |

  # What is not a version (02 X3, 23 C2, 12 V6)

  Scenario: latest is refused, naming the stable release of the cached list
    Given GitHub answers from "releases"
    And the release list is cached from "releases", 600 minutes old
    When I run "tlaup tool install latest"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "`stable` (v1.7.4)"
    And 0 requests were sent to GitHub

  Scenario: latest is refused, naming the stable build installed when nothing is cached
    Given the build "v1.7.4" is installed and pinned
    And GitHub answers from "releases"
    When I run "tlaup tool install latest"
    Then the exit code is 2
    And stderr contains "`stable` (v1.7.4)"
    And 0 requests were sent to GitHub

  Scenario: latest is refused with no tag when nothing is cached or installed
    Given GitHub answers from "releases"
    When I run "tlaup tool install latest"
    Then the exit code is 2
    And stderr contains "Use `stable` or `rolling`"
    And 0 requests were sent to GitHub

  Scenario: An address is not a version
    Given GitHub answers from "releases"
    When I run "tlaup tool install https://example.org/tla2tools.jar"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr contains "Installing from an address is not supported"
    And 0 requests were sent to GitHub

  # Java, the repository, the token

  Scenario: Installing needs no Java, and the build's commit and build time come from the jar
    Given java is not installed
    And GitHub answers from "releases"
    When I run "tlaup tool install rolling"
    Then the exit code is 0
    When I run "tlaup tool current"
    Then the exit code is 0
    And stdout contains "rolling@bc1b506 (2026.11.15.002146)"

  Scenario: tool.repository set to another https address is where the requests go, without the token
    Given the config file contains:
      """
      tool:
        repository: https://ghe.example.org/api/v3/repos/tlaplus/tlaplus
      """
    And GitHub answers from "releases"
    And GitHub answers 403 to "https://ghe.example.org/api/v3/repos/tlaplus/tlaplus/releases/tags/v1.7.4"
    And the environment variable "GH_TOKEN" is "token-of-the-test-29a"
    When I run "tlaup tool install v1.7.4"
    Then the exit code is 5
    And stderr contains "https://ghe.example.org/api/v3/repos/tlaplus/tlaplus/releases/tags/v1.7.4 answered 403"
    And 1 request was sent to GitHub
    And no request carried a token to "ghe.example.org"

  Scenario: The token is never printed, under --debug either
    Given the environment variable "GH_TOKEN" is "token-of-the-test-29a"
    And GitHub answers from "releases"
    And GitHub answers 401 to "/releases/tags/rolling"
    When I run "tlaup --debug tool install rolling"
    Then the exit code is 5
    And stderr contains "Traceback"
    And stderr does not contain "token-of-the-test-29a"
    And stdout does not contain "token-of-the-test-29a"
