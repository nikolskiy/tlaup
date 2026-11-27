Feature: The cache commands
  "cache dir" prints the cache folder, "cache list" shows the run folders, and "cache clean" removes what nothing
  will use again: run folders by the rules of design 11 R6, the remembered GitHub lookups and, with "--all" and no
  kind named, the remembered Java check. Installed tools and modules are never touched (design 23 C1).

  # cache dir and the group

  Scenario: cache dir prints the cache folder and creates nothing
    When I run "tlaup cache dir"
    Then the exit code is 0
    And stdout is exactly "{home}/tlaup/cache"
    And stderr is empty
    And the file "{home}/tlaup/cache" does not exist

  Scenario: The group without its command prints the usage on stdout and exits 2
    When I run "tlaup cache"
    Then the exit code is 2
    And stdout contains "Usage:"
    And stderr is empty

  # cache list

  Scenario: With no run folders cache list prints nothing
    When I run "tlaup cache list"
    Then the exit code is 0
    And stdout is empty
    And stderr is empty

  Scenario: cache list shows a kept folder and the total of the kept ones
    Given the build "v1.7.4" is installed and pinned
    And a spec "Slow" from the golden specs
    And java replays "tlc/v1.7.4/checkpoint-run" with exit code 255
    And java writes "queue.chkpt, vars.chkpt" into its metadir
    When I run "tlaup tlc Slow --keep --cfg Slow.cfg -- -checkpoint 1"
    And I run "tlaup cache list"
    Then the exit code is 0
    And stdout contains "{kept-id}" 1 times
    And stdout contains "Slow.tla Slow.cfg"
    And stdout contains "v1.7.4"
    And stdout contains " B"
    And stdout contains "kept: TLC crashed (exit 255)"
    And stdout contains "checkpoint complete"
    And stdout contains "1 kept run folder holds "
    And stderr is empty

  # cache clean: what each form removes

  Scenario: cache clean leaves a kept folder
    Given the build "v1.7.4" is installed and pinned
    And a spec "Slow" from the golden specs
    And java replays "tlc/v1.7.4/checkpoint-run" with exit code 255
    And java writes "queue.chkpt, vars.chkpt" into its metadir
    When I run "tlaup tlc Slow --keep --cfg Slow.cfg -- -checkpoint 1"
    And I run "tlaup cache clean"
    Then the exit code is 0
    And stdout is empty
    And the cache holds 1 run folder

  Scenario: cache clean with the id of a kept folder removes it and its lock file and nothing else
    Given the build "v1.7.4" is installed and pinned
    And a spec "Slow" from the golden specs
    And java replays "tlc/v1.7.4/checkpoint-run" with exit code 255
    And java writes "queue.chkpt, vars.chkpt" into its metadir
    And a file "{runs}/../remote/0123456789abcdef.json" containing:
      """
      {}
      """
    When I run "tlaup tlc Slow --keep --cfg Slow.cfg -- -checkpoint 1"
    And I run "tlaup cache clean {kept-id}"
    Then the exit code is 0
    And stdout is empty
    And stderr contains "removed run folder "
    And the cache holds no run folders
    And the cache holds no lock files
    And the file "{runs}/../remote/0123456789abcdef.json" exists

  Scenario: cache clean --all removes a kept folder and an unsettled resumable one that plain cache clean leaves
    Given the build "v1.7.4" is installed and pinned
    And a spec "Slow" from the golden specs
    And java replays "tlc/v1.7.4/checkpoint-run" with exit code 255
    And java writes "queue.chkpt, vars.chkpt" into its metadir
    And a file "{runs}/20260101T000000Z-aaaaaaaa/run.json" containing:
      """
      {"spec": "Hand.tla", "keep": true, "kept": false, "ended": null, "started": "2026-01-01T00:00:00Z"}
      """
    And a file "{runs}/20260101T000000Z-aaaaaaaa/queue.chkpt" containing:
      """
      x
      """
    And a file "{runs}/20260101T000000Z-aaaaaaaa/vars.chkpt" containing:
      """
      x
      """
    When I run "tlaup tlc Slow --keep --cfg Slow.cfg -- -checkpoint 1"
    And I run "tlaup cache clean"
    Then the exit code is 0
    And the cache holds 2 run folders
    When I run "tlaup cache clean --all"
    Then the exit code is 0
    And stderr contains "removed run folder " 2 times
    And the cache holds no run folders

  Scenario: cache clean --remote removes the remembered lookups and leaves run folders
    Given the build "v1.7.4" is installed and pinned
    And a spec "Slow" from the golden specs
    And java replays "tlc/v1.7.4/checkpoint-run" with exit code 255
    And java writes "queue.chkpt, vars.chkpt" into its metadir
    And a file "{runs}/../remote/0123456789abcdef.json" containing:
      """
      {}
      """
    When I run "tlaup tlc Slow --keep --cfg Slow.cfg -- -checkpoint 1"
    And I run "tlaup cache clean --remote"
    Then the exit code is 0
    And stderr contains "removed the remembered GitHub lookups"
    And the file "{runs}/../remote/0123456789abcdef.json" does not exist
    And the cache holds 1 run folder

  Scenario: cache clean --runs removes an unsettled folder that is not resumable and leaves the lookups
    Given a file "{runs}/../remote/0123456789abcdef.json" containing:
      """
      {}
      """
    And a file "{runs}/20260101T000000Z-bbbbbbbb/run.json" containing:
      """
      {"spec": "Hand.tla", "keep": false, "kept": false, "ended": null, "started": "2026-01-01T00:00:00Z"}
      """
    When I run "tlaup cache clean --runs"
    Then the exit code is 0
    And stderr contains "removed run folder 20260101T000000Z-bbbbbbbb"
    And the cache holds no run folders
    And the file "{runs}/../remote/0123456789abcdef.json" exists

  Scenario: cache clean with no option removes both kinds and leaves the Java check
    Given a file "{runs}/../remote/0123456789abcdef.json" containing:
      """
      {}
      """
    And a file "{runs}/../java.json" containing:
      """
      {}
      """
    And a file "{runs}/20260101T000000Z-bbbbbbbb/run.json" containing:
      """
      {"spec": "Hand.tla", "keep": false, "kept": false, "ended": null, "started": "2026-01-01T00:00:00Z"}
      """
    When I run "tlaup cache clean"
    Then the exit code is 0
    And stderr contains "removed run folder 20260101T000000Z-bbbbbbbb"
    And stderr contains "removed the remembered GitHub lookups"
    And stderr contains "freed "
    And the cache holds no run folders
    And the file "{runs}/../remote/0123456789abcdef.json" does not exist
    And the file "{runs}/../java.json" exists

  Scenario: cache clean --all also removes the remembered Java check
    Given a file "{runs}/../java.json" containing:
      """
      {}
      """
    When I run "tlaup cache clean --all"
    Then the exit code is 0
    And stderr contains "removed the remembered Java check"
    And the file "{runs}/../java.json" does not exist

  Scenario: cache clean --runs --all removes kept folders and leaves the lookups and the Java check
    Given the build "v1.7.4" is installed and pinned
    And a spec "Slow" from the golden specs
    And java replays "tlc/v1.7.4/checkpoint-run" with exit code 255
    And java writes "queue.chkpt, vars.chkpt" into its metadir
    And a file "{runs}/../remote/0123456789abcdef.json" containing:
      """
      {}
      """
    And a file "{runs}/../java.json" containing:
      """
      {}
      """
    When I run "tlaup tlc Slow --keep --cfg Slow.cfg -- -checkpoint 1"
    And I run "tlaup cache clean --runs --all"
    Then the exit code is 0
    And the cache holds no run folders
    And the file "{runs}/../remote/0123456789abcdef.json" exists
    And the file "{runs}/../java.json" exists

  Scenario: cache clean --remote --all removes the lookups and leaves kept folders and the Java check
    Given the build "v1.7.4" is installed and pinned
    And a spec "Slow" from the golden specs
    And java replays "tlc/v1.7.4/checkpoint-run" with exit code 255
    And java writes "queue.chkpt, vars.chkpt" into its metadir
    And a file "{runs}/../remote/0123456789abcdef.json" containing:
      """
      {}
      """
    And a file "{runs}/../java.json" containing:
      """
      {}
      """
    When I run "tlaup tlc Slow --keep --cfg Slow.cfg -- -checkpoint 1"
    And I run "tlaup cache clean --remote --all"
    Then the exit code is 0
    And the cache holds 1 run folder
    And the file "{runs}/../remote/0123456789abcdef.json" does not exist
    And the file "{runs}/../java.json" exists

  Scenario: cache clean leaves installed tools and modules alone
    Given the build "v1.7.4" is installed and pinned
    And a file "{modules}/Mine/module.json" containing:
      """
      {}
      """
    When I run "tlaup cache clean --all"
    Then the exit code is 0
    And the file "{modules}/Mine/module.json" exists
    When I run "tlaup tool current"
    Then the exit code is 0
    And stdout contains "v1.7.4"

  # Nothing to clean, and what cannot be removed

  Scenario: Nothing to clean on a fresh home is not an error
    When I run "tlaup cache clean"
    Then the exit code is 0
    And stdout is empty
    And stderr contains "nothing was removed"
    And stderr does not contain "error:"

  Scenario: A second clean after cache clean --all removes nothing and is not an error
    Given the build "v1.7.4" is installed and pinned
    And a spec "Slow" from the golden specs
    And java replays "tlc/v1.7.4/checkpoint-run" with exit code 255
    And java writes "queue.chkpt, vars.chkpt" into its metadir
    When I run "tlaup tlc Slow --keep --cfg Slow.cfg -- -checkpoint 1"
    And I run "tlaup cache clean --all"
    Then the exit code is 0
    When I run "tlaup cache clean --all"
    Then the exit code is 0
    And stdout is empty
    And stderr contains "nothing was removed"
    And stderr does not contain "error:"

  Scenario: A fresh lock file with no folder is left alone
    Given a file "{runs}/x.lock" containing:
      """
      """
    When I run "tlaup cache clean"
    Then the exit code is 0
    And the file "{runs}/x.lock" exists

  Scenario: cache clean with an id that names no folder exits 4
    When I run "tlaup cache clean nosuch"
    Then the exit code is 4
    And stdout is empty
    And stderr contains "error:" 1 times

  Scenario: cache clean with an id and --all is a usage error and removes nothing
    Given the build "v1.7.4" is installed and pinned
    And a spec "Slow" from the golden specs
    And java replays "tlc/v1.7.4/checkpoint-run" with exit code 255
    And java writes "queue.chkpt, vars.chkpt" into its metadir
    When I run "tlaup tlc Slow --keep --cfg Slow.cfg -- -checkpoint 1"
    And I run "tlaup cache clean {kept-id} --all"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "error:" 1 times
    And the cache holds 1 run folder
