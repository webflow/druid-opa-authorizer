#!/usr/bin/env bash
# Commit message must be <JIRA-ID>: summary (e.g. DEN-108: fix thing) -- The ticket must
# also match the current branch's ticket, so a commit can't drift onto the wrong ticket.
msg=$(head -n1 "$1")
# Neither is authored by hand: a local merge commit, and dpe-agent-config's sync commit, which
# has no ticket to name.
case "$msg" in Merge\ *|chore\(agent-config\):\ *) exit 0;; esac

if ! printf '%s' "$msg" | grep -qE '^[A-Za-z]+-[0-9]+: .{1,72}$'; then
  echo "commit-msg: first line must be '<JIRA-ID>: <summary>' (e.g. DEN-108: fix thing)." >&2
  exit 1
fi

branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
case "$branch" in main|master|HEAD) exit 0;; esac

branch_ticket=$(printf '%s' "$branch" | grep -oE '^[A-Za-z]+-[0-9]+')
if [ -n "$branch_ticket" ]; then
  msg_ticket=$(printf '%s' "$msg" | grep -oE '^[A-Za-z]+-[0-9]+')
  if [ "$msg_ticket" != "$branch_ticket" ]; then
    echo "commit-msg: message is prefixed with '$msg_ticket' but the branch is '$branch_ticket' -- the commit ticket must match the branch's." >&2
    exit 1
  fi
fi
