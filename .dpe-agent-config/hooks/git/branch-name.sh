#!/usr/bin/env bash
# Branch must be <JIRA-ID>-short-desc (e.g. DEN-108-fix-thing)
b=$(git rev-parse --abbrev-ref HEAD)
# `chore/agent-config-<tag>` comes from dpe-agent-config's sync workflow, which has no ticket to
# name; without this, pushing a fixup to a sync branch would need --no-verify.
case "$b" in main|master|HEAD|chore/agent-config-*) exit 0;; esac
printf '%s' "$b" | grep -qE '^[A-Za-z]+-[0-9]+-[a-z0-9._-]+$' || {
  echo "branch-name: '$b' must match <JIRA-ID>-short-desc (e.g. DEN-108-fix-thing)." >&2; exit 1; }
