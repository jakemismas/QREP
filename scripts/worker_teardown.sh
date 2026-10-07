#!/usr/bin/env bash
# Remove a worker's worktree and its local branch once the work has merged.
#
# Why: each worktree carries its own venv, node_modules and vendored runtime,
# so leftovers cost gigabytes and invite stale-tree mistakes, but a teardown
# must never lose work. So it refuses, before removing anything:
#   - a branch that HEAD does not contain;
#   - uncommitted or untracked files;
#   - ignored files that no build recreates (anything regenerable() does not
#     list). `git worktree remove` deletes ignored files without asking, and
#     .gitignore covers the private corpus tiers and the overnight report;
#   - a held file. The worktree is first renamed aside, which fails cleanly
#     while any process (a preview server, a shell, an editor) holds a file in
#     it, where a direct removal would delete part of the tree and then stop.
# It deletes the branch with `git branch -d`, which refuses unmerged work too,
# and uses only git's own removal commands: the machine's hooks forbid raw
# deletes, and git knows which files belong to the worktree.
#
# Usage: scripts/worker_teardown.sh <ticket> [branch]
#   Run it from a checkout whose HEAD contains the merged branch (the main
#   checkout after `git pull`). The branch defaults to the one the worktree
#   has checked out; pass it to finish a teardown whose worktree is already
#   gone.
# Env: QREP_WT_ROOT, as for worker_bootstrap.sh.
set -euo pipefail

die() { echo "worker_teardown: $*" >&2; exit 1; }
step() { echo "==> $*"; }

[ $# -ge 1 ] && [ $# -le 2 ] || die "usage: worker_teardown.sh <ticket> [branch]"
ticket=$1
[[ $ticket =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] \
  || die "ticket must start with a letter or digit and use only letters, digits, '.', '_' and '-': $ticket"

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo=$(git -C "$script_dir" rev-parse --show-toplevel)
common_dir=$(git -C "$repo" rev-parse --path-format=absolute --git-common-dir)
main_root=$(dirname "$common_dir")
wt_root=${QREP_WT_ROOT:-"$(dirname "$main_root")/qrep-wt"}
if command -v cygpath >/dev/null 2>&1; then
  wt_root=$(cygpath -m "$wt_root")
  repo=$(cygpath -m "$repo")
fi
# git lists worktree paths without a trailing slash, and the lookups below
# compare exact strings.
while [ "${#wt_root}" -gt 1 ] && [ "${wt_root%/}" != "$wt_root" ]; do wt_root=${wt_root%/}; done
wt="$wt_root/$ticket"
parked="$wt_root/.teardown-$ticket"

worktree_branch() {
  git -C "$repo" worktree list --porcelain | awk -v want="$1" '
    index($0, "worktree ") == 1 { path = substr($0, 10); next }
    path == want && index($0, "branch ") == 1 { b = substr($0, 8); sub(/^refs\/heads\//, "", b); print b; exit }'
}

is_registered() {
  git -C "$repo" worktree list --porcelain | grep -qxF "worktree $1"
}

is_locked() {
  git -C "$repo" worktree list --porcelain | awk -v want="$1" '
    index($0, "worktree ") == 1 { path = substr($0, 10); next }
    path == want && ($0 == "locked" || index($0, "locked ") == 1) { found = 1 }
    END { exit !found }'
}

# Ignored outputs that the bootstrap, a build or a test run recreates.
regenerable() {
  case "$1" in
    .venv/ | .pytest_cache/ | .ruff_cache/ | .qrep-worker.env | build/ | dist/) return 0 ;;
    tests/fixtures/_generated/ | reference/out/) return 0 ;;
    web/node_modules/ | web/dist/ | web/.vendor-cache/ | web/test-results/ | web/playwright-report/) return 0 ;;
    web/public/pyodide/ | web/public/wheels/ | web/public/fixtures/) return 0 ;;
    __pycache__/ | */__pycache__/ | *.egg-info/ | *.py[cod]) return 0 ;;
  esac
  return 1
}

[ "$wt" != "$repo" ] || die "refusing to remove the checkout this script runs from ($repo)"
[ "$wt" != "$main_root" ] || die "refusing to remove the main checkout"
[ ! -e "$parked" ] || die "$parked is left over from an earlier teardown: look inside, then move it back with git worktree move if git still lists it, or to a scratch folder if not, and re-run; nothing was removed"

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
  ! is_locked "$wt" || die "$wt is locked; unlock it (git worktree unlock) only once no session uses it; nothing was removed"
  dirty=$(git -C "$wt" status --porcelain)
  [ -z "$dirty" ] || die "$wt has uncommitted or untracked files; commit and push them, or move them out, and re-run; nothing was removed:
$dirty"
  ignored_cmd=(git -C "$wt" ls-files -z --others --ignored --exclude-standard --directory --no-empty-directory)
  "${ignored_cmd[@]}" >/dev/null || die "could not list the ignored files in $wt; nothing was removed"
  keep=()
  while IFS= read -r -d '' entry; do
    regenerable "$entry" || keep+=("$entry")
  done < <("${ignored_cmd[@]}")
  if [ "${#keep[@]}" -gt 0 ]; then
    printf '  %s\n' "${keep[@]}" >&2
    die "$wt holds the ignored files above, which git worktree remove would delete without asking and no build recreates; move them out of the worktree and re-run; nothing was removed"
  fi

  step "moving worktree $wt aside to $parked"
  git -C "$repo" worktree move "$wt" "$parked" \
    || die "could not move $wt aside: a process (a preview server, a shell or an editor) probably holds files in it; stop that process and re-run; nothing was removed"
  step "removing worktree $parked"
  git -C "$repo" worktree remove "$parked" \
    || die "git worktree remove failed for $parked (git's reason is above)." \
      "If git worktree list still shows it, nothing was deleted: move it back with" \
      "git worktree move \"$parked\" \"$wt\". If not, it may be partly deleted: move what" \
      "is left to a scratch folder and finish with: worker_teardown.sh $ticket $branch." \
      "Stop and report"
fi

if git -C "$repo" show-ref --verify --quiet "refs/heads/$branch"; then
  step "deleting local branch $branch"
  git -C "$repo" branch -d "$branch" || die "git branch -d $branch failed; stop and report"
fi

! is_registered "$wt" || die "$wt is still registered as a worktree"
! is_registered "$parked" || die "$parked is still registered as a worktree"
[ ! -e "$wt" ] || die "$wt is still on disk; stop and report"
[ ! -e "$parked" ] || die "$parked is still on disk; a process may hold files in it; stop and report"
! git -C "$repo" show-ref --verify --quiet "refs/heads/$branch" || die "branch $branch still exists"
step "removed worktree $wt and branch $branch"
