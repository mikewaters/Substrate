#!/usr/bin/env bash
set -euo pipefail

echo "[wt] bootstrap: $(pwd)"

# --------------------------------------------------
# 1) Ensure uv exists
# --------------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
  echo "[wt] ERROR: uv not installed"
  echo "Install: https://github.com/astral-sh/uv"
  exit 1
fi

# --------------------------------------------------
# 2) Create per-worktree virtualenv
# --------------------------------------------------
# We intentionally DO NOT share .venv across worktrees.
# This prevents dependency or interpreter conflicts.

if [[ ! -d .venv ]]; then
  echo "[wt] creating virtualenv"
  uv venv
fi

# --------------------------------------------------
# 3) Install dependencies
# --------------------------------------------------
echo "[wt] syncing deps"
uv sync
# hack
uv add agentlayer

# hack
uv add agentlayer
make install

# --------------------------------------------------
# 4) Activate environment for current shell
# --------------------------------------------------
# Activation affects only this script process, but we
# provide a helper file so humans or agents can source it.

ACTIVATE_FILE=".wt.activate"

cat > "$ACTIVATE_FILE" <<'EOF'
# source this file to activate worktree venv
source .venv/bin/activate
EOF

echo "[wt] wrote $ACTIVATE_FILE"

# --------------------------------------------------
# 5) Stable per-worktree port
# --------------------------------------------------
python3 - <<'PY'
import hashlib, os
p = os.getcwd().encode()
port = 4000 + int(hashlib.sha256(p).hexdigest()[:8],16)%2000
open(".wt.port","w").write(str(port))
print("[wt] port =",port)
PY

# --------------------------------------------------
# 6) Agent hint file
# --------------------------------------------------
cat > .wt.agent-env <<EOF
WORKTREE=$(pwd)
VENV=.venv
PORT=$(cat .wt.port)
ACTIVATE=source .venv/bin/activate
EOF

echo "[wt] bootstrap complete"
