# Documentation

Start here, then open only what the task needs. Each folder has its own index that says, per document, when to read it.

| Where | What it holds | Read it when |
| --- | --- | --- |
| [roadmap.md](roadmap.md) | The single source of truth: purpose, how the work is done (the agent pipeline, its stages, review gates and where each stage stands), decisions, milestones, the investigation list. Ticked items are done; dated notes record partial progress. | You plan or change anything, need a decision's reason, or need to know which stage the work is in and what it may do. Read its "How the work is done" section first; the rest by the milestone or decision you touch. |
| [contributing/](contributing/README.md) | Development setup, commands, the code map of today's code, conventions, releasing. | You run, test, commit or release. |
| [design/](design/README.md) | Design documents (pipeline stage 3), one per area, for the code as it will be. Their packages, commands and test layout do not exist until the work packages are built. | You design, cut work packages, build a package or review one. The index says which documents everyone reads and which are per area. |
| [research/](research/README.md) | Investigation results (pipeline stage 2), one file per question. | A design section or roadmap item cites a question, or you need the evidence behind a fact. |
| [analysis/](analysis/00-summary.md) | The six analysis reports of release 0.8.1 and their summary. Line numbers may have drifted; check the source before relying on one. | You need the original finding behind a roadmap item. Later stages read the roadmap and the design instead. `07-walkthrough-notes.md` is history: every decision in it is restated in the roadmap, and where the two differ the roadmap is right. |
| [examples/](examples/) | Example specs, some with custom Java modules. | You need a spec to run, or work on the examples. |
