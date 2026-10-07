#!/usr/bin/env bash
# Build (or repair) the isolated worktree one QREP sprint worker runs in.
#
# Why: parallel workers must never measure each other's code. The main venv's
# editable install resolves qrep to the main checkout, a fresh worktree has no
# node_modules, vendored Pyodide or qrep wheel, and every local Playwright run
# would otherwise share port 4173 and reuse whatever server already listens
# there. So each ticket gets its own worktree outside the repo, its own venv
# installed editable from that worktree and pinned by constraints.txt (with an
# assertion that qrep really imports from there), its own web toolchain and
# source-stamped wheel, and its own Playwright port.
#
# Usage: scripts/worker_bootstrap.sh <ticket> <branch> [base-ref]
#   ticket    worktree folder name, for example 105 (letters, digits, . _ -)
#   branch    branch to check out; created from base-ref if it exists on
#             neither side, resumed from origin/<branch> if only pushed
#   base-ref  start point for a new branch (default origin/main, fetched first)
# Re-running on an existing worktree repairs it instead of failing. Any failed
# step stops the script with a message. No git operation is ever forced; the
# only things rebuilt from scratch are node_modules (npm ci), the qrep wheel,
# and a venv whose interpreter no longer runs.
# Env: QREP_WT_ROOT (default: the main checkout's parent folder + /qrep-wt),
#      QREP_BASE_PYTHON (default: python) creates the venv.
set -euo pipefail

die() { echo "worker_bootstrap: $*" >&2; exit 1; }
step() { echo "==> $*"; }

