Feature: The live view of tlaup tlc on a terminal
  With both streams on a terminal, tlaup tlc draws a full-screen layout on stderr while TLC runs, redrawn at
  --refresh-interval, and when the run ends the layout closes and the complete result is printed as plain output.
  Redirected output, a terminal smaller than 60 by 15, --plain and tlc.plain give plain output (design 22 O4 and
  O5, 02 X2, decisions D30 and D40). Real processes on a pseudo-terminal, read through a terminal emulator; no pty
  on Windows (D15).

  Background:
    Given the build "v1.7.4" is installed and pinned

  # O4: the last frame and the scrollback

  Scenario: A run on a terminal shows the layout, and the terminal keeps the plain result after it closes
    Given a spec "Violation" from the golden specs
    And java replays "tlc/v1.7.4/violation" with exit code 12
    And java's output has "<tmp>/q01/run" replaced by "{work}"
    When I run "tlaup tlc Violation" in a terminal 100 by 30
    Then the exit code is 12
    And the terminal showed the layout
    And the last layout frame contains "Finished"
    And the last layout frame contains "errors 1   warnings 1"
    And the last layout frame contains "44 states generated, 44 distinct, 35 on queue, diameter 4"
    And the terminal ends with the expected file "tlc_live/violation.txt"

  # O4 and O5, T12 rule 5: the one scenario that depends on the real clock. The fake falls silent about 0.6
  # seconds in (line 26 starts 2190, which sets Checking; lines 29 to 31 are the first progress message), so only
  # the refresh thread can draw a later elapsed time.

  Scenario: The display updates while TLC is silent
    Given a spec "Big" from the golden specs
    And java replays "tlc/v1.7.4/big-states" with exit code 0
    And java pauses 20 ms between lines
    And java hangs after line 31
    When I start "tlaup tlc Big --refresh-interval 0.2" in a terminal 100 by 30 and press Ctrl-C once the terminal has shown "Checking" and then an elapsed time 2 seconds later
    Then the exit code is 130
    And the terminal showed the layout
    And the last layout frame contains "Interrupted"
    And the terminal contains "Result: incomplete, interrupted after"
    And the java process has exited

  # D30: the layout needs stdout on the terminal too

  # 39's expected file holds no escape sequence, so matching it shows the file has none.

  Scenario: With stdout redirected the terminal stays on the main screen with plain progress, and the file has the result
    Given a spec "Violation" from the golden specs
    And java replays "tlc/v1.7.4/violation" with exit code 12
    And java's output has "<tmp>/q01/run" replaced by "{work}"
    When I run "tlaup tlc Violation" in a terminal 100 by 30 with stdout redirected to "out.txt"
    Then the exit code is 12
    And the terminal stayed on the main screen
    And the terminal contains "TLC v1.7.4@5a47802, Java"
    And the terminal contains "44 states generated, 44 distinct"
    And the file "out.txt" matches the expected file "tlc_run/violation.txt"

  # O4: a terminal smaller than 60 by 15

  Scenario: A terminal of 50 by 10 gets plain output
    Given a spec "Violation" from the golden specs
    And java replays "tlc/v1.7.4/violation" with exit code 12
    When I run "tlaup tlc Violation" in a terminal 50 by 10
    Then the exit code is 12
    And the terminal stayed on the main screen
    And the terminal contains "44 states generated, 44 distinct"

  # O4: plain output asked for

  Scenario: With --plain the terminal stays on the main screen with plain output
    Given a spec "Violation" from the golden specs
    And java replays "tlc/v1.7.4/violation" with exit code 12
    When I run "tlaup tlc Violation --plain" in a terminal 100 by 30
    Then the exit code is 12
    And the terminal stayed on the main screen
    And the terminal contains "TLC v1.7.4@5a47802, Java"
    And the terminal contains "44 states generated, 44 distinct"

  Scenario: With TLAUP_TLC_PLAIN=1 and no flag the terminal stays on the main screen with plain output
    Given a spec "Violation" from the golden specs
    And java replays "tlc/v1.7.4/violation" with exit code 12
    And the environment variable "TLAUP_TLC_PLAIN" is "1"
    When I run "tlaup tlc Violation" in a terminal 100 by 30
    Then the exit code is 12
    And the terminal stayed on the main screen
    And the terminal contains "TLC v1.7.4@5a47802, Java"
    And the terminal contains "44 states generated, 44 distinct"

  Scenario: With --raw --plain the run is a raw run
    Given a spec "Violation" from the golden specs
    And java replays "tlc/v1.7.4/plain/violation" with exit code 12
    When I run "tlaup tlc Violation --raw --plain" in a terminal 100 by 30
    Then the exit code is 12
    And the terminal stayed on the main screen
    And the terminal contains "TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)"
    And the terminal contains "Error: Invariant Small is violated."
