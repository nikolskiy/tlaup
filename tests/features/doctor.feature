Feature: tlaup doctor
  "doctor" prints one line per check as "<name>: <level>, <detail>", with ok, warning or error, re-runs the Java
  version checks and exits 3 when a check is an error (design 23 C1, 13 J3). It makes no request and writes
  nothing but the remembered Java check.

  Scenario: With everything set up every line is ok, and the Java check is run again
    Given the build "v1.7.4" is installed and pinned
    And JAVA_HOME is a JDK of version "25.0.5"
    When I run "tlaup doctor"
    Then the exit code is 0
    And stdout contains "java: ok"
    And stdout contains "javac: ok"
    And stdout contains "pinned build: ok"
    And stdout contains "config file: ok"
    And stdout contains "JAVA_HOME"
    And stderr is empty
    And java was started with "-version"
    And java did not run "tlc2.TLC"

  Scenario: The GitHub token is named by its variable and its value is never printed
    Given the build "v1.7.4" is installed and pinned
    And JAVA_HOME is a JDK of version "25.0.5"
    And the environment variable "GITHUB_TOKEN" is "doctor-secret-value"
    When I run "tlaup doctor"
    Then the exit code is 0
    And stdout contains "GitHub token: ok"
    And stdout contains "GITHUB_TOKEN"
    And stdout does not contain "doctor-secret-value"
    And stderr does not contain "doctor-secret-value"

  # Java

  Scenario: No Java is an error, and the other checks still print
    Given the build "v1.7.4" is installed and pinned
    And java is not installed
    When I run "tlaup doctor"
    Then the exit code is 3
    And stdout contains "java: error"
    And stdout contains "pinned build: ok"
    And stderr contains "error:" 1 times
    And stderr does not contain "Traceback"

  Scenario: A Java that is too old is an error
    Given the build "v1.7.4" is installed and pinned
    And java is version "1.8.0_202"
    When I run "tlaup doctor"
    Then the exit code is 3
    And stdout contains "java: error"
    And stderr contains "error:" 1 times
    And stderr does not contain "Traceback"

  Scenario: A JAVA_HOME with no Java in it is a warning, and PATH is used
    Given the build "v1.7.4" is installed and pinned
    And java is version "25.0.5"
    And JAVA_HOME is an empty folder
    When I run "tlaup doctor"
    Then the exit code is 0
    And stdout contains "java: warning"
    And stdout contains "JAVA_HOME"

  Scenario: No javac is a warning
    Given the build "v1.7.4" is installed and pinned
    And java is version "25.0.5"
    And javac is not installed
    When I run "tlaup doctor"
    Then the exit code is 0
    And stdout contains "javac: warning"

  Scenario: The Java check is run again each time
    Given the build "v1.7.4" is installed and pinned
    And java is version "21.0.1"
    When I run "tlaup doctor"
    Given java is replaced by version "25.0.5"
    When I run "tlaup doctor"
    Then the exit code is 0
    And stdout contains "25.0.5"

  Scenario: The macOS stub with no JDK is an error that shows what it printed
    Given the build "v1.7.4" is installed and pinned
    And java answers its version check with "Unable to locate a Java Runtime." on stderr and exit code 1
    When I run "tlaup doctor"
    Then the exit code is 3
    And stdout contains "java: error"
    And stdout contains "Unable to locate a Java Runtime."
    And stderr contains "error:" 1 times
    And stderr does not contain "Traceback"

  Scenario: An answer that is not a version is a warning, and the run goes on
    Given the build "v1.7.4" is installed and pinned
    And java answers its version check with "not a version" on stdout and exit code 0
    When I run "tlaup doctor"
    Then the exit code is 0
    And stdout contains "java: warning"

  # The pinned build

  Scenario: No build installed is an error that names tool install
    Given no build is installed
    And JAVA_HOME is a JDK of version "25.0.5"
    When I run "tlaup doctor"
    Then the exit code is 3
    And stdout contains "pinned build: error"
    And stdout contains "tlaup tool install"
    And stderr contains "error:" 1 times
    And stderr does not contain "Traceback"

  Scenario: Builds installed and none pinned is an error that names tool pin
    Given the build "v1.7.4" is installed
    And JAVA_HOME is a JDK of version "25.0.5"
    When I run "tlaup doctor"
    Then the exit code is 3
    And stdout contains "pinned build: error"
    And stdout contains "tlaup tool pin"
    And stderr contains "error:" 1 times
    And stderr does not contain "Traceback"

  Scenario: A truncated jar is an error that names install --force
    Given the build "v1.7.4" is installed and pinned
    And the jar of the build "v1.7.4" is truncated
    And JAVA_HOME is a JDK of version "25.0.5"
    When I run "tlaup doctor"
    Then the exit code is 3
    And stdout contains "pinned build: error"
    And stdout contains "--force"
    And stderr contains "error:" 1 times
    And stderr does not contain "Traceback"

  Scenario: A pin that names a build that is gone is an error
    Given a file "{tools}/pin" containing:
      """
      v9.9.9-000000000000
      """
    And JAVA_HOME is a JDK of version "25.0.5"
    When I run "tlaup doctor"
    Then the exit code is 3
    And stdout contains "pinned build: error"
    And stderr contains "error:" 1 times
    And stderr does not contain "Traceback"

  # Leftovers

  Scenario: A folder in the tool folder that is not a build is a warning and is kept
    Given the build "v1.7.4" is installed and pinned
    And JAVA_HOME is a JDK of version "25.0.5"
    And a file "{tools}/old-build/tla2tools.jar" containing:
      """
      not a jar
      """
    When I run "tlaup doctor"
    Then the exit code is 0
    And stdout contains "tool folder: warning"
    And stdout contains "old-build"
    And the file "{tools}/old-build/tla2tools.jar" exists

  Scenario: A module folder that is not a module is a warning and is kept
    Given the build "v1.7.4" is installed and pinned
    And JAVA_HOME is a JDK of version "25.0.5"
    And a file "{modules}/broken/module.json" containing:
      """
      this is not JSON
      """
    When I run "tlaup doctor"
    Then the exit code is 0
    And stdout contains "module folder: warning"
    And stdout contains "broken"
    And the file "{modules}/broken/module.json" exists

  # The config file

  Scenario: An unknown key is a warning
    Given the build "v1.7.4" is installed and pinned
    And JAVA_HOME is a JDK of version "25.0.5"
    And the config file contains:
      """
      tlc:
        wokers: 4
      """
    When I run "tlaup doctor"
    Then the exit code is 0
    And stdout contains "config file: warning"
    And stdout contains "wokers"

  Scenario: A config file that does not parse is an error, and the other checks still print
    Given the build "v1.7.4" is installed and pinned
    And JAVA_HOME is a JDK of version "25.0.5"
    And the config file contains:
      """
      tlc: [unclosed
      """
    When I run "tlaup doctor"
    Then the exit code is 3
    And stdout contains "config file: error"
    And stdout contains "tlaup config edit"
    And stdout contains "java: ok"
    And stderr contains "error:" 1 times
    And stderr does not contain "Traceback"

  # The folders

  Scenario: A run folder that cannot be written is an error
    Given the build "v1.7.4" is installed and pinned
    And JAVA_HOME is a JDK of version "25.0.5"
    And a file "{runs}/x" containing:
      """
      x
      """
    And the folder "{runs}" is read-only
    When I run "tlaup doctor"
    Then the exit code is 3
    And stdout contains "run folder: error"
    And stderr contains "error:" 1 times
    And stderr does not contain "Traceback"

  # What it does not do

  Scenario: On a fresh home doctor writes nothing but the Java check, and makes no request
    Given java is version "25.0.5"
    When I run "tlaup doctor"
    Then the file "{config}/config.yaml" does not exist
    And the cache holds no run folders
    And stdout contains "config file: ok"
