# Module sources for the scenarios of `module add`

Folders that `a module source "<name>" from the fake sources` copies into the working folder. Their Java
sources are copies of those in `tests/fakes/java-src/`, because the fake `javac` does not compile: it copies the
prepared class of the same file name from `tests/fakes/classes/`. The two `.jar` files are not jars; nothing
reads them.

| Folder | What |
| --- | --- |
| `Queue/` | A `.tla` module, `DirectOverrides.java` under `modules/tlc2/overrides/`, `sub/Constants.java` under a top-level `tlc2/overrides/`, and `lib/a.jar` and `lib/b.jar`. |
| `TlaOnly/` | One `.tla` module and no Java. |
| `NoIndex/` | One `.tla` module and `NotAnOverride.java`, a class that implements nothing. |
