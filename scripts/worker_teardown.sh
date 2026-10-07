#!/usr/bin/env bash
# Remove a worker's worktree and its local branch once the work has merged.
#
# Why: each worktree carries its own venv, node_modules and vendored runtime,
# so leftovers cost gigabytes and invite stale-tree mistakes, but a teardown
# must never lose work. So this refuses a branch that HEAD does not contain,
# lets `git worktree remove` refuse a dirty tree (never --force), and deletes
# the branch with `git branch -d`, which refuses unmerged work too. It uses
# only git's own removal commands: the machine's hooks forbid raw deletes,
# and git knows which files belong to the worktree.
#
# Usage: scripts/worker_teardown.sh <ticket> [branch]
#   Run it from a checkout whose HEAD contains the merged branch (the main
#   checkout after `git pull`). The branch defaults to the one the worktree
#   has checked out; pass it to finish a teardown whose worktree is already
#   gone. Uncommitted work or an unmerged branch stops it before anything is
#   removed. Files held open by a running process (or a shell whose current
#   folder is inside the worktree) can stop git midway: stop and report.
# Env: QREP_WT_ROOT, as for worker_bootstrap.sh.
set -euo pipefail

die() { echo "worker_teardown: $*" >&2; exit 1; }
step() { echo "==> $*"; }

[ $# -ge 1 ] && [ $# -le 2 ] || die "usage: worker_teardown.sh <ticket> [branch]"
ticket=$1
[[ $ticket =~ ^[A-Za-z0-9._-]+$ ]] || die "ticket may use only letters, digits, '.', '_' and '-': $ticket"

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo=$(git -C "$script_dir" rev-parse --show-toplevel)
common_dir=$(git -C "$repo" rev-parse --path-format=absolute --git-common-dir)
main_root=$(dirname "$common_dir")
wt_root=${QREP_WT_ROOT:-"$(dirname "$main_root")/qrep-wt"}
if command -v cygpath >/dev/null 2>&1; then
  wt_root=$(cygpath -m "$wt_root")
  repo=$(cygpath -m "$repo")
fi
wt="$wt_root/$ticket"

worktree_branch() {
  git -C "$repo" worktree list --porcelain | awk -v want="$1" '
    index($0, "worktree ") == 1 { path = substr($0, 10); next }
    path == want && index($0, "branch ") == 1 { b = substr($0, 8); sub(/^refs\/heads\//, "", b); print b; exit }'
}

is_registered() {
  git -C "$repo" worktree list --porcelain | grep -qxF "worktree $1"
}

[ "$wt" != "$repo" ] || die "refusing to remove the checkout this script runs from ($repo)"
[ "$wt" != "$main_root" ] || die "refusing to remove the main checkout"

registered=false
if is_registered "$wt"; then
  registered=true
  checked_out=$(worktree_branch "$wt")
  [ -n "$checked_out" ] || die "$wt has a detached HEAD; check out its branch first"
  branch=${2:-$checked_out}
  [ "$branch" = "$checked_out" ] || die "$wt has '$checked_out' checked out, not '$branch'"
elif [ -e "$wt" ]; then
  die "$wt exists but is not a registered worktree (an earlier removal may have hit locked files); stop and report"
else
  branch=${2:-}
  [ -n "$branch" ] || die "no worktree at $wt; pass the branch name to delete only the branch"
fi

head_name=$(git -C "$repo" rev-parse --abbrev-ref HEAD)
if git -C "$repo" show-ref --verify --quiet "refs/heads/$branch"; then
  git -C "$repo" merge-base --is-ancestor "refs/heads/$branch" HEAD \
    || die "$branch is not merged into $head_name in $repo; merge its PR and pull first"
fi

if $registered; then
  step "removing worktree $wt"
  git -C "$repo" worktree remove "$wt" \
    || die "git worktree remove failed (git's reason is above); nothing was forced; stop and report"
fi

if git -C "$repo" show-ref --verify --quiet "refs/heads/$branch"; then
  step "deleting local branch $branch"
  git -C "$repo" branch -d "$branch" || die "git branch -d $branch failed; stop and report"
fi

is_registered "$wt" && die "$wt is still registered as a worktree"
[ ! -e "$wt" ] || die "$wt is still on disk; a process may hold files in it open; stop and report"
! git -C "$repo" show-ref --verify --quiet "refs/heads/$branch" || die "branch $branch still exists"
step "removed worktree $wt and branch $branch"
