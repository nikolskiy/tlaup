Feature: Adding, listing and removing Java modules
  "module add" builds a folder in a temporary folder and registers it under the folder's name; "module list"
  shows the registered modules and their build times in UTC; "module remove" deletes one; "module dir" prints
  the folder (design 13 M1 to M3, 14 F2, F8, 23 C1). The compiler is the fake javac, which copies prepared
  class files for the sources it is given.

  # M1: module names

  Scenario Outline: A name that would leave the modules folder is refused and nothing is deleted: <name>
    Given the build "v1.7.4" is installed and pinned
    When I run "tlaup module remove <name>"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "error:" 1 times
    And the file "{tools}/pin" exists

    Examples:
      | name     |
      | ../tool  |
      | ../tools |
      | ..       |
      | .        |
      | a/b      |

  Scenario: A folder whose name is not a valid module name is refused, with a hint to rename it
    Given a file "my module/modules/M.tla" containing:
      """
      ---- MODULE M ----
      ====
      """
    When I run "tlaup module add 'my module'"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr contains "hint: rename the folder"
    And the registered modules are:
      | module |

  Scenario: A name is checked before any setting is read
    Given the config file contains:
      """
      this is: [not valid
      """
    And a file "my module/modules/M.tla" containing:
      """
      ---- MODULE M ----
      ====
      """
    When I run "tlaup module add 'my module'"
    Then the exit code is 2
    And stderr contains "is not a valid module name"

  Scenario: A path that is not a folder is not found
    When I run "tlaup module add nosuch"
    Then the exit code is 4
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr contains "nosuch is not a folder"

  Scenario: A module that is not registered is not found, and the hint says how to see the registered ones
    When I run "tlaup module remove Nosuch"
    Then the exit code is 4
    And stdout is empty
    And stderr contains "error: module 'Nosuch' is not registered"
    And stderr contains "hint: run `tlaup module list`"

  Scenario: The name is the folder's own, however the folder is reached
    Given the build "v1.7.4" is installed and pinned
    And a module source "Queue" from the fake sources
    And I am in the folder "{work}/Queue"
    When I run "tlaup module add ."
    Then the exit code is 0
    And the registered modules are:
      | module |
      | Queue  |

  Scenario: The root of the file system is not a module
    When I run "tlaup module add /"
    Then the exit code is 2
    And stderr contains "error:" 1 times
    And the registered modules are:
      | module |

  # M2: the build in a temporary folder

  Scenario: The first add compiles the Java sources and registers the module
    Given the build "v1.7.4" is installed and pinned
    And a module source "Queue" from the fake sources
    When I run "tlaup module add Queue"
    Then the exit code is 0
    And stdout is empty
    And stderr is exactly "Added module Queue"
    And the registered modules are:
      | module |
      | Queue  |
    And javac was started with "-encoding"
    And javac was started with "UTF-8"
    And javac was started with "--release"
    And javac was started with "11"
    And the file "{modules}/Queue/classes/tlc2/overrides/DirectOverrides.class" exists
    And the file "{modules}/Queue/classes/tlc2/overrides/Constants.class" exists
    And the file "{modules}/Queue/lib/a.jar" exists
    And the file "{modules}/Queue/modules/Queue.tla" exists
    And the file "{modules}/Queue/tlc2/overrides/sub/Constants.java" exists
    And the file "{modules}/Queue/classes/META-INF/services/tlc2.overrides.ITLCOverrides" contains "tlc2.overrides.DirectOverrides"
    And the file "{modules}/Queue/module.json" exists

  Scenario: A compile error shows the compiler's output and the classpath, and keeps the previous build
    Given the build "v1.7.4" is installed and pinned
    And a module source "Queue" from the fake sources
    When I run "tlaup module add Queue"
    Given javac fails with "syntax-error"
    When I run "tlaup module add Queue"
    Then the exit code is 5
    And stdout is empty
    And stderr contains "error: javac failed with exit code 1"
    And stderr contains "error: ';' expected"
    And stderr contains "tla2tools.jar"
    And the file "{modules}/Queue/classes/tlc2/overrides/DirectOverrides.class" exists
    And the registered modules are:
      | module |
      | Queue  |

  Scenario: A compile error in a first add registers nothing
    Given the build "v1.7.4" is installed and pinned
    And a module source "Queue" from the fake sources
    And javac fails with "syntax-error"
    When I run "tlaup module add Queue"
    Then the exit code is 5
    And the registered modules are:
      | module |
    And the file "{modules}/Queue" does not exist

  Scenario: A second add replaces the module and says so
    Given the build "v1.7.4" is installed and pinned
    And a module source "Queue" from the fake sources
    When I run "tlaup module add Queue"
    And I run "tlaup module add Queue"
    Then the exit code is 0
    And stderr is exactly "Replaced module Queue"
    And the registered modules are:
      | module |
      | Queue  |

  Scenario: Java sources and no javac stop with what is missing, and register nothing
    Given the build "v1.7.4" is installed and pinned
    And a module source "Queue" from the fake sources
    And javac is not installed
    When I run "tlaup module add Queue"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr contains "javac"
    And the registered modules are:
      | module |

  Scenario: Java sources and no tools jar stop with what to do, and register nothing
    Given no build is installed
    And a module source "Queue" from the fake sources
    When I run "tlaup module add Queue"
    Then the exit code is 3
    And stdout is empty
    And stderr contains "error:" 1 times
    And stderr contains "hint:" 1 times
    And javac was not started
    And the registered modules are:
      | module |

  Scenario: Builds are installed and none is pinned
    Given the build "v1.7.4" is installed
    And a module source "Queue" from the fake sources
    When I run "tlaup module add Queue"
    Then the exit code is 3
    And stderr contains "no version pinned"
    And javac was not started

  Scenario: A module of .tla files only needs no build and no javac
    Given no build is installed
    And javac is not installed
    And a module source "TlaOnly" from the fake sources
    When I run "tlaup module add TlaOnly"
    Then the exit code is 0
    And stderr is exactly "Added module TlaOnly"
    And the registered modules are:
      | module  |
      | TlaOnly |
    And javac was not started
    And java was not started

  Scenario: The module add never asks GitHub for anything
    Given no build is installed
    And a module source "Queue" from the fake sources
    When I run "tlaup module add Queue"
    Then the exit code is 3
    And javac was not started
    And java was not started

  Scenario: A module is removed
    Given the build "v1.7.4" is installed and pinned
    And a module source "Queue" from the fake sources
    When I run "tlaup module add Queue"
    And I run "tlaup module remove Queue"
    Then the exit code is 0
    And stdout is empty
    And stderr is exactly "Removed module Queue"
    And the registered modules are:
      | module |
    And the file "{modules}/Queue" does not exist

  Scenario: A module removed once is not found the second time
    Given the module "Queue" is registered
    When I run "tlaup module remove Queue"
    And I run "tlaup module remove Queue"
    Then the exit code is 4

  # M3: the javac check and the service file

  Scenario: A javac older than the release is refused, and nothing is compiled
    Given the build "v1.7.4" is installed and pinned
    And a module source "Queue" from the fake sources
    And javac is version "1.8.0_202"
    When I run "tlaup module add Queue"
    Then the exit code is 3
    And stderr contains "javac"
    And javac was started 1 time
    And the registered modules are:
      | module |

  Scenario: A javac of version 25 compiles for release 11
    Given the build "v1.7.4" is installed and pinned
    And a module source "Queue" from the fake sources
    And javac is version "25.0.5"
    When I run "tlaup module add Queue"
    Then the exit code is 0
    And javac was started with "11"

  Scenario: A module whose Java has no override class gets no service file and a warning
    Given the build "v1.7.4" is installed and pinned
    And a module source "NoIndex" from the fake sources
    When I run "tlaup module add NoIndex"
    Then the exit code is 0
    And stderr contains "Added module NoIndex"
    And stderr contains "warning:" 1 times
    And stderr contains "no override index class was found"
    And the file "{modules}/NoIndex/classes/META-INF/services/tlc2.overrides.ITLCOverrides" does not exist
    And the registered modules are:
      | module  |
      | NoIndex |

  Scenario: The warning comes after the line that says the module was added
    Given the build "v1.7.4" is installed and pinned
    And a module source "NoIndex" from the fake sources
    When I run "tlaup module add NoIndex"
    Then stderr matches the expected file "module_add/no-index.txt"

  # C1, F8: list and dir

  Scenario: The registered modules are listed in name order with their build time in UTC
    Given the module "Queue" is registered
    And the module "Alpha" is registered
    When I run "tlaup module list"
    Then the exit code is 0
    And stderr is empty
    And stdout matches the expected file "module_list/two.txt"

  Scenario: With nothing registered the list is empty, and a note says so
    When I run "tlaup module list"
    Then the exit code is 0
    And stdout is empty
    And stderr is exactly "no modules are registered"

  Scenario: The modules folder is printed whether or not it exists
    When I run "tlaup module dir"
    Then the exit code is 0
    And stdout is exactly "{modules}"
    And stderr is empty
    And the file "{modules}" does not exist

  Scenario: The modules folder is printed with a broken config file
    Given the config file contains:
      """
      this is: [not valid
      """
    When I run "tlaup module dir"
    Then the exit code is 0
    And stdout is exactly "{modules}"

  Scenario: The group without a command prints the usage on stdout and exits 2
    When I run "tlaup module"
    Then the exit code is 2
    And stdout contains "Usage"
    And stderr is empty

  Scenario Outline: A command without its argument is a usage error: <command>
    When I run "<command>"
    Then the exit code is 2
    And stdout is empty
    And stderr contains "<argument>"

    Examples:
      | command             | argument |
      | tlaup module add    | PATH     |
      | tlaup module remove | NAME     |
