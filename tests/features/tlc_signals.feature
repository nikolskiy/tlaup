Feature: Stopping tlaup tlc with a signal
  A signal to tlaup is passed on to TLC: the first stops it, a second kills it, and tlaup exits 130 for SIGINT and
  143 for SIGTERM with TLC gone. A first signal while TLC writes a checkpoint waits for the checkpoint; a second
  stops at once. In a parsed run the JVM has a process group of its own, so a Ctrl-C at the terminal reaches tlaup
  alone (design 11 R2 and R6, 20 G3, decisions D52 and D60; inventory row R14). tlaup runs as a real process, and
  the signal goes to the tlaup process alone, so each scenario shows the forwarding. The fake java gets SIGTERM from
  tlaup whichever signal tlaup received.

  Background:
    Given the build "v1.7.4" is installed and pinned

  # R2 and G3: one signal, and two

  Scenario Outline: <signal> to tlaup stops a parsed run, keeps what was printed and exits <code>
    Given a spec "Slow" from the golden specs
    And java replays "tlc/v1.7.4/checkpoint-run" with exit code 0
    And java hangs after line 35
    When I start "tlaup tlc Slow" and send <signal> once java is running
    Then the exit code is <code>
    And stdout contains "Warning: Please run the Java VM"
    And stdout contains "Result: incomplete, interrupted after" 1 times
    And stderr does not contain "Traceback"
    And java received SIGTERM
    And the java process has exited

    Examples:
      | signal  | code |
      | SIGTERM | 143  |
      | SIGINT  | 130  |

  Scenario Outline: <signal> to tlaup stops a raw run and exits <code>
    Given a spec "Success" from the golden specs
    And java replays "tlc/v1.7.4/plain/success" with exit code 0
    And java hangs after line 3
    When I start "tlaup tlc Success --raw" and send <signal> once java is running
    Then the exit code is <code>
    And stderr does not contain "Traceback"
    And java was started without "-tool"
    And java received SIGTERM
    And the java process has exited

    Examples:
      | signal  | code |
      | SIGTERM | 143  |
      | SIGINT  | 130  |

  # The fake ignores the SIGTERM tlaup sends for the first SIGINT, so it is still running when the second comes.

  Scenario: A second SIGINT kills a parsed run that did not stop, exits 130 and keeps the result line
    Given a spec "Slow" from the golden specs
    And java replays "tlc/v1.7.4/checkpoint-run" with exit code 0
    And java hangs after line 35
    And java ignores SIGTERM
    When I start "tlaup tlc Slow" and send SIGINT twice
    Then the exit code is 130
    And stdout contains "Result: incomplete, interrupted after" 1 times
    And stderr does not contain "Traceback"
    And java received SIGTERM
    And the java process has exited

  Scenario: A second SIGINT kills a raw run that did not stop and exits 130
    Given a spec "Success" from the golden specs
    And java replays "tlc/v1.7.4/plain/success" with exit code 0
    And java hangs after line 3
    And java ignores SIGTERM
    When I start "tlaup tlc Success --raw" and send SIGINT twice
    Then the exit code is 130
    And stderr does not contain "Traceback"
    And java received SIGTERM
    And the java process has exited

  # R6: an interrupted run under --keep keeps its complete checkpoint

  Scenario Outline: SIGINT to a run under --keep with a complete checkpoint keeps its run folder: <mode>
    Given a spec "Slow" from the golden specs
    And java replays "tlc/v1.7.4/checkpoint-run" with exit code 0
    And java writes "queue.chkpt, vars.chkpt" into its metadir
    And java hangs after line 35
    When I start "tlaup tlc Slow --keep <flags>" and send SIGINT once java is running
    Then the exit code is 130
    And the cache holds 1 run folder
    And stderr contains "Checkpoint kept (" 1 times
    And stderr contains "interrupted"
    And stderr contains "): {kept}"
    And stderr contains "Resume with: tlaup tlc {work}/Slow.tla"
    And java received SIGTERM

    Examples:
      | mode   | flags |
      | parsed |       |
      | raw    | --raw |

  # R6, G3 and question Q10: the checkpoint deferral. The fake prints 2195 (lines 36 to 38), begins its checkpoint,
  # and commits it before 2196 (lines 39 to 41), after which it hangs. The deferral is shown by the one waiting
  # line and the kept, complete checkpoint (package 37's note), not by what the fake was sent at any moment. The
  # pause between lines lets tlaup read 2195 before the fake marks its checkpoint, as a real TLC's would: a signal
  # that comes while 2195 still waits in tlaup's queue is sent on at once (01 T5's window, finding FC8).

  Scenario: A first SIGINT while TLC writes its checkpoint waits for it, and the complete checkpoint is kept
    Given a spec "Slow" from the golden specs
    And java replays "tlc/v1.7.4/checkpoint-run" with exit code 0
    And java pauses 20 ms between lines
    And java begins a checkpoint after line 38 and commits it before line 39
    And java hangs after line 41
    When I start "tlaup tlc Slow --keep" and send SIGINT once java has begun its checkpoint
    Then the exit code is 130
    And stderr contains "waiting for TLC to finish writing its checkpoint; press Ctrl-C again to stop now" 1 times
    And java received SIGTERM
    And the cache holds 1 run folder
    And stderr contains "Checkpoint kept (" 1 times
    And stdout does not contain "the checkpoint was incomplete"
    And the java process has exited

  Scenario: A second SIGINT while TLC writes its checkpoint stops it at once, and nothing is kept
    Given a spec "Slow" from the golden specs
    And java replays "tlc/v1.7.4/checkpoint-run" with exit code 0
    And java pauses 20 ms between lines
    And java begins a checkpoint after line 38 and commits it before line 39
    And java hangs after line 41
    When I start "tlaup tlc Slow --keep" and send SIGINT once java has begun its checkpoint, and again once stderr contains "waiting for TLC to finish writing its checkpoint"
    Then the exit code is 130
    And stderr contains "waiting for TLC to finish writing its checkpoint" 1 times
    And java received no signal
    And the cache holds no run folders
    And the cache holds no lock files
    And stdout contains "the checkpoint was incomplete, nothing to resume" 1 times
    And stderr does not contain "Checkpoint kept"
    And the java process has exited

  # D60 on a pseudo-terminal: the keys go to the terminal's foreground group, tlaup's

  Scenario: Ctrl-C at the terminal during a parsed run reaches tlaup and not TLC, which has a group of its own
    Given a spec "Success" from the golden specs
    And java replays "tlc/v1.7.4/success" with exit code 0
    And java hangs after line 6
    When I start "tlaup tlc Success" in a terminal 100 by 30 and press Ctrl-C once the terminal has shown "TLC v1.7.4@" and then "Please run the Java VM"
    Then the exit code is 130
    And java received SIGTERM
    And java ran in its own process group
    And the terminal contains "Result: incomplete, interrupted after"
    And the terminal does not contain "Traceback"
    And the java process has exited

  Scenario: Ctrl-\ at the terminal during a parsed run is passed to TLC as SIGQUIT and changes nothing else
    Given a spec "Success" from the golden specs
    And java replays "tlc/v1.7.4/success" with exit code 0
    And java pauses 100 ms between lines
    When I start "tlaup tlc Success" in a terminal 100 by 30 and press Ctrl-\ once the terminal has shown "TLC v1.7.4@" and then "Please run the Java VM"
    Then the exit code is 0
    And java received SIGQUIT
    And java ran in its own process group
    And the terminal contains "Result: no error found, every state checked (TLC exit code 0)"
    And the terminal does not contain "Traceback"

  # The fake ignores the terminal's SIGINT, so it is still running when tlaup's SIGTERM comes.

  Scenario: With --raw a Ctrl-C at the terminal reaches TLC itself, in tlaup's process group
    Given a spec "Success" from the golden specs
    And java replays "tlc/v1.7.4/plain/success" with exit code 0
    And java hangs after line 3
    And java ignores SIGINT
    When I start "tlaup tlc Success --raw" in a terminal 100 by 30 and press Ctrl-C once the terminal has shown "TLC2 Version" and then "Use the -nowarning option"
    Then the exit code is 130
    And java received SIGINT, then SIGTERM
    And java ran in tlaup's process group
    And the terminal does not contain "Traceback"
    And the java process has exited

  Scenario: Ctrl-C at the terminal while TLC writes its checkpoint waits for it, and the complete checkpoint is kept
    Given a spec "Slow" from the golden specs
    And java replays "tlc/v1.7.4/checkpoint-run" with exit code 0
    And java pauses 20 ms between lines
    And java begins a checkpoint after line 38 and commits it before line 39
    And java hangs after line 41
    When I start "tlaup tlc Slow --keep" in a terminal 100 by 30 and press Ctrl-C once java has begun its checkpoint
    Then the exit code is 130
    And java received SIGTERM
    And java ran in its own process group
    And the terminal contains "waiting for TLC to finish writing its checkpoint; press Ctrl-C again to stop now"
    And the cache holds 1 run folder
    And the terminal contains "Checkpoint kept ("
    And the java process has exited
