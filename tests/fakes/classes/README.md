# Prepared classes for the fake `javac`

The fake `javac` (`tests/fakes/javac.py`) compiles nothing: for each source `X.java` it is given, it copies every `X.class` and `X$*.class` found here into its `-d` folder, keeping the path below this folder. The class files are real, compiled once from the sources in `tests/fakes/java-src/` and committed.

Compiled from the repository root with `javac 25.0.5`:

```
javac --release 11 -d tests/fakes/classes tests/fakes/java-src/plain/Plain.java
```

| Class | Source | What |
| --- | --- | --- |
| `plain/Plain.class` | `java-src/plain/Plain.java` | A class that depends on nothing, for the fake's own tests. |

A package that needs another class adds its source under `java-src/`, compiles it by the same command, and adds a row here.
