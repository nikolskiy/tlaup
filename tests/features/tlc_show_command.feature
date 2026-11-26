Feature: tlaup tlc --show-command
  --show-command prints the Java command a run would start, as one shell-quoted line on stdout, without the
  lifeline agent, and starts nothing but the Java version check: no run folder, no lock, no question, no
  install (design 11 R9, 20 G1, decisions D45 and D51; inventory row R11).

  Background:
    Given a spec "Success" from the golden specs
    And java is version "25.0.5"

  Scenario: The command is one line with the encoding options, -fp and -seed, and no lifeline agent
    Given the build "v1.7.4" is installed and pinned
    When I run "tlaup tlc Success --show-command"
    Then the exit code is 0
    And stderr is empty
    And stdout contains "tlc2.TLC" 1 times
    And stdout does not contain "-javaagent"
    And stdout contains " -Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8 "
    And stdout contains " tlc2.TLC -tool -metadir {runs}/"
    And stdout contains " -fp "
    And stdout contains " -seed "
    And stdout contains " {work}/Success.tla"

  Scenario: With -fp, -seed and -metadir given, the command holds them as given and nothing random
    Given the build "v1.7.4" is installed and pinned
    When I run "tlaup tlc Success --show-command -- -fp 3 -seed 7 -metadir {work}/m"
    Then the exit code is 0
    And stdout contains " -XX:+IgnoreUnrecognizedVMOptions -XX:+UseParallelGC -cp {tools}/"
    And stdout contains "/tla2tools.jar tlc2.TLC -tool -workers auto -fp 3 -seed 7 -metadir {work}/m {work}/Success.tla" 1 times
    And stdout does not contain "{runs}"

  Scenario: --show-command makes no run folder and no lock, and starts java only for its version
    Given the build "v1.7.4" is installed and pinned
    When I run "tlaup tlc Success --show-command"
    Then the exit code is 0
    And the cache holds no run folders
    And the cache holds no lock files
    And java was started 1 time
    And java did not run "tlc2.TLC"

  Scenario: With --raw the command has no -tool
    Given the build "v1.7.4" is installed and pinned
    When I run "tlaup tlc Success --raw --show-command"
    Then the exit code is 0
    And stdout contains " tlc2.TLC -metadir "
    And stdout does not contain "-tool"

  Scenario: With --coverage, -coverage 1 stands before the spec
    Given the build "v1.7.4" is installed and pinned
    When I run "tlaup tlc Success --coverage --show-command -- -fp 3 -seed 7"
    Then the exit code is 0
    And stdout contains " -workers auto -coverage 1 -fp 3 -seed 7 {work}/Success.tla"

  Scenario Outline: With no build pinned it exits 3, and nothing is asked or installed: <flags>
    Given the build "v1.7.4" is installed
    And GitHub answers from "releases"
    When I run "tlaup tlc Success --show-command <flags>"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr does not contain "Which build"
    And 0 requests were sent to GitHub
    And no build is pinned

    Examples:
      | flags                  |
      |                        |
      | --auto-install rolling |

  Scenario: A path with square brackets is printed as text, not read as markup
    Given the build "v1.7.4" is installed and pinned
    And I am in the folder "{work}/a [b] :x:"
    And a spec "Success" from the golden specs
    When I run "tlaup tlc Success --show-command"
    Then the exit code is 0
    And stdout contains "a [b] :x:/Success.tla'"
