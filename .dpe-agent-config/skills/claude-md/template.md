@../AGENTS.md

That import is load-bearing: Claude Code reads `CLAUDE.md`, not `AGENTS.md`, so without it
nothing above reaches a session. Everything below is Claude Code only.

## Claude Code only

- [The non-obvious correct form — e.g. `AWS_PROFILE=<n> pulumi …`, because `pulumi` takes the
  profile from the environment and has no `--profile` flag.]
- Hooks in `.dpe-agent-config/hooks/agent/` are vendored from `dpe-agent-config`; propose changes there, then run `.dpe-agent-config/hooks/agent/test-hooks.sh`.
- Path-scoped conventions live in `.claude/rules/`; they load when matching files are read.

<!--
  Delete the whole `## Claude Code only` section if nothing qualifies. The import plus the
  bridge sentence is a complete file, and most repos ship exactly that.

  Comments are free in this file and only this file — Claude Code strips them from memory files
  before injection. AGENTS.md and REVIEW.md get no such treatment, and lint fails on `<!--` in
  those two.
-->
