Feature: tlaup completion
  "completion" prints the completion script of bash, zsh or fish on stdout. Any other shell is a usage error
  (design 23 C3). The completers themselves are tested in tests/unit/cmd/test_completion.py.

  Scenario Outline: The script of each shell is printed
    When I run "tlaup completion <shell>"
    Then the exit code is 0
    And stdout contains "_TLAUP_COMPLETE"
    And stdout contains "tlaup"
    And stderr is empty

    Examples:
      | shell |
      | bash  |
      | zsh   |
      | fish  |

  Scenario: PowerShell is not offered
    When I run "tlaup completion powershell"
    Then the exit code is 2
    And stdout is empty
