Feature: Probe of the pytest-bdd forms the design uses

  Scenario: A doc string, and a Given after a When
    Given a file "a.txt" containing:
      """
      line one
        indented "quoted"
      """
    When I run "first"
    Given java replays "tlc/x" with exit code 12
    When I run "second"
    Then the runs were "first,second"
    And the file "a.txt" holds 2 lines
