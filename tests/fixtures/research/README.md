# Captured investigation data

Raw data captured while answering the roadmap's investigation questions (pipeline stage 2), on 2026-11-14 with Linux and OpenJDK 25.0.5. Each folder belongs to one question; its number matches the result file in `docs/research/`, which explains what the data shows. Start there, not here.

No test reads these files yet. They are kept as evidence and as a starting point: the testing design of milestone 2 decides which become golden files, which move, and which are deleted.

## Folders

| Folder | Question | What is in it |
| --- | --- | --- |
| `01-tlc-output/` | [1, real TLC output](../../../docs/research/01-tlc-output.md) | Small specs (`specs/`) and TLC's output for each, with and without `-tool`, on v1.7.4 and 1.8.0. The commands are in each version's `commands.txt`. |
| `02-json-traces/` | [2, JSON traces](../../../docs/research/02-json-traces.md) | Specs, their `-tool` output and the trace files `-dumpTrace json` wrote (1.8.0 only). |
| `03-jar-identity/` | [3, jar identity and upstream command](../../../docs/research/03-jar-identity-and-upstream-cli.md) | Jar manifests, startup banners, SHA-256 sums, release API responses, the CalVer tag list, the file list of upstream PR 1371 and a copy of upstream's build workflow. |
| `08-github-api/` | [8, GitHub API ordering](../../../docs/research/08-github-api-ordering.md) | Trimmed release and tag lists from the GitHub API, in API order. Its own `README.md` says what was kept. |
| `10-examples-manifest/` | [10, Examples manifest](../../../docs/research/10-examples-manifest.md) | The manifest schema from the TLA+ Examples repository and one example manifest. |
| `12-sany-pcal-repl/` | [12, SANY, PlusCal, REPL](../../../docs/research/12-sany-pcal-repl.md) | Inputs and outputs of the parser, the PlusCal translator and the REPL on both versions, and the files PlusCal left behind. Its own `README.txt` explains the layout. |
| `13-override-loading/` | [13, override loading](../../../docs/research/13-override-loading.md) | 35 Java override cases per version (sources, specs, TLC output) run directly and through `tlaup`, with the scripts that made and ran them. The largest folder. |
| `14-jar-manifest/` | [14, jar manifest](../../../docs/research/14-jar-manifest.md) | `MANIFEST.MF` of v1.7.4, v1.8.0 and rolling. |
| `15-exit-codes/` | [15, exit codes and signals](../../../docs/research/15-exit-codes-and-signals.md) | Specs that trigger each TLC exit code, the output of each run, the result tables per version, and the scripts for the exit-code and signal tests. |
| `17-metadir/` | [17, metadir](../../../docs/research/17-metadir.md) | Specs and scripts for the metadir experiments, the folder trees they left (`trees.txt`) and the v1.7.4 collision error. |
| `18-digest/` | [18, digest field](../../../docs/research/18-digest-field.md) | Trimmed release API responses and a table of every release's jar digest. |

Questions 4, 5, 6, 7, 9, 11 and 16 kept no data here; their evidence is quoted in their result files.

## Paths

Absolute paths of the machine that ran the questions were replaced, so the files show no user name or home folder:

- `<repo>` is the root of this repository.
- `<tmp>` is the scratch folder the investigation ran in; `<tmp>/qNN/` is question NN's work folder, where the jars and specs were copied.

Other `/tmp/...` paths, such as `/tmp/Naturals.tla` or `/tmp/tlc-123.../`, are left as TLC printed them: TLC unpacks its standard modules into the system temporary folder. Because of the placeholders, the helper scripts do not run as they are; they show what was run.

## Secret scanning and lint

`detect-secrets` scans this folder like the rest of the repository. On 2026-11-15 it reported 106 possible secrets here, all of them 40-character git commit hashes: the `X-Git-Revision` lines of jar manifests (`03-jar-identity/`, `14-jar-manifest/`) and the `commit_sha` fields of the tag list (`08-github-api/`). `.secrets.baseline` excludes exactly those two line shapes with two `exclude_lines` patterns. The manifest pattern also matches the `X-Git-Revision = "..."` form, because detect-secrets reads `Key: value` files a second time as a config file. A line that holds anything besides the hash is still scanned. If a new capture is flagged, check the value first, then add a pattern for that exact line shape rather than excluding a file or folder.

`ruff` excludes this folder (in `pyproject.toml`), because the helper scripts are not project code.

The folder was also checked by hand on 2026-11-15 for tokens, keys, passwords, email addresses, host names and home folder paths; none were found. The word "secrets" appears only in upstream's workflow file, as the names of upstream's GitHub secrets (for example `secrets.GITHUB_TOKEN`), never their values.

If GitHub secret scanning reports something here, look at the file it names. If it is a hash, a digest or a secret's name, close the alert as a false positive. If it is a real credential, revoke it first, then remove it from the file.
