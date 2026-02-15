Feb 15, 2026
Nancy — GPT-5.2 Thinking

---

# Worktrunk + uv + Multi-Agent Worktrees

**User Guide**

This guide explains how to use your project’s preconfigured worktree system for safe parallel development with multiple coding agents or humans. It assumes the repository already contains the standardized Worktrunk + bootstrap setup.

---

# Quickstart

## Create a new task workspace

```bash
wt switch --create feat-login-timeout
```

What happens automatically:

* new branch created
* worktree directory created
* dependencies installed via `uv sync`
* local virtualenv created
* environment files prepared
* per-worktree port assigned
* tmux session spawned (if enabled)

---

## Enter your environment

If tmux opened:

```bash
tmux a
```

If not:

```bash
source .wt.activate
```

---

## Run your task

Examples:

Run tests:

```bash
pytest
```

Start dev server:

```bash
uv run app.py
```

Launch agent:

```bash
claude
```

or

```bash
codex
```

---

## Finish work

```bash
git add .
git commit -m "feat: implement login timeout"
git push
```

Open PR as usual.

---

## Clean up worktree after merge

```bash
wt remove feat-login-timeout
```

---

# Core Concepts

## 1) One task = one worktree

Each branch has its own:

* filesystem
* dependencies
* env vars
* ports
* agents

This prevents conflicts and lets multiple changes run simultaneously.

---

## 2) Worktrees are isolated environments

Each worktree contains:

| File           | Purpose              |
| -------------- | -------------------- |
| `.venv/`       | local virtualenv     |
| `.env.local`   | local secrets/config |
| `.wt.port`     | assigned dev port    |
| `.wt.activate` | activation command   |

Agents and developers should only interact inside their current worktree directory.

---

## 3) Deterministic setup

Every worktree is reproducible because bootstrap scripts:

* install dependencies
* create env files
* assign ports
* prepare runtime state

This guarantees consistent environments for both humans and agents.

---

# Daily Workflow Patterns

---

## Parallel feature work

Example:

```
wt switch --create feat-ui
wt switch --create refactor-auth
```

Now you can run:

* UI agent in one
* refactor agent in another
* tests in both

---

## Agent collaboration workflow

Recommended pattern:

| Worktree | Role      |
| -------- | --------- |
| feature  | implement |
| review   | validate  |
| tests    | verify    |

Agents work independently and changes merge later.

---

## Switching tasks

```bash
wt switch feat-ui
```

Instantly moves you into that workspace.

---

## Listing active worktrees

```bash
wt list
```

Shows branches + paths + activity state.

---

# Environment Usage

---

## Activate environment manually

```bash
source .wt.activate
```

Never activate global environments. Always use the worktree one.

---

## Get assigned port

```bash
cat .wt.port
```

Use this value when running local servers.

---

## Read machine-parsable environment info

```bash
cat .wt.agent-env
```

Agents use this file to detect runtime config.

---

# Best Practices

---

### Always run agents inside a worktree

Never launch tools from the main checkout when doing task work.

---

### Commit often

Small commits make merges and debugging easier.

---

### Never share `.venv` between worktrees

Each workspace has its own environment intentionally.

---

### Keep branches short-lived

Delete worktrees once merged to avoid clutter.

---

### Don’t edit `.env.local` in other worktrees

Each branch owns its environment.

---

# Troubleshooting

---

## Dependencies not installed

Run:

```bash
uv sync
```

---

## Virtualenv not active

Run:

```bash
source .wt.activate
```

---

## Wrong Python version

Delete and recreate env:

```bash
rm -rf .venv
uv venv
uv sync
```

---

## Port conflict

Regenerate:

```bash
rm .wt.port
./scripts/wt/bootstrap.sh
```

---

## Worktree stuck or broken

Recreate:

```bash
wt remove branch-name
wt switch --create branch-name
```

---

# Advanced Usage

---

## Run multiple agents simultaneously

Open tmux session and assign panes:

Pane 1 → Claude
Pane 2 → Codex
Pane 3 → tests

Each sees only its worktree filesystem.

---

## Scriptable automation

Because bootstrap is deterministic, you can safely automate:

* CI preflight
* test runners
* linters
* review agents

---

## Rebase main into task

```bash
git fetch
git rebase origin/main
```

Safe because each branch is isolated.

---

# Mental Model

Think of worktrees as:

> lightweight disposable dev machines sharing one Git repo

They are not branches.
They are independent checkouts of branches.

---

# Command Reference

| Action   | Command                   |
| -------- | ------------------------- |
| new task | `wt switch --create name` |
| switch   | `wt switch name`          |
| list     | `wt list`                 |
| remove   | `wt remove name`          |

---

# Summary

This system gives you:

* deterministic environments
* safe concurrency
* agent isolation
* reproducible setups
* zero manual bootstrapping

It turns parallel development from fragile → reliable.

---

**Note:** This guide assumes your repository already contains the standardized Worktrunk configuration, bootstrap scripts, and hooks described earlier.
