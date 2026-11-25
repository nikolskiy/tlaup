Feature: Errors and exit codes
  Each error gives the exit code of decision D29 and nothing on stdout (design 02 X1, 14 F10).
  The scenarios through "tools" reach the root group only; package 29a renames them to "tool".

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
    # The old "tools pin" names its argument "version"; 29a's "tool pin VERSION" changes the text with the name.
    When I run "tlaup tools pin"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "version"

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
      | command                 | debug | traceback        |
      | tlaup tools dir         | 0     | does not contain |
      | tlaup --debug tools dir | 0     | contains         |
      | tlaup tools dir         | 1     | contains         |
