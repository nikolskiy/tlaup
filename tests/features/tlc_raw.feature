Feature: tlaup tlc --raw
  With --raw TLC's own output reaches the terminal unchanged: TLC's stdout on stdout, its stderr on stderr, no
  -tool, and TLC's exit code. The run goes through the same preflight and run folder as a parsed run, and a closed
  output pipe stops TLC (design 11 R1, R6 and R11, 02 X2, 20 G3; inventory row R10). Every scenario that starts
  Java is a real process, since a raw run hands TLC tlaup's own streams.

  Background:
    Given the build "v1.7.4" is installed and pinned
    And a spec "Success" from the golden specs

  # X2: the two streams stay apart

  Scenario: TLC's stdout and stderr reach stdout and stderr unchanged, and TLC runs without -tool
    Given java writes "to-out" to stdout and "to-err" to stderr
    When I run "tlaup tlc Success --raw" as a process
    Then the exit code is 0
    And stdout is exactly "to-out"
    And stderr is exactly "to-err"
    And java was started without "-tool"

  Scenario: A plain capture reaches stdout byte for byte, and TLC's exit code passes through
    Given a spec "Violation" from the golden specs
    And java replays "tlc/v1.7.4/plain/violation" with exit code 12
    When I run "tlaup tlc Violation --raw" as a process
    Then the exit code is 12
    And stdout matches the expected file "tlc_raw/violation.txt"
    And java was started without "-tool"

  # R6: the run folder

  Scenario: A raw run that ends normally leaves no run folder and no lock file
    Given java replays "tlc/v1.7.4/plain/success" with exit code 0
    When I run "tlaup tlc Success --raw" as a process
    Then the exit code is 0
    And the cache holds no run folders
    And the cache holds no lock files

  # R11: the same preflight as a parsed run

  Scenario: A raw run of a spec that does not exist exits 4 before Java starts
    When I run "tlaup tlc Nosuch --raw" as a process
    Then the exit code is 4
    And stdout is empty
    And stderr contains "error:" 1 times
    And java was not started

  Scenario: A raw run without Java exits 3
    Given java is not installed
    When I run "tlaup tlc Success --raw" as a process
    Then the exit code is 3
    And stdout is empty
    And stderr contains "error:" 1 times
    And java did not run "tlc2.TLC"

  # R1 and D58: a closed output pipe stops TLC (Linux and macOS; on Windows --raw does not, R1)

  Scenario: When the reader of a raw run goes away, TLC is stopped and tlaup exits 141
    Given java prints 60 lines
    And java pauses 1000 ms between lines
    When I run "tlaup tlc Success --raw" as a process whose reader closes after 1 line
    Then the exit code is 141
    And stderr does not contain "Traceback"
    And java received SIGTERM
    And the java process has exited
