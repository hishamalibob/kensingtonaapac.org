#!/usr/bin/env bash
# Publish guard for kensingtonaapac.org.
#
# Looks at the newest files on a branch. If they would break the site, it waits
# a few minutes (an upload may still be in progress) and looks again. If the
# files are still broken, it puts the last working version back with a new
# commit and opens an issue that explains what happened.
#
# Nothing is ever deleted: the undone change stays in the history.
# It never touches anything inside .github.
# A commit message that contains [skip-check] is left alone.
#
# Usage: guard.sh BRANCH        (run inside a clone of this repository)
# Needs: GH_TOKEN and GITHUB_REPOSITORY for the issue and the rebuild request.
# Settings: GUARD_WAIT   seconds to wait before the second look (default 180)
#           GUARD_ISSUES 0 to skip the issue and the rebuild (used by the drill)
#           GUARD_DEPTH  how many earlier versions to consider (default 10)

set -uo pipefail

branch="${1:?Usage: guard.sh BRANCH}"
wait_s="${GUARD_WAIT:-180}"
make_issue="${GUARD_ISSUES:-1}"
depth="${GUARD_DEPTH:-10}"
slug="${GITHUB_REPOSITORY:-}"
owner="${slug%%/*}"
work="$(mktemp -d)"
checker="$work/check.py"
bot_name="github-actions[bot]"
bot_email="41898282+github-actions[bot]@users.noreply.github.com"

say() {
  echo "$*"
  if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then echo "$*" >> "$GITHUB_STEP_SUMMARY"; fi
}

note() { # note KEY VALUE: pass a result to later workflow steps
  if [ -n "${GITHUB_OUTPUT:-}" ]; then echo "$1=$2" >> "$GITHUB_OUTPUT"; fi
}

newest() {
  git fetch -q origin "+refs/heads/$branch:refs/remotes/origin/$branch" || return 1
  git checkout -q --detach "origin/$branch" || return 1
  if [ -f .github/scripts/check.py ]; then cp .github/scripts/check.py "$checker"; fi
  [ -f "$checker" ]
}

# validate REV [EARLIER_REV]: prints the problems; status 0 fine, 10 problems, anything else could not check
validate() {
  local rev="$1" base="${2:-}" dir args=()
  dir="$work/tree-$(git rev-parse --short "$rev")" || return 2
  rm -rf "$dir" && mkdir -p "$dir" || return 2
  git archive "$rev" | tar -x -C "$dir" || return 2
  if [ -n "$base" ] && git rev-parse -q --verify "$base^{commit}" > /dev/null 2>&1; then
    rm -rf "$work/base" && mkdir -p "$work/base"
    if git archive "$base" | tar -x -C "$work/base"; then args=(--baseline "$work/base"); fi
  fi
  python3 "$checker" files "$dir" ${args[@]+"${args[@]}"}
}

skipped() { git log -1 --format=%B | grep -qiF '[skip-check]'; }

newest || { say "Could not read the files on $branch, so nothing was changed."; exit 2; }

head="$(git rev-parse HEAD)"
if skipped; then say "The newest change (${head:0:7}) asks to skip the check, so it was left alone."; exit 0; fi
problems="$(validate HEAD HEAD~1)"; rc=$?
if [ "$rc" -eq 0 ]; then say "The published files look right (${head:0:7})."; note restored false; exit 0; fi
if [ "$rc" -ne 10 ]; then say "The checker could not run, so nothing was changed."; exit 2; fi

say "The files in ${head:0:7} have problems:"
say "$problems"
say "Waiting $wait_s seconds in case more files are still being uploaded."
sleep "$wait_s"

newest || { say "Could not read the files on $branch, so nothing was changed."; exit 2; }
head="$(git rev-parse HEAD)"
if skipped; then say "The newest change (${head:0:7}) asks to skip the check, so it was left alone."; exit 0; fi
problems="$(validate HEAD HEAD~1)"; rc=$?
if [ "$rc" -eq 0 ]; then say "A later upload completed the change. The files look right now (${head:0:7})."; note restored false; exit 0; fi
if [ "$rc" -ne 10 ]; then say "The checker could not run, so nothing was changed."; exit 2; fi

subject="$(git log -1 --format=%s)"
when="$(TZ=America/Los_Angeles date -d "@$(git log -1 --format=%ct)" '+%b %-d at %-I:%M %p') Pacific"

good=""
for rev in $(git rev-list --first-parent -n "$depth" HEAD~1 2> /dev/null); do
  if validate "$rev" > /dev/null 2>&1; then good="$rev"; break; fi
done

open_issue() { # open_issue TITLE BODY
  [ "$make_issue" = "1" ] || return 0
  gh label create publish-guard --color B60205 --description "Opened when a published change breaks the site" --force > /dev/null 2>&1 || true
  gh issue create --title "$1" --label publish-guard --body "$2" || say "Could not open the issue."
}

link="https://github.com/$slug/commit/$head"

if [ -z "$good" ]; then
  say "No working version was found in the last $depth changes, so nothing was put back. This needs a person."
  open_issue "kensingtonaapac.org is broken and could not be repaired automatically" "@$owner the change \"$subject\" (published $when) broke the site, and none of the last $depth versions passed the check, so nothing was put back.

What is wrong now:

$problems

The change: $link

The README has a section called \"If something goes wrong\"."
  exit 1
fi

git restore --source="$good" --staged --worktree -- . ':(exclude).github' || { say "Could not put the files back."; exit 1; }
if git diff --cached --quiet; then
  say "The site files already match the last working version, so there was nothing to put back."
  exit 1
fi

GIT_AUTHOR_NAME="$bot_name" GIT_AUTHOR_EMAIL="$bot_email" GIT_COMMITTER_NAME="$bot_name" GIT_COMMITTER_EMAIL="$bot_email" git commit -q \
  -m "Restore the last working version" \
  -m "The change \"$subject\" (${head:0:7}) would have broken the site, so the site files from ${good:0:7} were put back. Nothing was deleted: the change is still in the history." \
  || { say "Could not save the repair."; exit 1; }

if ! git push -q origin "HEAD:refs/heads/$branch"; then
  say "Newer files were published while the repair was under way. They will be checked by their own run."
  exit 0
fi

fixed="$(git rev-parse HEAD)"
say "Put back the last working version (${good:0:7}) as ${fixed:0:7}."
note restored true

if [ "$make_issue" = "1" ] && [ -n "$slug" ]; then
  gh api -X POST "repos/$slug/pages/builds" > /dev/null 2>&1 || say "Could not ask for a rebuild. GitHub usually rebuilds on its own."
fi

open_issue "A change to kensingtonaapac.org was undone automatically" "@$owner the change \"$subject\" (published $when) would have broken the site, so the last working version was put back automatically. The site is fine and you do not need to do anything right away.

What was wrong with the change:

$problems

Your change is not lost. It is saved here: $link

To publish it again, fix what is listed above and upload the files again. If the change was right and the check is wrong, publish it again with [skip-check] in the commit message."

exit 0
