#!/usr/bin/env bash
set -euo pipefail

# scripts/wt/tmux.sh
# Creates a tmux session named after the current directory, with panes for:
# - Claude Code
# - Codex CLI
# - tests / dev server
# Optionally opens Cursor if `cursor` is on PATH.

if ! command -v tmux >/dev/null 2>&1; then
  echo "[wt] tmux not installed; skipping"
  exit 0
fi

WT_DIR="$(pwd)"
SESSION="wt-$(basename "$WT_DIR" | tr -cs '[:alnum:]' '-')"

# Avoid clobbering an existing session
if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "[wt] tmux session exists: $SESSION"
  exit 0
fi

tmux new-session -d -s "$SESSION" -c "$WT_DIR" -n agents

# Split into 3 panes
tmux split-window -t "$SESSION":0 -h -c "$WT_DIR"
tmux split-window -t "$SESSION":0.0 -v -c "$WT_DIR"

# Pane 0: Claude Code (if installed)
tmux send-keys -t "$SESSION":0.0 'command -v claude >/dev/null && claude || echo "claude not found"' C-m

# Pane 1: Codex CLI (if installed)
tmux send-keys -t "$SESSION":0.1 'command -v codex >/dev/null && codex || echo "codex not found"' C-m

# Pane 2: tests/dev server placeholder (customize)
tmux send-keys -t "$SESSION":0.2 'echo "run tests or dev server here"; test -f .wt.port && echo "port: $(cat .wt.port)"' C-m

# Optional: open Cursor (CLI name can vary; only run if present)
if command -v cursor >/dev/null 2>&1; then
  cursor "$WT_DIR" >/dev/null 2>&1 || true
fi

echo "[wt] created tmux session: $SESSION (attach with: tmux a -t $SESSION)"
