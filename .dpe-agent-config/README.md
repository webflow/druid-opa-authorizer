# .dpe-agent-config/

Synced from [`dpe-agent-config`](https://github.com/webflow/dpe-agent-config) — see `VERSION`
for which release.

**Do not edit anything under this directory by hand.** `verification.sh drift` checks it against
`CHECKSUM` and fails CI on any local change. To change something here, open a PR on
`dpe-agent-config` instead; it reaches every consumer on the next tagged release.

## What's yours

Everything this directory checks but never writes:

`.claude/settings.json`, `.codex/hooks.json`, root `lefthook.yml`, `.claude/CLAUDE.md`,
`AGENTS.md`, `REVIEW.md`, the skill stubs under `.claude/skills/` and `.agents/skills/`, and
everything under `.agents/` (`config.env`, `rules/`).

Your root `.gitignore` is the one file `init` appends to: `.agents/.log/` has to be ignored by
something the clone carries, because the hook registrations are committed and the denial log
records each refused command verbatim. `lint` checks for the same reason, and accepts either
that entry or `.log/` in `.agents/.gitignore`, which an earlier `init` wrote.

`verification.sh lint` checks the contract on those — that a hook you're supposed to run is
actually registered, that every vendored skill has a stub, that `lefthook.yml` extends this
directory's — but never edits them itself. A sync PR never touches them either.

## Commands

### `verification.sh`

Run from anywhere in the repo; it resolves the repo root itself.

| Command          | What it does                                                                                      |
| ---------------- | ------------------------------------------------------------------------------------------------- |
| `lint`           | The contract check. Prints one `FAIL:` line per finding and exits non-zero. This is what CI runs. |
| `drift`          | Checks this directory against `CHECKSUM`. Fails if anything here was edited locally.              |
| `checksum [dir]` | Prints the hash `drift` compares against. Defaults to this directory.                             |
| `init`           | One-time bootstrap for a repo that has none of the files above. Never overwrites.                 |
| `stubs`          | Rewrites the skill stubs from the vendored skills. The one command here that overwrites.          |
| `probe`          | Prints the manual obedience-probe procedure — run it yourself in an agent session.                |

What `lint` checks:

- **The context files exist.** `AGENTS.md`, `REVIEW.md` and `.claude/CLAUDE.md` are present, and
  no root `CLAUDE.md` is.
- **`.claude/CLAUDE.md` bridges to `AGENTS.md`.** Its first line is a bare `@../AGENTS.md` —
  without it, nothing in `AGENTS.md` reaches a Claude Code session.
- **`AGENTS.md` and `REVIEW.md` use their canonical sections, in order**, and carry no HTML
  comments — only Claude Code strips those; every other reader pays for them.
- **Nested files come in pairs.** Every nested `AGENTS.md` has a `CLAUDE.md` beside it containing
  only `@AGENTS.md`, and vice versa. Neither alone reaches both tools.
- **Root `lefthook.yml` extends this directory's**, so the vendored git hooks are live.
- **Every `MANDATORY` hook is registered** on its declared event in both `.claude/settings.json`
  and `.codex/hooks.json`, every registered name resolves, and every launcher path is valid.
- **Every vendored skill has a stub** in `.claude/skills/` and `.agents/skills/` that still
  matches the skill it points at — the description is the trigger, so a stale stub is a skill
  that silently stops firing.
- **Every local rule has a test.** `.agents/rules/<name>.py` needs
  `.agents/rules/tests/test_<name>.py`, the same convention the catalog runs under.

A release that adds a `MANDATORY` hook, or renames a skill or reworks its `description:`, turns
`lint` red until you make the edit it names. That is the intended signal — the sync PR reports
it in the body but cannot fix it, because these are your files.

### `hooks/agent/run`

The hook launcher. Both registration files call `run <name>`; the rest are for you.

| Command                                   | What it does                                                                                                                                                                                                               |
| ----------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `run <name>`                              | Runs one hook against a tool event on stdin. Registered, not typed by hand.                                                                                                                                                |
| `run list`                                | Every hook available to register — central and local, with event and mandatory flag.                                                                                                                                       |
| `run mandatory`                           | `name event` per mandatory hook: what must appear in both registration files.                                                                                                                                              |
| `run resolve <name>`                      | Exit 0 if the name resolves centrally or in `.agents/rules/`, 1 if not.                                                                                                                                                    |
| `run stats`                               | Denial counts from `.agents/.log/denials.jsonl`, and below them the fail-open allows — commands a hook let through because its rule could not be reached. A steady count there is a broken hook, not a well-behaved agent. |
| `run check-registration <claude> <codex>` | The registration half of `lint`. `lint` calls it for you.                                                                                                                                                                  |

`hooks/agent/test-hooks.sh` runs the vendored test suite against the vendored hooks, then this
repo's own `.agents/rules/tests/`. It needs `pytest` and exits 1 with an install hint if it's
missing.

## Setting up a repo

Run `.dpe-agent-config/verification.sh init` once in a repo that doesn't have the files above.
It writes the mechanical ones — the two hook registrations, root `lefthook.yml`, the
`@../AGENTS.md` bridge, the skill stubs, `CODEOWNERS`, `.reviewflow.yml` — and never
overwrites.

It deliberately does **not** write `AGENTS.md` or `REVIEW.md`: their content is the work, and a
placeholder would pass the shape check while saying nothing. `init` ends by printing lint's
findings and a line to paste into Claude Code or Codex, which reaches the `agents-md` and
`review-md` skills.

Then run `lefthook install` once per clone, so the vendored `commit-msg` and `branch-name` hooks
are live locally.

**Keep formatters out of this directory.** It is checksummed, and `drift` compares it byte for
byte — so a repo-wide `prettier`/`eslint` glob fails on it, and running the same tool with
`--write` rewrites the bytes `drift` checks. Red either way, with no formatting that satisfies
both. `init` appends `.dpe-agent-config/` to `.prettierignore`, `.eslintignore` and
`.stylelintignore` when the repo already uses them; add the equivalent for any other tool that
writes across the whole tree.

`.reviewflow.yml` is a starting point, not finished config: add this repo's own generated and
vendored paths to `ignoredFilePatterns` — never a path `REVIEW.md` has a rule about, since
ignoring one drops it from the changed-file list — and drop `maxDiffChars` if the default is
enough.

The config alone runs nothing. Reviewflow needs a workflow that invokes it, and that file is
yours to write: it carries the triggers, permissions and model this repo wants, and an
`ANTHROPIC_API_KEY` secret on the repo. `dpe-agent-config`'s own
`.github/workflows/reviewflow.yml` is a working copy to start from.

## Wiring the check into CI

The git hooks are bypassable with `--no-verify`, and a sync PR never fails on its own — your CI
is what blocks a merge until the contract holds. Make `lint` and `drift` a required check.

An example workflow to copy into `.github/workflows/` and adapt — nothing like it is vendored,
because your CI is yours:

```yaml
name: agent-config
on: [push, pull_request]
jobs:
  contract:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: bash .dpe-agent-config/verification.sh lint
      - run: bash .dpe-agent-config/verification.sh drift
```

Both are pure bash plus the stdlib Python the launcher already needs — no setup step. Add
`.dpe-agent-config/hooks/agent/test-hooks.sh` as a third step if you keep local rules in
`.agents/rules/`: it runs the vendored suite and then your own `.agents/rules/tests/`, which is
the only thing that executes the test file `lint` requires beside each rule. That one needs
`pytest` installed first.

`drift` is a no-op in the `dpe-agent-config` source repo and only means something here, in a
vendored copy.

## After a release

A sync PR replaces this directory wholesale and stamps a new `VERSION` and `CHECKSUM`.

1. Read the PR body's lint report — it names any edit your files need.
2. Run `.dpe-agent-config/verification.sh stubs` if lint says a stub no longer matches its skill.
3. **Codex users:** if a hook's _registration_ changed, not just its logic, run `/hooks` in your
   next session and re-trust it, or Codex skips it silently.
