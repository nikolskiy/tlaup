Feature: The config commands
  "config path" prints where the file is, "config show" and "config get" read the settings in effect, "config set"
  changes one key, and "config edit" opens the file in the user's editor. With a broken file "path" and "edit" work
  and the others stop with the reason (design 14 F1, F4, F5, 23 C1).

  # F1 and C1

  Scenario: A value that does not fit its key is a usage error and writes nothing
    When I run "tlaup config set tlc.workers many"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "tlc.workers"
    And the file "{config}/config.yaml" does not exist

  Scenario Outline: A key that does not exist is not found: <command>
    When I run "<command>"
    Then the exit code is 4
    And stdout is empty
    And stderr contains "no.such.key"
    And the file "{config}/config.yaml" does not exist

    Examples:
      | command                        |
      | tlaup config set no.such.key 1 |
      | tlaup config get no.such.key   |

  Scenario: A mistyped key is answered with the nearest one
    When I run "tlaup config get tlc.worker"
    Then the exit code is 4
    And stdout is empty
    And stderr contains "tlc.workers"

  Scenario: A section name is not a key
    When I run "tlaup config get tlc"
    Then the exit code is 4
    And stdout is empty
    And stderr contains "tlc.workers"
    And stderr contains "tlc.refresh_interval"

  Scenario: config path prints the path and creates nothing
    When I run "tlaup config path"
    Then the exit code is 0
    And stdout is exactly "{config}/config.yaml"
    And stderr is empty
    And the file "{config}/config.yaml" does not exist

  Scenario: The schema checks the type, and the range is the command's that uses the value
    When I run "tlaup config set tlc.refresh_interval 0"
    Then the exit code is 0
    When I run "tlaup config get tlc.refresh_interval"
    Then the exit code is 0
    And stdout is exactly "0.0"

  Scenario: config show on a fresh home lists the settings with no file (the fixture's repository comes from the environment)
    When I run "tlaup config show"
    Then the exit code is 0
    And stderr is empty
    And stdout matches the expected file "config/show-defaults.txt"
    And the file "{config}/config.yaml" does not exist

  Scenario: config show names the layer each value came from
    Given the config file contains:
      """
      tlc:
        workers: 4
      """
    And the environment variable "TLAUP_JAVA_MIN_VERSION" is "17"
    When I run "tlaup config show"
    Then the exit code is 0
    And stdout matches the expected file "config/show-layers.txt"

  Scenario: config show warns about unknown keys on stderr, not in its output
    Given the config file contains:
      """
      tlc:
        wokers: 4
      """
    When I run "tlaup config show"
    Then the exit code is 0
    And stderr contains "warning:"
    And stderr contains "tlc.wokers"
    And stdout does not contain "wokers"

  Scenario: config get prints the default
    When I run "tlaup config get tlc.workers"
    Then the exit code is 0
    And stdout is exactly "auto"

  Scenario: config set writes the value and config get reads it back
    When I run "tlaup config set tlc.workers 4"
    Then the exit code is 0
    And stdout is empty
    And stderr contains "tlc.workers"
    And stderr contains "{config}/config.yaml"
    And the file "{config}/config.yaml" contains "workers: 4"
    When I run "tlaup config get tlc.workers"
    Then the exit code is 0
    And stdout is exactly "4"

  Scenario: A host name is lower-cased, and a URL is not a host name
    When I run "tlaup config set tool.token_hosts '[GHE.example.com]'"
    Then the exit code is 0
    When I run "tlaup config get tool.token_hosts"
    Then the exit code is 0
    And stdout is exactly "[ghe.example.com]"
    When I run "tlaup config set tool.token_hosts 'https://ghe.example.com'"
    Then the exit code is 2
    And stdout is empty

  Scenario: A list of Java options is written and read back
    When I run "tlaup config set java.opts '[-Xmx8g, -XX:+UseParallelGC]'"
    Then the exit code is 0
    When I run "tlaup config get java.opts"
    Then the exit code is 0
    And stdout contains "-Xmx8g"
    And stdout contains "-XX:+UseParallelGC"

  Scenario: A value that is not YAML is a usage error
    When I run "tlaup config set java.opts '[-Xmx8g'"
    Then the exit code is 2
    And stdout is empty
    And the file "{config}/config.yaml" does not exist

  Scenario: config set keeps the other keys and the header, and drops a comment
    Given the config file contains:
      """
      # my note
      tlc:
        keep: true
      """
    When I run "tlaup config set tlc.workers 2"
    Then the exit code is 0
    And the file "{config}/config.yaml" contains "# tlaup settings"
    And the file "{config}/config.yaml" contains "keep: true"
    And the file "{config}/config.yaml" contains "workers: 2"
    When I run "tlaup config get tlc.keep"
    Then stdout is exactly "true"

  Scenario: config set keeps a key it does not know and says so
    Given the config file contains:
      """
      tlc:
        wokers: 4
      """
    When I run "tlaup config set tlc.workers 2"
    Then the exit code is 0
    And stderr contains "tlc.wokers"
    And the file "{config}/config.yaml" contains "wokers: 4"

  # F4: a file that does not parse

  Scenario Outline: A file that is not YAML leaves path and edit working and stops the others: <command>
    Given the config file contains:
      """
      tlc: [
      """
    When I run "<command>"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "line"
    And stderr contains "column"
    And stderr contains "tlaup config edit"
    And stderr does not contain "Traceback"
    And the config file is unchanged

    Examples:
      | command                        |
      | tlaup config show              |
      | tlaup config get tlc.workers   |
      | tlaup config set tlc.workers 4 |

  Scenario: config path works with a file that is not YAML
    Given the config file contains:
      """
      tlc: [
      """
    When I run "tlaup config path"
    Then the exit code is 0
    And stdout is exactly "{config}/config.yaml"

  Scenario: config edit opens a file that is not YAML, and exits 3 when it is left that way
    Given the config file contains:
      """
      tlc: [
      """
    And the environment variable "EDITOR" is "editor"
    And the editor exits with code 0
    When I run "tlaup config edit"
    Then the editor was started with "{config}/config.yaml"
    And the exit code is 3
    And stdout is empty
    And stderr contains "tlaup config edit"
    And stderr does not contain "Traceback"
    And the config file is unchanged

  # F4: a bad value in the environment is not a file error

  Scenario Outline: A bad environment value names the variable and does not point at the file: <command>
    Given the environment variable "TLAUP_TLC_WORKERS" is "many"
    When I run "<command>"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "TLAUP_TLC_WORKERS"
    And stderr contains "tlc.workers"
    And stderr does not contain "tlaup config edit"

    Examples:
      | command                        |
      | tlaup config show              |
      | tlaup config get tlc.workers   |
      | tlaup config set tlc.workers 4 |

  # F4: a file with a value of the wrong type

  Scenario Outline: A file with a wrong type leaves path and edit working and stops the others: <command>
    Given the config file contains:
      """
      tlc:
        refresh_interval: fast
      """
    When I run "<command>"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "tlc.refresh_interval"
    And stderr contains "tlaup config edit"
    And stderr does not contain "Traceback"
    And the config file is unchanged

    Examples:
      | command                        |
      | tlaup config show              |
      | tlaup config get tlc.workers   |
      | tlaup config set tlc.workers 4 |

  Scenario: config path works with a file holding a wrong type
    Given the config file contains:
      """
      tlc:
        refresh_interval: fast
      """
    When I run "tlaup config path"
    Then the exit code is 0
    And stdout is exactly "{config}/config.yaml"

  Scenario: config edit opens a file holding a wrong type, and exits 3 when it is left that way
    Given the config file contains:
      """
      tlc:
        refresh_interval: fast
      """
    And the environment variable "EDITOR" is "editor"
    And the editor exits with code 0
    When I run "tlaup config edit"
    Then the editor was started with "{config}/config.yaml"
    And the exit code is 3
    And stderr contains "tlc.refresh_interval"
    And the config file is unchanged

  Scenario: After the editor repairs the file, edit and show work
    Given the config file contains:
      """
      tlc: [
      """
    And the environment variable "EDITOR" is "editor"
    And the editor writes:
      """
      tlc:
        workers: 3
      """
    When I run "tlaup config edit"
    Then the exit code is 0
    And stdout is empty
    When I run "tlaup config show"
    Then the exit code is 0
    And stdout contains "workers: 3"

  # F5

  Scenario: An editor given with arguments is started with them and the path
    Given the environment variable "EDITOR" is "editor --wait"
    And the editor exits with code 0
    When I run "tlaup config edit"
    Then the exit code is 0
    And stdout is empty
    And the editor was started with "--wait"
    And the editor was started with "{config}/config.yaml"

  Scenario: VISUAL wins over EDITOR
    Given the environment variable "VISUAL" is "editor --visual"
    And the environment variable "EDITOR" is "editor --wait"
    And the editor exits with code 0
    When I run "tlaup config edit"
    Then the exit code is 0
    And the editor was started with "--visual"
    And the editor was started without "--wait"

  Scenario: An empty VISUAL counts as unset
    Given the environment variable "VISUAL" is ""
    And the environment variable "EDITOR" is "editor --wait"
    And the editor exits with code 0
    When I run "tlaup config edit"
    Then the exit code is 0
    And the editor was started with "--wait"

  Scenario: An edit that writes a wrong value exits 3 and keeps what the editor wrote
    Given the environment variable "EDITOR" is "editor"
    And the editor writes:
      """
      tlc:
        workers: many
      """
    When I run "tlaup config edit"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "tlc.workers"
    And the file "{config}/config.yaml" contains "workers: many"

  Scenario: An edit that writes a good file exits 0 and prints the warnings of the file
    Given the environment variable "EDITOR" is "editor"
    And the editor writes:
      """
      tlc:
        wokers: 3
      """
    When I run "tlaup config edit"
    Then the exit code is 0
    And stderr contains "tlc.wokers"

  Scenario: Quitting without changes on a fresh home leaves no file
    Given the environment variable "EDITOR" is "editor"
    And the editor exits with code 0
    When I run "tlaup config edit"
    Then the exit code is 0
    And the editor was started with "{config}/config.yaml"
    And the file "{config}/config.yaml" does not exist

  Scenario: An editor that exits with an error is a failure
    Given the environment variable "EDITOR" is "editor"
    And the editor exits with code 1
    When I run "tlaup config edit"
    Then the exit code is 5
    And stdout is empty
    And the file "{config}/config.yaml" does not exist

  Scenario: With no editor set and none on PATH, edit asks for EDITOR
    When I run "tlaup config edit"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "EDITOR"
    And the editor was not started

  Scenario: An editor that is not on PATH is named, and not started
    Given the environment variable "EDITOR" is "nosuch-editor --wait"
    When I run "tlaup config edit"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "EDITOR"
    And stderr contains "nosuch-editor"
    And the editor was not started
