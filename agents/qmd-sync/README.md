# QMD Sync "agent"

TBD: Make this into an agent via Claude Agent SDK

This agent is responsible for re-analyzing the `qmd` project and updating our design to reflect any changes or improvements.

**Initial install:**
```bash
# from repository root
git subtree add --prefix=agents/qmd-sync/src git@github.com:mikewaters/qmd.git main --squash
```

**Update to the latest:**
```bash
# from repository root
git subtree pull --prefix=agents/qmd-sync/src git@github.com:mikewaters/qmd.git main --squash
```
## Methodology
Prompt chain, where agent is given initial prompt (`qmd-analysis-prompt.md`); that agent's output is fed into the next agent, and so forth.
The final output is a list of features to fill any gaps identified between QMD and this tool.

```
qmd-analysis-prompt.md --> substrate-improvements-prompt.md --> substrate-feature-prompt.md --> features/
```
