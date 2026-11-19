# Using the TLA+ tools as an agent: a report from the formal check

Written 2026-11-18 by the agent that did the formal check of the design ([`specs/README.md`](../../specs/README.md)), at the maintainer's request, right after the work. It says how the TLA+ tools were used in that session, what cost time, and what would have helped; then it sets that against what the roadmap already plans. Its purpose is to check that the plan points the right way for agents, and to name what the plan does not have.

**What this is based on.** One session, one agent, about three hours. Three specs, 27 configs, several dozen TLC runs, the largest about 16.6 million distinct states. TLC only, started as `java -cp tla2tools.jar tlc2.TLC`, build 2026.05.26.235334 (rev 4ba7d88), OpenJDK 25.0.5, Linux, 12 cores.

**What it is not based on.** tlaup itself was never run (the first finding says why), so everything said about tlaup comes from its design documents, not from use. Not used either: SANY on its own, PlusCal, the REPL, simulation mode, `-coverage`, `-difftrace`, `-dumpTrace`, checkpoints and `-recover`. One build of TLC, one Java, one operating system.

## Why tlaup was not used

The task allowed either the released tlaup or plain `java`. Plain `java` won at once, for three reasons, each of which the plan already removes:

| Reason | Today (0.8.x) | Planned | Verdict |
| --- | --- | --- | --- |
| It works in the maintainer's real folders. | Two `XDG_` variables on every command, and they must not leak to `uv` or `git`. | One variable, `TLAUP_HOME` ([14 F2](../design/14-config-and-cli.md#f2-folder-overrides)). | Right, and necessary. An agent will not use a tool that can damage the user's setup by default. |
| No build was installed in the temporary folders, and installing is a download. | `tools install`, then run. | `--auto-install` and `TLAUP_AUTO_INSTALL`, never a prompt ([12 V9](../design/12-tools-and-downloads.md#v9-first-run-prompt)). | Right. See "A jar that is already on the disk" below for what is still missing. |
| TLC's own flags do not reach TLC. | Only the spec and `--cfg`. The check needed `-workers`, `-metadir`, `-noGenerateSpecTE` and a `-config` per variant. | Everything after `--` is passed on ([11 R8](../design/11-runner.md#r8-passthrough-and-workers)). | Right. Without it tlaup cannot do this kind of work at all. |

So the first wave is a precondition, not a refinement: with today's release an agent that knows TLC goes round tlaup.

## What cost time

In order of cost. Each has what happened, what would have helped, and whether it is planned.

### 1. Finding out how big a model is, by waiting

The first run-folder model did not finish. After ten minutes it had 20 million states and a queue that was still growing; it then filled the disk. Nothing says in advance how large a state space is, and nothing in TLC stops a breadth-first run after a set time with a clean answer. The model was cut down three times by trial: run, watch the queue, stop, think, change.

What would have helped: a budget. `tlaup tlc Spec --max-time 2m`, or a limit on states, that stops TLC and reports a third outcome beside "holds" and "violated": **incomplete**, with the states found, the depth reached and whether the queue was growing or shrinking. An agent can then try a model for two minutes, read one result, and decide.

Planned: no. It is not a TLC flag, so decision D24 (no first-class TLC options beyond `--workers`) does not speak against it; tlaup will own the child and its signals ([20 G3](../design/20-groundwork.md#g3-java-launcher)), which is all it needs. The JSON result needs the word for it; the open question on `unknown` as an outcome in [40](../design/40-later-milestones.md#milestone-4-automation-surface) is the place.

### 2. Reading the result of a run

Every result was read with `grep` for five phrases ("is violated", "No error has been found", "states generated", "Finished in", "Error:"). The check script in `specs/` does the same with `sed`. That is scraping, and it broke once: a full disk came out as "TLC threw an unexpected exception. This was probably caused by an error in the spec or model", which the patterns took for a failed run of unknown kind.

What would have helped: one JSON document per run with the outcome, the name and kind of the violated property, generated and distinct states, depth, states left on the queue, duration, and whether the search was complete.

Planned: yes, the JSON reporter of milestone 4, built on a result model that already has these fields ([10 P3](../design/10-parser.md#p3-result-model)). Right direction, and for an agent it is the most valuable single item on the roadmap. Three things to make sure of:

- **The violated property by name**, and whether it is an invariant, an action property or a temporal property. The Examples vocabulary ("safety failure") is not enough: the check had 17 configs that were *meant* to fail, each on one named property, and a run that fails on a different one is a different result.
- **States left on the queue** when a run stops early. It is the one number that says how far from done a run was.
- **The environment in the same document**: TLC build and commit, Java version, workers, the command, the cfg. All of that was copied into the README by hand so the numbers could be reproduced.

### 3. Reading a counterexample

A TLC trace prints every variable of every state. The run-folder spec has 15 variables, several of them functions of records; a 28-step trace is several hundred lines, nearly all of them unchanged from the step before. Reading one in full costs more context than the spec. A throwaway script printed, per step, the action's name and two chosen variables, and that was enough for every trace that was read.

What would have helped: per step, the action name and only the variables that changed, with the full first state; a way to name the variables to show; the loop marked in a liveness trace.

Planned: partly. The parser gives each state its action and location ([10 P5](../design/10-parser.md#p5-error-traces)), a value diff exists in the terminal reporter ([22 O3](../design/22-reporters.md#o3-terminal-reporter)), and `-difftrace` passes through. Not planned: a compact form as the default for a machine reader, and choosing variables. In the JSON, a list of changed variable names per step would let a reader skip the rest.

### 4. Many configs for one spec

The check needed 27 configs for three specs: the design as written, each answer to an open question, each option that waits on the maintainer, and each property that is expected to fail. TLC cannot take a constant from the command line, so every variant is a file; they were generated by a Python script and then kept. A shell script runs them all and compares each outcome with a comment on the first line of the config.

What would have helped: a list of runs with what each should give (holds, or this property fails), run by one command that prints one table and exits non-zero on a surprise. And a constant given on the command line, written into a temporary config.

Planned: not as such. "Run the examples straight from the tlaplus/Examples manifest" is listed after the roadmap, and it is the same feature: a manifest of spec, config and expected outcome. It would be worth designing with the project file of milestone 3, with the expected property by name. This is what turns a set of specs into a regression suite, for an agent and for CI alike.

### 5. State files, and a disk that filled

TLC writes its queue and fingerprints under `-metadir`, by default beside the spec. The runs were pointed at the session's scratch folder, which is a RAM disk of 7.6 GB on this machine; two long runs filled it. Each run then needed a folder made, passed and removed by hand, and a run stopped by `timeout` left its folder behind.

Planned: yes. One run folder per run under the cache, removed at the end ([11 R6](../design/11-runner.md#r6-run-folders)); `tlaup cache` to list them with sizes. Right direction. Two things the agent's way of working adds:

- **A stopped run should not always be kept.** (Taken up the same day: decision D48, `tlaup tlc --no-keep`, [R6](../design/11-runner.md#r6-run-folders).) R6 keeps the folder of an interrupted run that has a checkpoint, for 30 days. An agent that tries a model, stops it and tries a smaller one would leave a kept folder of gigabytes each time, if TLC writes checkpoints by itself (question 25). A stop by budget, or a `--no-keep`, should delete.
- **Say where the cache is and how much room it has** when a run dies of "No space left on device", and report that as what it is, not as a spec error.

### 6. A long silence in the liveness check

A liveness run of 1.3 million states printed "Checking temporal properties for the complete state space" and then nothing for 35 minutes, until it was stopped. There is no progress and no way to tell slow from stuck.

Planned: the parser has a `LIVENESS` phase, so a reporter can at least show the phase and the time in it. The budget of point 1 covers the rest. One more thing costs nothing: warn when a config has both `SYMMETRY` and a temporal property, since symmetry is not sound for liveness and TLC runs it anyway.

### 7. A parse error that took three tries

`[][phase \in S => stoppedBy' = stoppedBy]_vars` fails with `Encountered "]_"`, because `[phase \in S` is read as the start of a function. The message gives the place and nothing a reader can act on. Each try cost a full TLC start, because SANY ran as part of TLC.

Planned: `tlaup sany` as its own fast command with diagnostics in `path:line:col` form ([21 S1](../design/21-other-tools.md#s1-sany)). Right: an agent would run it after every edit, before any long run. Not planned, and cheap later: a short hint for the handful of SANY messages that are known to mislead.

### 8. Stopping a run

Runs were stopped with `timeout`, which signals the wrapper script, and with `kill` on a process id found with `ps`. A broad `pkill` was refused by the agent's own permission rules. Once it was unclear whether a JVM was still running.

Planned: signals forwarded to the JVM, the grace period, exit codes 130 and 143 ([20 G3](../design/20-groundwork.md#g3-java-launcher)). Exactly right; this is the failure the launcher design is about. A small addition: `run.json` already records the process id, so `tlaup cache list` could say which runs are alive.

### 9. Things one has to know

Each cost a failed or wasted run the first time.

| What | Plan |
| --- | --- |
| `-noGenerateSpecTE`, or every failed run writes two files beside the spec. | Default (D36). Right. |
| `-workers auto`. | Default (D24). It was accepted by the build used here, with Java 25; that is one data point for question 19, on a build that is neither of the two supported ones. |
| `-XX:+UseParallelGC`. | In the default Java options ([13 J1](../design/13-modules-and-java.md#j1-java-options)). Right. |
| `CHECK_DEADLOCK FALSE`, or a model whose processes can all finish "deadlocks". | Not planned, and it should stay TLC's default. A hint on a deadlock whose last state has no enabled action by design would be guessing; a line in the documentation for agents is enough. |
| Counts of a run that stops at a violation differ from run to run with several workers. | Not planned. Worth one sentence beside the numbers in the JSON, so nobody compares them. |

### 10. A jar that is already on the disk

The jar came from a search of the home folder, and its build was read with `unzip` from the manifest and `sha256sum`.

Planned: identity from the manifest and `tool list` ([12 V1](../design/12-tools-and-downloads.md#v1-version-store)). Importing a jar from a local path is listed after the roadmap. For an agent in a sandbox with no network that import is the only way in; it may deserve to move up.

## What worked well

- **Breadth-first search gives the shortest counterexample.** Every finding of the check was a trace of 5 to 28 steps that could be read as a story.
- **Action names in the trace.** They are what made the throwaway script possible.
- **The message names the violated property.**
- **Speed.** 16.6 million states in about eight minutes on eight workers. The limit was never TLC's speed, always the size of the model.
- **`-config` takes any path**, so variants could live in a folder of their own.
- **Exit codes 12 and 13** tell an invariant from a property. They were not used, only because the text had to be read anyway.

## Is the plan pointed the right way?

Yes. The plan removes all three reasons tlaup was not used. Of the ten points above it covers four in full (results as data, run folders, signals, defaults) and three in part (traces, the liveness phase, parse errors). Nothing planned looked wrong from this side, and nothing planned would have been in the way.

What an agent needs differs from what a person at a terminal needs in four ways, and the plan has each:

| An agent | Plan |
| --- | --- |
| Never sees a live display; reads one result at the end. | The layout is drawn only on a terminal; JSON on stdout (D30, D40). |
| Cannot answer a prompt. | No prompt without a terminal; a flag and a variable for the one question (D4, D45). |
| Must not touch the user's own setup. | `TLAUP_HOME` (D25). |
| Branches on the outcome. | Exit codes with a fixed meaning (D29). |

One thing to weigh again. The JSON reporter sits in milestone 4, after the terminal reporter and the live layout of milestone 1b. For an agent the order of value is the other way round: the result as data first, the display last. The result model is built in the first wave either way, and the JSON reporter is described as a third small reporter on top of it. If it is cheap, as the sketch suggests, doing it with the first wave would make 0.9.0 usable by agents from its first day.

## Proposals that are not on the roadmap

In the order an agent would want them.

1. **A budget, and "incomplete" as an outcome** (point 1). Time or states; stop TLC cleanly; report how far it got.
2. **A manifest of runs with expected outcomes, and one command to check it** (point 4). The expected property by name. Design it with the project file.
3. **A compact trace for machine readers** (point 3). Action, changed variables, the loop.
4. **In the JSON result: the violated property and its kind, states left on the queue, and the environment** (point 2).
5. **A keep rule for stopped runs** (point 5), so trial runs do not fill the cache for 30 days.
6. **The liveness phase shown with its elapsed time, and a warning for symmetry with a temporal property** (point 6).
7. **A full disk reported as a full disk** (point 5).
8. **A page for agents**: the flags, the exit codes, the JSON schema, and four recipes (try a model within a budget, check a set of configs, read a counterexample, clean up). Short enough to load whole.
9. **A constant from the command line** (point 4).
10. **Import a jar from a path** (point 10): already listed after the roadmap; an agent without network needs it first.

## What was not looked at

- Whether any of the ten proposals is cheap. They are needs, not designs.
- How another agent, or the same one on another task, would use the tools. PlusCal, the REPL and simulation never came up.
- tlaup in use. When 0.9.0 exists, this report should be done again with it.
