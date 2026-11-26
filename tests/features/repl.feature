Feature: Starting the TLA+ REPL
  "tlaup repl [-- arguments]" starts the REPL of the pinned build with the terminal passed straight through and exits
  with the REPL's own code; a Ctrl-C is the REPL's, and SIGTERM stops it from outside. A build without the REPL (v1.7.4)
  is refused with exit 3 before Java is started (design 21 S3, decisions D29, D45 and D60). The refusals run in
  process; every run of the REPL is a real process, because the child inherits the real file descriptors. The fake
  java echoes its input.

  # S3, step 1: the capability is a fact about the build, checked before Java

  Scenario: A build without the REPL is refused before java is started
    Given the build "v1.7.4" is installed and pinned
    When I run "tlaup repl"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr contains "the pinned build v1.7.4"
    And stderr contains "has no REPL"
    And stderr contains "tlaup tool install rolling"
    And java was not started

  Scenario: The refusal comes before the search for java
    Given the build "v1.7.4" is installed and pinned
    And java is not installed
    When I run "tlaup repl"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr contains "has no REPL"
    And stderr contains "tlaup tool install rolling"
    And java was not started

  # S3, steps 2 to 4: the terminal is passed through and the code is the REPL's own

  Scenario: The input reaches the REPL and its output reaches stdout, and the exit code is the REPL's own
    Given the build "rolling" is installed and pinned
    And java echoes its input
    When I run "tlaup repl" as a process with input:
      """
      1+1
      """
    Then the exit code is 0
    And stdout contains "1+1"
    And java ran "tlc2.REPL" 1 time

  Scenario: SIGTERM from outside stops the REPL and exits 143
    Given the build "rolling" is installed and pinned
    And java echoes its input
    When I start "tlaup repl" and send SIGTERM once java is running
    Then the exit code is 143
    And java received SIGTERM
    And the java process has exited

  # S5: the arguments after "--" and the JVM options reach Java unchanged

  Scenario: The arguments after "--" and a JVM option are passed on unchanged
    Given the build "rolling" is installed and pinned
    And java echoes its input
    When I run "tlaup repl --java-opt=-Xss8m -- -x" as a process with input:
      """
      1+1
      """
    Then the exit code is 0
    And java was started with "-x"
    And java was started with "-Xss8m"
    And java ran "tlc2.REPL" 1 time
