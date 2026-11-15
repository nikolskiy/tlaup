# 13. What TLC prints when an operator override loads, fails to load, or does not match

## Question

What does TLC print when a Java operator-override class loads, when it fails to load, and when an override does not match its operator? Both mechanisms: the `@TLAPlusOperator` annotation registered through an `tlc2.overrides.ITLCOverrides` class (system property `tlc2.overrides.TLCOverrides`), and the older convention of a class named like the TLA+ module (`tlc2.module.<Module>`) on the classpath. Message codes and text in `-tool` mode, and the exit code, for v1.7.4 and the current 1.8.0 / rolling build. Serves Milestone 1, runner: "Report clearly when an override module fails to load."

## Source

- Ran TLC from both jars with `java` 25.0.5 (`/usr/bin/java`, `javac` present), 35 cases per version, the same `java` flags, `-DTLA-Library` and classpath order that `tlaup tlc --show-command` prints (see Evidence 1). Output, sources, exact commands and exit codes are in `tests/fixtures/research/13-override-loading/` (`make-cases.sh` writes the sources, `run-cases.sh` compiles and runs them; per version `cases/<case>/` holds the TLA+ and Java sources and `out/<case>.{txt,exit,cmd,javac.txt}` the captured result).
- Also ran the real `tlaup tlc` (formatted, `--raw` and `--show-command`) on five of the cases against both jars: `tlaup-v1.7.4/` and `tlaup-rolling/` in the same folder.
- Read TLC source: `SpecProcessor.java` at tag v1.7.4 (https://github.com/tlaplus/tlaplus/blob/v1.7.4/tlatools/org.lamport.tlatools/src/tlc2/tool/impl/SpecProcessor.java, lines 500-690) and at commit `bc1b506` of the rolling build (https://github.com/tlaplus/tlaplus/blob/bc1b506/tlatools/org.lamport.tlatools/src/tlc2/tool/impl/SpecProcessor.java, lines 2190-2330); message texts in `tlc2/output/MP.java` (rolling, lines 961-979); codes in `tlc2/output/EC.java` (2154, 2168, 2400, 2402, 2403; exit codes in `EC.ExitStatus`); `tlc2/tool/impl/TLAClass.java` (class loading).
- Jars: v1.7.4 `tla2tools.jar`, sha256 `936a2620...e050e88`, "TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)". Rolling (https://github.com/tlaplus/tlaplus/releases/tag/rolling) and v1.8.0 (a pre-release, https://github.com/tlaplus/tlaplus/releases/tag/v1.8.0) are the same file: sha256 `7e53aa63...fb84f`, 4510884 bytes, "TLC2 Version 2026.11.15.002146 (rev: bc1b506)". So "1.8.0" and "rolling" are one result, called 1.8.0 below. (`tlaup tools list` shows rolling as `bc1b506 2026-10-23`, but the asset on GitHub was updated 2026-11-15T00:32Z; the release date shown is the tag's, not the jar's.)

## Short answer

1. **In v1.7.4 the system property `tlc2.overrides.TLCOverrides` does not exist.** TLC hard-codes the index class name `tlc2.overrides.TLCOverrides` (`SpecProcessor.java:577`). A different index class name, or a list of classes, is ignored, silently. The property is honoured only in the 1.8.0 build (`SpecProcessor.java:2203-2204`: path-separator list, default `tlc2.overrides.TLCOverrides`, and a built-in `TLCBuiltInOverrides` is always prepended). So tlaup's `-Dtlc2.overrides.TLCOverrides=...` has no effect on v1.7.4.
2. **Every "class cannot be used" case is silent when the class is merely absent or not an `ITLCOverrides`.** Class not found, not on the classpath, listed in the property but missing, not implementing `ITLCOverrides`, or listing a class whose methods carry no annotation: TLC prints nothing, exits 0, and the TLA+ definition runs. The only sign is the absence of the "Loading ... override" line, and that line is printed only for `warn = true`.
3. **Class found but broken** (exception in static init, constructor, `get()`, `get()` returning null, private constructor): TLC aborts with message `1000` (severity 1, "TLC threw an unexpected exception ... The exception was a `<class>` : `<message>`"), exit code 255, before any state is computed. The message never names the override class. A static-init failure prints a full Java stack trace inside the message (the `Caused by:` line carries the cause).
4. **Annotation names a missing module or operator**, or **arity differs**: only if `warn = true` (the annotation's default is `true`, from `TLAPlusOperator.java` at v1.7.4; the repo's examples set `warn = false`) TLC prints a warning and falls back to the TLA+ definition, exit 0: `2402` "(no such module)", `2403` "(no such operator)", `2400` "Failed to match ... override" (arity). With `warn = false` they are silent. The older convention uses `2400` for both arity mismatch and a Java method with no TLA+ operator of that name, and it has no `warn` switch.
5. **Both defined**: the Java override wins (TLC replaces the definition body). No warning that the TLA+ body is shadowed. Two overrides for one operator: both load (two `2168` lines), last registered wins, no warning.
6. **Override throws at evaluation time**: exit 75 (`FAILURE_SPEC_EVAL`) with `2154` "Attempted to apply the operator overridden by the Java method `<method>`, but it produced the following error: `<message>`" nested inside a `1000`, followed by `2103` with the TLA+ position. Wrong parameter type, wrong return type and non-static method fail the same way, but only at the first call. A `null` return gives exit 255 and `2102` "current state is not a legal state ... x = null". A non-public method gives exit 255 with a garbled nested `2154` (a literal `%2%` appears).
7. v1.7.4 and 1.8.0 print identical text, codes and exit codes for every case except the three property cases of point 1; the 1.8.0 build also prints `Linting of module X` lines in `-tool` mode, and its stack traces differ in line numbers.

## Confidence

Verified: ran every case on both jars; each row below is a captured output file. The source reading matches the observed behaviour in every case. Not verified: other Java versions (only Java 25 was available), the `warn` default in 1.8.0 (read only at v1.7.4), non-`-tool` output, Windows path separators in the property.

## Evidence

### 1. How tlaup invokes java

`uv run tlaup tlc spec --show-command` (v1.7.4 pinned, project with `modules/` and `classes/`, copy in `tlaup-v1.7.4/ok_warn_true.cmd.txt`):

```
java -XX:+IgnoreUnrecognizedVMOptions -XX:+UseParallelGC -DTLA-Library=<proj>/modules -Dtlc2.overrides.TLCOverrides=tlc2.overrides.TLCOverrides -cp <proj>/classes:<proj>/modules:<jar> tlc2.TLC -metadir <cache>/run/tlc/spec_<hash> spec.tla
```

`src/tlaup/tlc/runner.py` adds `-Dtlc2.overrides.TLCOverrides=` only if a classpath directory has `META-INF/services/tlc2.overrides.ITLCOverrides` or `tlc2/overrides/TLCOverrides.class`; `-tool` is inserted before the spec name when not `--raw`. Correction from the stage 2 check (2026-11-14): the repo's `docs/examples/QueueModule` and `module-set-a/b` define `QueueOverrides` etc. with no class named `TLCOverrides` and no service file in the source folder, but `tlaup modules add` writes `META-INF/services/tlc2.overrides.ITLCOverrides` listing them (`cmd/modules/add.py:121-132`), so through the normal flow tlaup does pass `-Dtlc2.overrides.TLCOverrides=tlc2.overrides.QueueOverrides`. On 1.8.0 that loads; on v1.7.4 it is ignored and the override silently does not load. Checked by running `docs/examples/QueueModule` with `docs/examples/spec/queue.tla` through `tlaup modules add` and `tlaup tlc queue --raw` (private XDG folders): v1.7.4 failed with the spec's own guard, `Assert` "Error: QueueUtils Java override is not loaded!"; v1.8.0 printed `State log test: ...` four times and exited 0. My cases run as `java ... -cp classes:modules:jar tlc2.TLC -metadir <tmp> -config spec.cfg -tool spec.tla`, with the property set explicitly (exact command per case in `out/<case>.cmd`).

### 2. Test setup

`spec.tla` EXTENDS `Ovr`, where `Ovr.tla` has `Add2(a, b) == a + b + 1000`. `Init == x = Add2(1, 2)`, invariant prints `<<"Inv sees", x, Add2(10, 20)>>` via `PrintT`. If the override is used the output is `<<"Inv sees", 3, 30>>`, otherwise `1003, 1030`.

### 3. Result table (identical on v1.7.4 and 1.8.0 unless stated)

"Used" = prints `3, 30`; "not used" = `1003, 1030` (TLA+ body).

| Case | Messages in `-tool` output | Exit | Override |
|---|---|---|---|
| `ok_warn_true` (annotation, `warn = true`) | `2168:0` "Loading Add2 operator override from tlc2.overrides.TLCOverrides with signature: <Java Method: public static tlc2.value.impl.Value tlc2.overrides.TLCOverrides.Add2(tlc2.value.impl.IntValue,tlc2.value.impl.IntValue)>." | 0 | used |
| `ok_warn_false`, `ok_value_params` | nothing at all | 0 | used |
| `legacy_ok` (`tlc2.module.Ovr`, no property, no `ITLCOverrides`) | `2168:0` "Loading Add2 operator override from file:`<path>`/tlc2/module/Ovr.class with signature: ..." (always printed, no `warn` switch) | 0 | used |
| `prop_class_not_found` (property names `tlc2.overrides.NoSuchClass`, real `TLCOverrides` on classpath) | v1.7.4 and 1.8.0 differ: v1.7.4 prints the `2168` line and uses the override (property ignored). 1.8.0 prints nothing and does not use it (the property replaces the default, and a missing class is skipped). | 0 | 1.7.4 used, 1.8.0 not used |
| `prop_class_not_on_classpath` (property correct, classes left off the classpath) | nothing | 0 | not used |
| `prop_second_class_missing` (property `TLCOverrides:NoSuchClass`) | `2168` for the first class only; nothing about the missing one | 0 | used (first) |
| `prop_alt_index_class` (index class `MyOverrides`, selected only by the property) | v1.7.4: nothing, not used. 1.8.0: `2168` ... from tlc2.overrides.MyOverrides | 0 | 1.7.4 not used, 1.8.0 used |
| `prop_two_index_classes` | same split as above | 0 | 1.7.4 not used, 1.8.0 used |
| `not_itlcoverrides` (index class does not implement the interface) | nothing | 0 | not used |
| `get_lists_unannotated` (`get()` lists a class whose method has no annotation) | nothing | 0 | not used |
| `static_init_throws` | `1000:1` "TLC threw an unexpected exception. This was probably caused by an error in the spec or model. See the User Output or TLC Console for clues to what happened. The exception was a java.lang.ExceptionInInitializerError" followed by the stack trace (about 20 lines, `tlc2.tool.impl.SpecProcessor...`) and `Caused by: java.lang.RuntimeException: boom in static init at tlc2.overrides.TLCOverrides.<clinit>(TLCOverrides.java:6)`. Then `2186` "Finished in ...". | 255 | n/a, run aborted |
| `ctor_throws` | `1000:1` ... "The exception was a java.lang.IllegalStateException\n: boom in constructor" (no stack trace) | 255 | aborted |
| `ctor_private` | `1000:1` ... "The exception was a java.lang.RuntimeException\n: " followed by an inner, garbled `1000:0` block (the message of the exception is empty) | 255 | aborted |
| `get_throws` | `1000:1` ... "java.lang.RuntimeException\n: boom in get()" | 255 | aborted |
| `get_returns_null` | `1000:1` ... "java.lang.NullPointerException\n: Cannot read the array length because "<local14>" is null" (v1.7.4 `<local19>`) | 255 | aborted |
| `annot_module_missing`, `warn = true` | `2402:3` "Failed to match Add2 operator override from NoSuchModule with signature: public static tlc2.value.impl.Value tlc2.overrides.TLCOverrides.Add2(tlc2.value.impl.IntValue,tlc2.value.impl.IntValue) (no such module)." | 0 | not used |
| `annot_op_missing`, `warn = true` | `2403:3` "Failed to match NoSuchOp operator override from Ovr with signature: ... (no such operator)." | 0 | not used |
| `annot_module_missing_warn_false` | nothing | 0 | not used |
| `arity_java_fewer`, `arity_java_more` (`warn = true`) | `2400:3` "Failed to match Add2 operator override from tlc2.overrides.TLCOverrides with signature: <Java Method: public static ... Add2(tlc2.value.impl.IntValue)>." | 0 | not used |
| `arity_java_fewer_warn_false` | nothing | 0 | not used |
| `legacy_arity_mismatch` | `2400:3` "Failed to match Add2 operator override from file:`<path>`/tlc2/module/Ovr.class with signature: <Java Method: ...Add2(tlc2.value.impl.Value)>." | 0 | not used |
| `legacy_op_missing_in_tla` (Java has `NotInTla`, TLA+ has no such operator) | `2168` for Add2, `2400:3` "Failed to match NotInTla operator override from file:... " | 0 | Add2 used |
| `no_override` (baseline) | nothing | 0 | not used |
| `duplicate_override` (two annotated methods for `Add2`) | two `2168` lines, no warning | 0 | both load; the second (`Add2again`) wins: `<<"Inv sees", 10, 37>>`. Order depends on `getDeclaredMethods`, which the JVM does not guarantee. |
| `eval_throws_runtime` (`RuntimeException("boom in override body")`) | (`2168` if `warn = true`) then `1000:1` wrapping `2154:0` "Attempted to apply the operator overridden by the Java method\npublic static tlc2.value.impl.Value tlc2.overrides.TLCOverrides.Add2(tlc2.value.impl.IntValue,tlc2.value.impl.IntValue),\nbut it produced the following error:\nboom in override body", then `2103:1` "The error occurred when TLC was evaluating the nested expressions at the following positions: 0. Line 4, column 9 to line 4, column 22 in spec ..." | 75 | aborted at first call |
| `eval_throws_error` (`StackOverflowError`) | same shape as above, message "boom as Error" | 75 | aborted |
| `eval_throws_evalexception` (`new EvalException(EC.GENERAL, ...)`) | `1000:1` wrapping `1000:0` "boom as EvalException", then `2103:1`; no `2154`, no method name | 75 | aborted |
| `legacy_throws` | `2168`, then `1000:1`/`2154:0` ... "boom in legacy body", `2103:1` | 75 | aborted |
| `param_type_mismatch` (`StringValue` parameters, called with ints) | `2154:0` ... "Cannot cast tlc2.value.impl.IntValue to tlc2.value.impl.StringValue"; load message `2168` is still printed as if fine | 75 | aborted at first call |
| `return_type_not_value` (`int` return) | `2154:0` ... "cannot convert MethodHandle(IValue[])int to (Value[])Value"; `2168` printed | 75 | aborted at first call |
| `method_not_static` | `2168` printed (with `public Value ...Add2`, no `static`), then `2154:0` ... "cannot convert MethodHandle(TLCOverrides,IValue[])Value to (Value[])Value" | 75 | aborted at first call |
| `method_not_public` (package-private static) | no `2168`; at first call a garbled `2154:1` containing a nested `2154:0` ("member is private to package: tlc2.overrides.TLCOverrides.Add2[Ljava.lang.Object;@2781e022/invokeStatic, from public Lookup") and a literal `%2%` | 255 | aborted at first call |
| `eval_returns_null` | `2102:1` "current state is not a legal state\nWhile working on the initial state:\nx = null" | 255 | aborted |

### 4. Message codes (from `EC.java` and `MP.java` in the 1.8.0 build; same text seen in v1.7.4)

| Code | Severity in `-tool` header | Text |
|---|---|---|
| 2168 | 0 | `Loading %1% operator override from %2% with signature: %3%.` |
| 2400 | 3 (warning) | `Failed to match %1% operator override from %2% with signature: %3%.` (arity) |
| 2402 | 3 | same, plus ` (no such module).` |
| 2403 | 3 | same, plus ` (no such operator).` |
| 2154 | 0 nested in 1000:1 | `Attempted to apply the operator overridden by the Java method\n%1%,\nbut it produced the following error:\n%2%` |
| 1000 | 1 (error) | the generic "TLC threw an unexpected exception" |

Exit codes (`EC.ExitStatus`): 0 success, 75 `FAILURE_SPEC_EVAL`, 255 `ERROR`. Load failures that throw are 255, evaluation failures are 75, except null results and non-public methods (255).

### 5. Source facts that explain the table

- v1.7.4: `SpecProcessor.java:577` `this.tlaClass.loadClass("tlc2.overrides.TLCOverrides")`; if the result is an `ITLCOverrides`, `newInstance()`, `get()`, then for each class every declared method is checked for `@Evaluation`, `@TLAPlusCallable`, `@TLAPlusOperator`. The `warn` flag guards the `2400/2402/2403` warnings and the `2168` line (for `@TLAPlusOperator`); the other two annotations always print `2168`. `catch (InstantiationException | IllegalAccessException)` calls `Assert.fail(EC.GENERAL)`; a constructor or static-init exception is not caught there and surfaces as `1000`.
- `TLAClass.loadClass` swallows every `Exception` (including `ClassNotFoundException`) and returns null; that is why a missing class is silent.
- 1.8.0: same loop wrapped in `for (String ovrde : (TLCBuiltInOverrides + ":" + System.getProperty("tlc2.overrides.TLCOverrides", "tlc2.overrides.TLCOverrides")).split(File.pathSeparator))`; also adds a `priority` / `silent` option to `@Evaluation`.
- Legacy convention (`tlc2.module.<Module>` or a class named like the module, found by `TLAClass.loadClass(moduleName)`, which also looks for `<Module>.class` through the TLA+ library path): only `public static` methods are considered; an arity mismatch or a method without a TLA+ operator of that name gives `2400`; matched ones always print `2168`. The annotation mechanism and the legacy mechanism are separate code paths and both exist in both versions.

### 6. What tlaup shows today (`tlaup-v1.7.4/`, `tlaup-rolling/`)

- `tlaup tlc` on `ok_warn_true`: "Success: Model checking completed successfully." The `2168` line is not shown in the formatted output (it appears only with `--raw`).
- `annot_op_missing` (warn = true): formatted output shows "Warning: Found 1 warning(s). Failed to match NoSuchOp operator override ... (no such operator)." and exit 0.
- `static_init_throws`: "Error: Model checking failed with 1 error(s). TLC threw an unexpected exception ... The exception was a java.lang.ExceptionInInitializerError" plus the whole stack trace, one frame per paragraph; exit 255. Nothing says an override module failed.
- `eval_throws_runtime`: "Failed with 3 error(s)", the `2154` text, exit 75.
- `prop_alt_index_class`: tlaup passes no property (no `TLCOverrides.class`), TLC silently runs the TLA+ body on both jars.

## Implications for the roadmap

- "Report clearly when an override module fails to load" can only be done for part of the failures from TLC output: the broken-class cases (`1000`, exit 255, mentioning `ExceptionInInitializerError`, `IllegalStateException`, etc., never the class name) and the `2400/2402/2403` warnings (only with `warn = true`). The cases a user is most likely to hit, wrong class name, class not on the classpath, class not an `ITLCOverrides`, `warn = false` mismatches, produce no output, so the runner cannot detect them from TLC's output. A check before launch (does each class named in the property exist and implement `ITLCOverrides`; does the annotated module/operator exist) would have to be done by tlaup itself. `java/inspector.py` already exists and is the obvious place; this was not examined here.
- Fact for planning: on v1.7.4 the property is ignored. Anything that lets a user register an index class under another name (the examples use `QueueOverrides`, `ModuleAOverrides`, which tlaup passes through the service file that `modules add` writes) works only on the 1.8.0 / rolling build; on v1.7.4 every module added with `tlaup modules add` whose index class is not named `TLCOverrides` silently does not load (checked with `QueueModule`, Evidence 1); on v1.7.4 the class must be literally `tlc2.overrides.TLCOverrides` on the classpath.
- To confirm a load, the `2168` line is the only positive signal, and only for `warn = true` (or legacy / `@TLAPlusCallable` / `@Evaluation`). tlaup's formatted output drops it today.
- Detecting a failed load by text: match `1000` severity 1 appearing before `2189` ("Computing initial states..."), i.e. before any state work, and the exit code 255. Exit 75 means an override ran and threw.
- Examples in `docs/examples` use `warn = false`; with that setting a wrong module or operator name is invisible.

## Open follow-ups

- Confirm `warn()` still defaults to `true` in the 1.8.0 build (read at v1.7.4 only; the fixtures always set it explicitly).
- Done in the stage 2 check for `QueueModule` only (Evidence 1); `module-set-a/b` and `sequences-ext` were not run.
- Check other JDKs (11, 17, 21): the garbled messages for `ctor_private` and `method_not_public` and the NPE text come from the JVM and may differ.
- `@Evaluation` and `@TLAPlusCallable` annotations were not exercised.
- Behaviour with `-DTLA-Library` modules containing a compiled `<Module>.class` (the loader's `resolver.resolve` path) was not tested.

## Date checked

2026-11-14. Jars downloaded the same day from the GitHub releases `v1.7.4` and `rolling` (v1.8.0 asset identical to rolling). Java: OpenJDK 25.0.5, Debian.
