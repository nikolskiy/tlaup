Feature: Translating PlusCal with the translator
  "tlaup pcal SPEC [-- translator arguments]" runs the PlusCal translator in the spec's folder on the pinned build,
  prints each error on stdout in the editor form with the spec's path, each label the translator added as
  path:line:col: label NAME added, and every line it does not recognise as written, says on stderr which files it
  wrote, and exits with the translator's own code (design 21 S2, decisions D29, D30 and D67). The fake java replays
  the PlusCal golden captures and writes no files.

  # S2, step 4: a good spec gives the two notes, on stderr

  Scenario Outline: A good spec gives exit 0, the two notes on stderr and nothing on stdout on <build>
    Given the build "<build>" is installed and pinned
    And a spec "Pcal" from the golden specs
    And java replays "pcal/<golden>/pcal-good" with exit code 0
    When I run "tlaup pcal Pcal"
    Then the exit code is 0
    And stderr contains "Pcal.tla translated (previous version saved as Pcal.old)"
    And stderr contains "Pcal.cfg written"
    And stdout is empty
    And java ran "pcal.trans" 1 time

    Examples:
      | build   | golden            |
      | v1.7.4  | v1.7.4            |
      | rolling | 2026.11.15.002146 |

  # S2, step 4: an error in the editor form, and the translator's code

  Scenario Outline: A syntax error gives one editor-form line and exit 255 on <build>
    Given the build "<build>" is installed and pinned
    And a spec "PcalSyn" from the golden specs
    And java replays "pcal/<golden>/pcal-syntaxerr" with exit code 255
    When I run "tlaup pcal PcalSyn"
    Then the exit code is 255
    And stdout contains "PcalSyn.tla:6:20: error: Expected "do" but found ":="" 1 times
    And stderr does not contain "translated"
    And stderr does not contain "written"

    Examples:
      | build   | golden            |
      | v1.7.4  | v1.7.4            |
      | rolling | 2026.11.15.002146 |

  Scenario Outline: The doubled full stop is trimmed, and an error with no position has none in its line on <build>
    Given the build "<build>" is installed and pinned
    And a spec "PcalNoAlg" from the golden specs
    And java replays "pcal/<golden>/pcal-noalg" with exit code 255
    When I run "tlaup pcal PcalNoAlg"
    Then the exit code is 255
    And stdout contains "PcalNoAlg.tla: error: Beginning of algorithm string --algorithm not found."
    And stdout does not contain "found.."

    Examples:
      | build   | golden            |
      | v1.7.4  | v1.7.4            |
      | rolling | 2026.11.15.002146 |

  Scenario Outline: -writeAST exits 255 after succeeding, and no file is said to be translated on <build>
    Given the build "<build>" is installed and pinned
    And a spec "Pcal" from the golden specs
    And java replays "pcal/<golden>/pcal-writeast" with exit code 255
    When I run "tlaup pcal Pcal -- -writeAST"
    Then the exit code is 255
    And java was started with "-writeAST"
    And stdout contains "Wrote file AST.tla."
    And stderr does not contain "translated"

    Examples:
      | build   | golden            |
      | v1.7.4  | v1.7.4            |
      | rolling | 2026.11.15.002146 |

  # S2, step 4, decision D67: each label the translator added, on stdout, in the position form

  Scenario Outline: -label -reportLabels gives the added label as one line on stdout on <build>
    Given the build "<build>" is installed and pinned
    And a spec "PcalNoLabel" from the golden specs
    And java replays "pcal/<golden>/pcal-label" with exit code 0
    When I run "tlaup pcal PcalNoLabel -- -label -reportLabels"
    Then the exit code is 0
    And java was started with "-label"
    And java was started with "-reportLabels"
    And stdout is exactly "PcalNoLabel.tla:7:3: label Lbl_1 added"
    And stderr contains "PcalNoLabel.tla translated (previous version saved as PcalNoLabel.old)"
    And stderr contains "PcalNoLabel.cfg written"

    Examples:
      | build   | golden            |
      | v1.7.4  | v1.7.4            |
      | rolling | 2026.11.15.002146 |

  # S2, step 4: passthrough after --

  Scenario Outline: -nocfg after -- reaches the translator and only the spec is translated on <build>
    Given the build "<build>" is installed and pinned
    And a spec "Pcal" from the golden specs
    And java replays "pcal/<golden>/pcal-nocfg" with exit code 0
    When I run "tlaup pcal Pcal -- -nocfg"
    Then the exit code is 0
    And java was started with "-nocfg"
    And stderr contains "Pcal.tla translated"
    And stderr does not contain "Pcal.cfg written"

    Examples:
      | build   | golden            |
      | v1.7.4  | v1.7.4            |
      | rolling | 2026.11.15.002146 |

  # D9: nothing that is not recognised is lost; the banner and the completion lines are not printed

  Scenario: Nothing recognised is printed, and an unrecognised line is printed as written
    Given the build "rolling" is installed and pinned
    And a spec "Pcal" from the golden specs
    And java replays "pcal/2026.11.15.002146/pcal-spec" with exit code 255
    When I run "tlaup pcal Pcal -- -spec Foo"
    Then the exit code is 255
    And stdout does not contain "Parsing completed."
    And stderr does not contain "Parsing completed."
    And stdout does not contain "Translation completed."
    And stdout does not contain "pcal.trans Version"
    And stdout contains "Wrote file AST.tla."
    And stdout contains "Could not find resource file Foo.tla."
    And stdout contains "the +cal translator is installed."

  # S2, step 2: the working folder is the spec's folder, and the file name is bare

  Scenario: The translator is started in the spec's folder with the bare file name, from another folder
    Given the build "v1.7.4" is installed and pinned
    And a file "specs/Pcal.tla" containing:
      """
      ---- MODULE Pcal ----
      ====
      """
    And java replays "pcal/v1.7.4/pcal-good" with exit code 0
    And I am in the folder "{work}/elsewhere"
    When I run "tlaup pcal ../specs/Pcal"
    Then the exit code is 0
    And java was started with "Pcal.tla"
    And java was started without "../specs/Pcal.tla"
    And java was started in the folder "{work}/specs"

  Scenario: --java-opt is in the command that is run
    Given the build "v1.7.4" is installed and pinned
    And a spec "Pcal" from the golden specs
    And java replays "pcal/v1.7.4/pcal-good" with exit code 0
    When I run "tlaup pcal Pcal --java-opt=-Xss8m"
    Then the exit code is 0
    And java was started with "-Xss8m"

  # R11, the order of the preflight: the same steps as sany

  Scenario: A missing spec is not found, and java is not started
    Given the build "v1.7.4" is installed and pinned
    When I run "tlaup pcal NoSuchSpec"
    Then the exit code is 4
    And stdout is empty
    And stderr contains "error:" 1 times
    And java was not started

  Scenario: With no build installed nothing can be asked in-process, and java is not started
    Given no build is installed
    And a spec "Pcal" from the golden specs
    And GitHub answers from "releases"
    When I run "tlaup pcal Pcal"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "error:" 1 times
    And 0 requests were sent to GitHub
    And java was not started

  Scenario: A bad --auto-install is a usage error before the spec is looked at
    Given no build is installed
    And GitHub answers from "releases"
    When I run "tlaup pcal NoSuchSpec --auto-install nonsense"
    Then the exit code is 2
    And stderr contains "error:" 1 times
    And 0 requests were sent to GitHub
    And java was not started