[ $# -ge 2 ] && [ $# -le 3 ] || die "usage: worker_bootstrap.sh <ticket> <branch> [base-ref]"
ticket=$1
branch=$2
base=${3:-origin/main}
[[ $ticket =~ ^[A-Za-z0-9._-]+$ ]] || die "ticket may use only letters, digits, '.', '_' and '-': $ticket"
git check-ref-format --branch "$branch" >/dev/null 2>&1 || die "invalid branch name: $branch"

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
common_dir=$(git -C "$script_dir" rev-parse --path-format=absolute --git-common-dir)
main_root=$(dirname "$common_dir")
wt_root=${QREP_WT_ROOT:-"$(dirname "$main_root")/qrep-wt"}
if command -v cygpath >/dev/null 2>&1; then
  wt_root=$(cygpath -m "$wt_root")
fi
wt="$wt_root/$ticket"
env_file="$wt/.qrep-worker.env"

worktree_branch() {
  git -C "$main_root" worktree list --porcelain | awk -v want="$1" '
    index($0, "worktree ") == 1 { path = substr($0, 10); next }
    path == want && index($0, "branch ") == 1 { b = substr($0, 8); sub(/^refs\/heads\//, "", b); print b; exit }
    path == want && $0 == "detached" { print "(detached HEAD)"; exit }'
}

is_registered() {
  git -C "$main_root" worktree list --porcelain | grep -qxF "worktree $1"
}

# 1. Worktree
if [[ $base == origin/* ]]; then
  step "fetching origin so $base is current"
  git -C "$main_root" fetch --quiet origin || die "git fetch origin failed; refusing to branch from a stale $base"
fi
git -C "$main_root" worktree prune
if is_registered "$wt"; then
  current=$(worktree_branch "$wt")
  [ "$current" = "$branch" ] || die "$wt is already a worktree on '$current', not '$branch'"
  step "reusing worktree $wt on $branch"
elif [ -e "$wt" ] && [ -n "$(ls -A "$wt" 2>/dev/null)" ]; then
  die "$wt exists but is not a registered worktree; move it aside and re-run"
else
  mkdir -p "$wt_root"
  if git -C "$main_root" show-ref --verify --quiet "refs/heads/$branch"; then
    step "adding worktree $wt for existing branch $branch"
    git -C "$main_root" worktree add "$wt" "$branch" \
      || die "git worktree add failed (is $branch checked out in another worktree?)"
  elif git -C "$main_root" show-ref --verify --quiet "refs/remotes/origin/$branch"; then
    # Resuming pushed work whose local branch is gone: start from the pushed
    # tip, never from base, or the new worktree would silently drop it.
    step "adding worktree $wt for $branch from origin/$branch"
    git -C "$main_root" worktree add --track -b "$branch" "$wt" "origin/$branch"
  else
    git -C "$main_root" rev-parse --verify --quiet "$base^{commit}" >/dev/null \
      || die "base ref not found: $base"
    step "adding worktree $wt on new branch $branch from $base"
    # --no-track: with origin/main as upstream, a bare `git pull` or
    # `git push` would target main. Workers push with `git push -u origin`.
    git -C "$main_root" worktree add --no-track -b "$branch" "$wt" "$base"
  fi
fi
[ -f "$wt/constraints.txt" ] || die "$wt/constraints.txt is missing: the branch predates the pinned toolchain; merge origin/main into it first"

# 2. Venv, installed editable from the worktree
venv_python() {
  if [ -x "$wt/.venv/Scripts/python.exe" ]; then echo "$wt/.venv/Scripts/python.exe"
  elif [ -x "$wt/.venv/bin/python" ]; then echo "$wt/.venv/bin/python"
  fi
}
py=$(venv_python)
if [ -z "$py" ]; then
  step "creating venv $wt/.venv"
  "${QREP_BASE_PYTHON:-python}" -m venv "$wt/.venv"
elif ! "$py" -c "import sys" >/dev/null 2>&1; then
  step "venv interpreter is broken; recreating $wt/.venv"
  "${QREP_BASE_PYTHON:-python}" -m venv --clear "$wt/.venv"
fi
py=$(venv_python)
[ -n "$py" ] || die "no venv interpreter under $wt/.venv"
step "installing qrep[dev] editable from the worktree, pinned by constraints.txt"
"$py" -m pip install --disable-pip-version-check --quiet -e "${wt}[dev]" -c "$wt/constraints.txt"

step "asserting qrep imports from the worktree"
# -I keeps the current directory off sys.path, so only the editable install
# can satisfy the import.
(cd "$wt_root" && "$py" -I -c '
import importlib.metadata
import os
import sys
import tomllib

root = os.path.normcase(os.path.realpath(sys.argv[1]))
import qrep

found = os.path.normcase(os.path.realpath(qrep.__file__))
try:
    inside = os.path.commonpath([root, found]) == root
except ValueError:
    inside = False
if not inside:
    sys.exit(f"FAIL: qrep imports from {qrep.__file__}, outside the worktree {sys.argv[1]}")
with open(os.path.join(sys.argv[1], "pyproject.toml"), "rb") as f:
    wanted = tomllib.load(f)["project"]["version"]
installed = importlib.metadata.version("qrep")
if installed != wanted:
    sys.exit(f"FAIL: installed qrep metadata is {installed}, pyproject says {wanted}")
print(f"qrep {installed} imports from {qrep.__file__}")
' "$wt") || die "qrep import assertion failed; this worktree would test the wrong code"

# 3. Web toolchain: npm ci, vendored runtime, fresh stamped wheel
step "npm ci"
(cd "$wt/web" && npm ci --no-audit --no-fund) \
  || die "npm ci failed (on Windows, a running preview server or editor can lock node_modules)"

main_cache="$main_root/web/.vendor-cache"
if [ "$wt" != "$main_root" ] && [ -d "$main_cache" ]; then
  # vendor.mjs re-verifies every cached file's sha256 and refetches a
  # mismatch, so seeding from the main checkout cannot poison the build.
  mkdir -p "$wt/web/.vendor-cache"
  for cached in "$main_cache"/*.whl; do
    [ -f "$cached" ] || continue
    [ -e "$wt/web/.vendor-cache/$(basename "$cached")" ] || cp "$cached" "$wt/web/.vendor-cache/"
  done
fi
step "vendoring the pinned Pyodide runtime and wheels"
(cd "$wt/web" && QREP_PYTHON="$py" node scripts/vendor.mjs)
step "building the qrep wheel from the worktree"
(cd "$wt/web" && QREP_PYTHON="$py" node scripts/wheel.mjs)
step "checking wheel freshness against the qrep sources"
(cd "$wt/web" && node scripts/wheel-hash.mjs)

# 4. Playwright port: stable per ticket, never shared with a sibling worktree
port_base=4200
port_span=800
port=""
if [ -f "$env_file" ]; then
  port=$(sed -n 's/^QREP_E2E_PORT="\{0,1\}\([0-9][0-9]*\)"\{0,1\}$/\1/p' "$env_file" | head -n 1)
fi
claimed_ports() {
  local f
  for f in "$wt_root"/*/.qrep-worker.env; do
    [ -f "$f" ] && [ "$f" != "$env_file" ] || continue
    sed -n 's/^QREP_E2E_PORT="\{0,1\}\([0-9][0-9]*\)"\{0,1\}$/\1/p' "$f"
  done
}
claimed=$(claimed_ports)
if [ -z "$port" ] || grep -qx "$port" <<<"$claimed"; then
  if [[ $ticket =~ ^[0-9]+$ ]]; then
    seed=$((10#$ticket))
  else
    seed=$(printf '%s' "$ticket" | cksum | cut -d ' ' -f 1)
  fi
  port=$((port_base + seed % port_span))
  tries=0
  while grep -qx "$port" <<<"$claimed"; do
    port=$((port_base + (port - port_base + 1) % port_span))
    tries=$((tries + 1))
    [ "$tries" -lt "$port_span" ] || die "no free Playwright port in $port_base-$((port_base + port_span - 1))"
  done
fi
cat > "$env_file" <<EOF
# Written by scripts/worker_bootstrap.sh; web/playwright.config.ts reads
# QREP_E2E_PORT from here. Load it into a shell with: set -a; . ./.qrep-worker.env; set +a
QREP_TICKET="$ticket"
QREP_WORKTREE="$wt"
QREP_PYTHON="$py"
QREP_E2E_PORT="$port"
EOF

step "ready"
echo "  worktree   $wt"
echo "  branch     $branch"
echo "  python     $py"
echo "  e2e port   $port (in $env_file)"
echo "  head       $(git -C "$wt" rev-parse --short HEAD)"
