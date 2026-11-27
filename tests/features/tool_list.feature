Feature: Listing the releases and the installed builds
  "tool list" shows the releases that have a tla2tools.jar, in the order of 02 X4, each followed by the installed
  builds of its name, then the builds upstream no longer lists; "--installed" shows the installed builds alone,
  with no request (design 12 V8, 02 X4, 23 C1; decisions D64, D65).

  # The four states of the release list (inventory rows T18 and T22)

  Scenario: Online, the list is asked for and the table shows every release with a jar
    Given the build "v1.7.4" is installed and pinned
    And the build "rolling@2026.11.01.000000" is installed
    And GitHub answers from "releases"
    When I run "tlaup tool list"
    Then the exit code is 0
    And stdout matches the expected file "tool_list/online.txt"
    And stderr is empty
    And 1 request was sent to GitHub

  Scenario: Cached, a list younger than an hour is shown with no request
    Given the build "v1.7.4" is installed and pinned
    And the build "rolling@2026.11.01.000000" is installed
    And the release list is cached from "releases", 1 minutes old
    When I run "tlaup tool list"
    Then the exit code is 0
    And stdout matches the expected file "tool_list/cached.txt"
    And stderr is empty
    And 0 requests were sent to GitHub

  Scenario: Stale, an older cached list is shown and marked when GitHub cannot be reached
    Given the build "v1.7.4" is installed and pinned
    And the build "rolling@2026.11.01.000000" is installed
    And the release list is cached from "releases", 180 minutes old
    And GitHub is unreachable
    When I run "tlaup tool list"
    Then the exit code is 0
    And stdout matches the expected file "tool_list/stale.txt"
    And stderr matches the expected file "tool_list/stale-note.txt"

  Scenario: Unavailable, the installed builds are listed with one warning
    Given the build "v1.7.4" is installed and pinned
    And the build "rolling@2026.11.01.000000" is installed
    And GitHub is unreachable
    When I run "tlaup tool list"
    Then the exit code is 0
    And stdout matches the expected file "tool_list/unavailable.txt"
    And stderr matches the expected file "tool_list/unavailable-warning.txt"
    And stderr contains "warning:" 1 times
    And stderr does not contain "error:"

  # The rows

  Scenario: An older installed rolling build shows that an update is available, directly under the rolling row
    Given the build "rolling@2026.11.01.000000" is installed and pinned
    And GitHub answers from "releases"
    When I run "tlaup tool list"
    Then the exit code is 0
    And stdout matches the expected file "tool_list/update-available.txt"

  Scenario: Rows follow 02 X4: rolling first, then versions by number, each followed by its installed builds
    Given the build "v1.7.4" is installed
    And the build "v1.8.0" is installed
    And the build "rolling" is installed and pinned
    And the build "rolling@2026.11.01.000000" is installed
    And GitHub answers from "releases"
    When I run "tlaup tool list"
    Then the exit code is 0
    And stdout matches the expected file "tool_list/order.txt"

  Scenario: The seven releases without a jar have no row
    Given the build "v1.7.4" is installed and pinned
    And GitHub answers from "releases"
    When I run "tlaup tool list"
    Then the exit code is 0
    And stdout contains "v1.5.6"
    And stdout does not contain "v1.5.5"
    And stdout does not contain "v1.5.4"
    And stdout does not contain "v1.5.3"
    And stdout does not contain "v1.5.2"
    And stdout does not contain "v1.5.1"
    And stdout does not contain "v1.5.0"
    And stdout does not contain "v1.4.8"

  Scenario: A build of a release that has no jar at the moment keeps its place, as installed
    Given the build "v1.7.4" is installed and pinned
    And the build "v1.5.5" is installed
    And the build "v1.9.9" is installed
    And GitHub answers from "releases"
    When I run "tlaup tool list"
    Then the exit code is 0
    And stdout matches the expected file "tool_list/release-without-jar.txt"

  Scenario: A build whose tag upstream no longer lists comes last, with no hint against uninstalling it
    Given the build "v1.7.4" is installed and pinned
    And the build "v1.9.9" is installed
    And GitHub answers from "releases"
    When I run "tlaup tool list"
    Then the exit code is 0
    And stdout matches the expected file "tool_list/not-upstream.txt"
    And stderr is empty
    And stdout does not contain "hint:"
    And stdout does not contain "uninstall"

  Scenario: Not on a terminal at 80 columns no row breaks over two lines
    Given the build "v1.7.4" is installed and pinned
    And the build "rolling@2026.11.01.000000" is installed
    And GitHub answers from "releases"
    And the environment variable "COLUMNS" is "80"
    When I run "tlaup tool list"
    Then the exit code is 0
    And stdout matches the expected file "tool_list/online.txt"

  # --installed

  Scenario: --installed lists the installed builds and makes no request
    Given the build "v1.7.4" is installed and pinned
    And the build "rolling" is installed
    And the build "rolling@2026.11.01.000000" is installed
    And GitHub answers from "releases"
    When I run "tlaup tool list --installed"
    Then the exit code is 0
    And stdout matches the expected file "tool_list/installed.txt"
    And stderr is empty
    And 0 requests were sent to GitHub

  Scenario: --installed with nothing installed says so on stderr
    Given no build is installed
    And GitHub answers from "releases"
    When I run "tlaup tool list --installed"
    Then the exit code is 0
    And stdout is empty
    And stderr is exactly "no builds are installed"
    And 0 requests were sent to GitHub

  Scenario: --installed reads no settings, so a broken config file does not stop it
    Given the build "v1.7.4" is installed and pinned
    And the config file contains:
      """
      tool: [this is not a section
      """
    When I run "tlaup tool list --installed"
    Then the exit code is 0
    And stdout contains "5a47802"
    And stderr is empty
