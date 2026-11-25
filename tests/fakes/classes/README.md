# Prepared classes for the fake `javac`

The fake `javac` (`tests/fakes/javac.py`) compiles nothing: for each source `X.java` it is given, it copies every `X.class` and `X$*.class` found here into its `-d` folder, keeping the path below this folder. The class files are real, compiled once from the sources in `tests/fakes/java-src/` and committed.

Compiled from the repository root with `javac 25.0.5`:

```
javac --release 11 -d tests/fakes/classes tests/fakes/java-src/plain/Plain.java
javac --release 11 -d tests/fakes/classes tests/fakes/java-src/tlc2/overrides/*.java
```

The second line (package 30, also `javac 25.0.5`) compiles against the stub `ITLCOverrides.java` beside the others, so no `tla2tools.jar` is needed.

| Class | Source | What |
| --- | --- | --- |
| `plain/Plain.class` | `java-src/plain/Plain.java` | A class that depends on nothing, for the fake's own tests. |
| `tlc2/overrides/ITLCOverrides.class` | `java-src/tlc2/overrides/ITLCOverrides.java` | A stub of TLC's interface: the "interface" case of the class-file reader. |
| `tlc2/overrides/DirectOverrides.class` | `java-src/tlc2/overrides/DirectOverrides.java` | Implements the interface directly. |
| `tlc2/overrides/NotAnOverride.class` | `java-src/tlc2/overrides/NotAnOverride.java` | Implements nothing; its source holds `"http://x"` before `// implements ITLCOverrides`. |
| `tlc2/overrides/AbstractOverrides.class` | `java-src/tlc2/overrides/AbstractOverrides.java` | Abstract, implements the interface. |
| `tlc2/overrides/InheritedOverrides.class` | `java-src/tlc2/overrides/InheritedOverrides.java` | Implements it through its superclass `AbstractOverrides`. |
| `tlc2/overrides/Constants.class` | `java-src/tlc2/overrides/Constants.java` | A `long` and a `double` constant, the two-slot entries of the constant pool. |
| `tlc2/overrides/Outer.class`, `Outer$Inner.class` | `java-src/tlc2/overrides/Outer.java` | A nested class that implements the interface. |

Recorded compiler errors for `fail_with` are in `tests/fakes/javac-errors/`: `syntax-error.txt` is what `javac 25.0.5` printed for a missing `;`.

A package that needs another class adds its source under `java-src/`, compiles it by the same command, and adds a row here.
