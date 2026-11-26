Feature: Errors and exit codes
  Each error gives the exit code of decision D29 and nothing on stdout (design 02 X1, 14 F10).

  Scenario: No command prints the usage on stdout and exits 2
    When I run "tlaup"
    Then the exit code is 2
    And stdout contains "Usage"
    And stderr is empty

  Scenario: A group without its command prints the usage on stdout and exits 2
    When I run "tlaup config"
    Then the exit code is 2
    And stdout contains "Usage"
    And stderr is empty

  Scenario: An unknown option is a usage error
    When I run "tlaup --nosuch"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "--nosuch"

  Scenario: A missing argument is a usage error
    When I run "tlaup tool pin"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "VERSION"

  Scenario: An unknown command is a usage error
    When I run "tlaup nosuch"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "nosuch"

  Scenario: --debug after the subcommand is an unknown option there
    When I run "tlaup config --debug"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "--debug"

  Scenario Outline: A relative TLAUP_HOME is one error, before the context exists
    Given the environment variable "TLAUP_HOME" is "relative/path"
    And the environment variable "TLAUP_DEBUG" is "<debug>"
    When I run "<command>"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr <traceback> "Traceback"

    Examples:
      | command                | debug | traceback        |
      | tlaup tool dir         | 0     | does not contain |
      | tlaup --debug tool dir | 0     | contains         |
      | tlaup tool dir         | 1     | contains         |

  Scenario: Help on a closed pipe exits 141 without a traceback
    When I run "tlaup --help" as a process with stdout on a closed pipe
    Then the exit code is 141
    And stderr does not contain "Traceback"

  Scenario: A usage error with both streams on a closed pipe exits 141
    When I run "tlaup --nosuch" as a process with stdout and stderr on a closed pipe
    Then the exit code is 141

  Scenario: A usage error with stderr on a closed pipe exits 141
    When I run "tlaup --nosuch" as a process with stdout on the null device and stderr on a closed pipe
    Then the exit code is 141

  # The tool group (package 29a)

  Scenario: The tool group without its command prints the usage on stdout and exits 2
    When I run "tlaup tool"
    Then the exit code is 2
    And stdout contains "Usage"
    And stderr is empty

  Scenario: A version not found with both streams on a closed pipe exits 141
    When I run "tlaup tool pin nosuch" as a process with stdout and stderr on a closed pipe
    Then the exit code is 141

  Scenario Outline: A pin file that cannot be read is one error, with the traceback only under debug
    Given a file "{tools}/pin/x" containing:
      """
      the pin is a folder here, which no reader can read as a file
      """
    And the environment variable "TLAUP_DEBUG" is "<debug>"
    When I run "<command>"
    Then the exit code is 5
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr <traceback> "Traceback"

    Examples:
      | command                    | debug | traceback        |
      | tlaup tool current         | 0     | does not contain |
      | tlaup --debug tool current | 0     | contains         |
      | tlaup tool current         | 1     | contains         |

  Scenario: GitHub unreachable with nothing installed is a network error
    Given GitHub is unreachable
    When I run "tlaup tool install v1.7.4"
    Then the exit code is 5
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr does not contain "Traceback"

  Scenario: An answer from GitHub that is not JSON is an error, not a traceback
    Given GitHub answers from "not-json"
    When I run "tlaup tool install stable"
    Then the exit code is 5
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr contains "did not answer with JSON"
    And stderr does not contain "Traceback"

  # The tool group (package 29b)

  Scenario: tool list with stdout on a closed pipe exits 141 without a traceback
    Given the build "v1.7.4" is installed and pinned
    And the build "rolling" is installed
    And the release list is cached from "releases", 1 minutes old
    When I run "tlaup tool list" as a process with stdout on a closed pipe
    Then the exit code is 141
    And stderr does not contain "Traceback"

  # The module group (package 31): one scenario for each exit code its errors give

  Scenario Outline: A module error is one error line with the code of its kind, and no traceback: <kind>
    Given the build "v1.7.4" is installed and pinned
    And a module source "Queue" from the fake sources
    And <setup>
    When I run "<command>"
    Then the exit code is <code>
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr does not contain "Traceback"

    Examples:
      | kind                  | setup                     | command                    | code |
      | an invalid name       | javac is version "25.0.5" | tlaup module remove a/b    | 2    |
      | javac is not found    | javac is not installed    | tlaup module add Queue     | 3    |
      | a path is not found   | javac is version "25.0.5" | tlaup module add nosuch    | 4    |
      | a module is not found | javac is version "25.0.5" | tlaup module remove Nosuch | 4    |

  Scenario: A javac error is one error line before the compiler's output, with no traceback
    Given the build "v1.7.4" is installed and pinned
    And a module source "Queue" from the fake sources
    And javac fails with "syntax-error"
    When I run "tlaup module add Queue"
    Then the exit code is 5
    And stdout is empty
    And stderr contains "error: javac failed with exit code 1"
    And stderr does not contain "Traceback"

  # The config group (package 44): one scenario for each exit code its errors give

  Scenario: A value that does not fit its key is one error line and exits 2
    When I run "tlaup config set tlc.workers many"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "error:" 1 times

  Scenario Outline: A broken config file is one error line and exits 3, with the traceback only under debug
    Given the config file contains:
      """
      tlc:
        refresh_interval: fast
      """
    And the environment variable "TLAUP_DEBUG" is "<debug>"
    When I run "<command>"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr <traceback> "Traceback"

    Examples:
      | command                   | debug | traceback        |
      | tlaup config show         | 0     | does not contain |
      | tlaup --debug config show | 0     | contains         |
      | tlaup config show         | 1     | contains         |

  Scenario: A key that does not exist is one error line and exits 4
    When I run "tlaup config get no.such.key"
    Then the exit code is 4
    And stdout is empty
    And stderr contains "error:" 1 times

  Scenario: An editor that fails is one error line and exits 5
    Given the environment variable "EDITOR" is "editor"
    And the editor exits with code 1
    When I run "tlaup config edit"
    Then the exit code is 5
    And stdout is empty
    And stderr contains "error:" 1 times

  Scenario: A run id with an option is one error line and exits 2
    When I run "tlaup cache clean nosuch --all"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "error:" 1 times

  Scenario: A run id that names no folder is one error line and exits 4
    When I run "tlaup cache clean nosuch"
    Then the exit code is 4
    And stdout is empty
    And stderr contains "error:" 1 times

  # The command tree as a whole (package 48)

  Scenario Outline: A removed name is an unknown command or option and exits 2: <removed>
    When I run "<command>"
    Then the exit code is 2
    And stdout is empty

    Examples:
      | command                      | removed         |
      | tlaup tools list             | tools           |
      | tlaup modules list           | modules         |
      | tlaup check-java             | check-java      |
      | tlaup fetch-cache clear      | fetch-cache     |
      | tlaup tool meta sync         | tools meta      |
      | tlaup module path            | modules path    |
      | tlaup config list            | config list     |
      | tlaup config edit vim        | config edit EDITOR |
      | tlaup tool install -f v1.7.4 | install -f      |
      | tlaup tool uninstall -y v1.7.4 | uninstall -y  |
      | tlaup -v                     | the old version flag |

  Scenario: The module group without its command prints the usage on stdout and exits 2
    When I run "tlaup module"
    Then the exit code is 2
    And stdout contains "Usage"
    And stderr is empty

  # Design 11 R11 step 0: a mistake in the command line is reported before the settings are read

  Scenario Outline: A mistake on the command line beats a broken config file: <command>
    Given the config file contains:
      """
      tlc:
        refresh_interval: fast
      """
    And the environment variable "TLAUP_JAVA_OPTS" is "<opts>"
    And the build "v1.7.4" is installed and pinned
    When I run "<command>"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr does not contain "config.yaml"

    Examples:
      | command                                       | opts |
      | tlaup tlc Success --workers 2 -- -workers 4   |      |
      | tlaup tlc Success                             | 'a   |
      | tlaup sany Success                            | 'a   |
      | tlaup pcal Success                            | 'a   |
      | tlaup repl                                    | 'a   |

  Scenario: A broken config file is still reported when the command line is right
    Given the config file contains:
      """
      tlc:
        refresh_interval: fast
      """
    And the build "v1.7.4" is installed and pinned
    When I run "tlaup tlc Success"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "error:" 1 times
