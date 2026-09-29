---
name: claude-md
description: Set up or fix a repo's .claude/CLAUDE.md — the Claude Code memory file whose @../AGENTS.md import is what makes the repo's context reach a Claude Code session at all. Use when wiring Claude Code into a repo, when `verification.sh lint` reports a CLAUDE.md finding, or when repo context is not loading in a session.
---

# Writing `.claude/CLAUDE.md`

Claude Code reads `CLAUDE.md`, not `AGENTS.md`. This file is the bridge, and in most repos it is
four lines long: an import, a sentence, and nothing else.

**The one rule that matters: this file is never a second copy of `AGENTS.md`.** Two files
describing the same repo drift, and drift is the conflicting-rules failure mode that makes
context files harmful rather than merely wasteful.

## Location is fixed

`./.claude/CLAUDE.md`. Never `./CLAUDE.md`. Both are valid to Claude Code; the nested one is the
standard for two reasons:

1. The repo root then carries exactly one agent file, `AGENTS.md`, which is the whole point.
2. The review tool's default document list includes `./CLAUDE.md` but not `./.claude/CLAUDE.md`,
   so the reviewer loads `AGENTS.md` once instead of once directly and once through the import.

Whether Claude Code loads both locations when both exist is undocumented. We do not find out per
repo: `verification.sh lint` **fails** if `./CLAUDE.md` exists.

## The import, and why it is not a link or a symlink

A `CLAUDE.md` that merely _links to_ `AGENTS.md` loads nothing. The import is the only mechanism.

Write it **bare, on its own line, first**:

```markdown
@../AGENTS.md
```

Paths resolve relative to **the file containing the import**, not the working directory and not
the repo root. Copy-pasting `@AGENTS.md` into `./.claude/CLAUDE.md` resolves to a non-existent
`.claude/AGENTS.md` and loads nothing, silently.

| `CLAUDE.md` location       | `AGENTS.md` location       | Import line     |
| -------------------------- | -------------------------- | --------------- |
| `./.claude/CLAUDE.md`      | `./AGENTS.md`              | `@../AGENTS.md` |
| `./packages/foo/CLAUDE.md` | `./packages/foo/AGENTS.md` | `@AGENTS.md`    |

Backticks and code fences suppress an import silently. Imports nest to a maximum depth of four
hops. `verification.sh lint` checks that line 1 is exactly the right import and that it resolves
to a file that exists.

**Never a symlink**, even though the documentation offers it as an alternative. A symlink is not
broken — the reviewer follows it — but it costs the thing you care about:

- It makes the reviewer load the same content **twice**. `AGENTS.md` and `CLAUDE.md` are both in
  the reviewer's default document list and it dedupes by path, never by content. Both are charged
  against the shared byte budget (default 30,720), and the loader skips _whole files_ when that
  budget runs out — so the duplicate can silently push `REVIEW.md` out of the review entirely.
- It cannot carry Claude-only content. The moment you need one line about a hook, you are
  converting to an import anyway.
- On Windows it needs Administrator or Developer Mode, and a checkout may materialise it as a
  text file containing the target path.

The import goes first, with **no heading above it**. `AGENTS.md` already opens with the repo name
as its H1; a title here produces two H1s in the merged context.

## What belongs below the import

Most repos need nothing beyond the import and a one-line bridge sentence. Add a line only when
**both** hold:

- discovering the rule by being hook-denied (or by a misconfigured integration) would waste a
  round trip, **and**
- the correct form is not obvious once you know the rule exists.

Expect one to three lines. Typical survivors:

- The credential invocation shape the hook accepts. `AGENTS.md` says which profile and that it
  is read-only; this says the exact form that gets through. State it accurately: `aws-readonly`
  accepts an allowed profile named **either** as `--profile <name>` **or** as `AWS_PROFILE=<name>`
  in the environment — `pulumi` has no `--profile` flag, so it is the environment form there.
- "Hooks are vendored — propose changes in `dpe-agent-config`, then run
  `.dpe-agent-config/hooks/agent/test-hooks.sh`."
- A one-line note that `.claude/rules/` exists, when it does.

**"Deploys are blocked" does not qualify.** The agent should not be deploying, and if it tries,
the hook's own stderr explains itself. `.claude/settings.json` is readable and a blocked call
returns the hook's message, so a well-written denial message is already documentation. If you are
writing a table here, improve the hook messages instead.

The admission test for every line: _would this line be meaningless to an agent that is not Claude
Code?_ If no, it belongs in `AGENTS.md` — move it.

## Deliberately not in this file

- **A skills table.** Claude Code discovers `.claude/skills/` itself and puts each skill's name
  and description in context at startup. Listing them again duplicates what is already loaded.
  Write the trigger into the skill's own description instead.
- **A hook inventory.** See above — the denial message is the documentation.
- **Slash commands and subagents.** Auto-discovered.
- Anything about the repo itself → `AGENTS.md`. Review rules → `REVIEW.md`. Setup and deploy
  steps → `README.md`.
- A rule you added because an agent annoyed you once → an enforcement layer, or a skill. This is
  not a complaints box; every entry taxes every future session.

## Comments are free here, and only here

Claude Code strips block-level HTML comments from memory files before injection, so instructional
comments in this file cost nothing at runtime and may stay for the next maintainer. `AGENTS.md`
and `REVIEW.md` get no such treatment — lint fails on `<!--` in those two.

## Nested directories and path-scoped rules

A nested `CLAUDE.md` is one line — `@AGENTS.md` — beside a nested `AGENTS.md`. Create the pair,
never one alone: Claude Code traverses `CLAUDE.md` only, and Codex reads `AGENTS.md` only (and
only when started in that directory). Nested files do **not** survive `/compact` until Claude
reads a file there again.

A path-scoped rule reloads on the next matching read, so prefer one when the audience is Claude
only:

```markdown
---
paths:
  - 'src/api/**/*.ts'
---
```

A rule file **without** `paths:` loads at startup with the same cost as this file. Do not use the
directory as a place to hide always-on content.

## Verify

`/context` in a session lists memory files loaded at startup — confirm this file appears under
"Memory files". That proves the startup load only. Nested files and `.claude/rules/` load later
and do not show there; for those, register the `log-instructions` hook (`InstructionsLoaded`) and
check its log after reading a file in the target directory.

Loading is not obedience. `verification.sh probe` is the check for whether a loaded rule is
actually followed.

## Before you call it done

- [ ] The file is at `./.claude/CLAUDE.md` and `./CLAUDE.md` does not exist
- [ ] Line 1 is exactly `@../AGENTS.md`, bare, with no heading above it
- [ ] The import resolves to a file that exists
- [ ] Nothing below the import would be meaningful to a non-Claude-Code agent
- [ ] No skills table, no hook inventory, no second copy of `AGENTS.md`
- [ ] `/context` shows the file under "Memory files"

## Template

`template.md`, beside this file. `verification.sh init` already writes the import and the bridge
sentence, so in most repos there is nothing left to do — the template's `## Claude Code only`
section is there to be deleted unless a line genuinely passes both halves of the test above.

A nested `CLAUDE.md` is not this template. It is one line, `@AGENTS.md`, and nothing else.

<!-- BEGIN principles -->
<!-- Generated from _shared/principles.md by tools/gen_skills.py. Do not edit between the markers. -->

## The three constraints

1. **The instruction budget.** There is no known fixed instruction limit, but reliability falls
   as the number, complexity and interaction of active constraints rise. Always-loaded context
   costs tokens and creates interference even when most of its rules are inactive.
2. **Load timing.** A startup file is hardwired into the session before the task is known. It
   cannot adapt. Every line is paid for on every request — the DAG session, the Pulumi session,
   the typo fix.
3. **The audience is every agent, not one.** These repos are worked on by Claude Code, Codex,
   and whatever comes next. A mechanism only one tool honours is a per-tool convenience, not a
   repo rule. Anything that must hold has to hold in a layer every agent passes through.

All three point one way: **the default for any candidate line is to exclude it, and the default
for any rule is to enforce it below the agent layer.** Inclusion is argued for.

## The two admission tests

A line may live in a startup-loaded file (`AGENTS.md`, `.claude/CLAUDE.md`) only if it passes
**both**:

| Test                          | Question                                               | Fails when                                                                        |
| ----------------------------- | ------------------------------------------------------ | --------------------------------------------------------------------------------- |
| **Not derivable from source** | Could the agent reach this by reading the source tree? | It restates `package.json`, the `Makefile`, the directory layout, or the imports. |
| **Globally relevant**         | Is this needed on ~every task in this repo?            | It applies to one subsystem, one language, one workflow, or one kind of change.   |

Derivable and global → delete. Not derivable but local → route it. Not derivable and global →
it belongs in the file. That set is small: expect 10–40 lines.

**"Not derivable from source" is not "unknowable."** The test is scoped to the source tree, not
to knowledge in general. Three different things sit under it:

| Kind                     | Example                                                                     | Who authors it                                                     |
| ------------------------ | --------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| Scattered but present    | Account IDs and the env→account mapping both sit in `Pulumi.*.yaml`         | An agent — the point is not paying for the lookup on every task    |
| Surface reading misleads | `protect: true` reads as prod-only and applies everywhere                   | An agent, with care — a normal read reaches the _wrong_ conclusion |
| Intent and history       | "dev reads prod buckets by design — do not fix it"; "this broke prod twice" | Not in the tree at any depth                                       |

Only the third needs a person, and usually as confirmation rather than authorship. It still
lives somewhere reachable: git log, incident notes, `TODO`/`WARNING`/`HACK` comments, PR
threads, and the file you are replacing.

Two consequences: this work is **mostly subtractive** — deleting what the tree already answers
and routing "always/never" rules into enforcement is most of the value. And **where you cannot
author, interrogate**: you cannot invent a trap, but you can report that `## Traps` is empty and
ask what has cost someone a debugging session here.

## The routing table

Every candidate fact routes to exactly **one** destination. A rule may additionally get an agent
hook as an early signal. Pick the first row that fits — rows are ordered by who they reach.

| Destination                                                                                                      | Loaded / applied                                                     | Reaches                                             | Takes                                                                                                                                                            |
| ---------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- | --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| IAM / branch protection / CODEOWNERS                                                                             | Always, by the platform                                              | Everyone, every tool                                | Access rules — read-only credentials, no direct push to `main`, human approval before deploy                                                                     |
| git hook (lefthook) + CI check                                                                                   | At commit / push / PR                                                | Every agent and every human                         | Artefact rules — commit format, branch naming, lint, generated files in sync                                                                                     |
| Agent `PreToolUse` hook — a catalog module registered by name in `.claude/settings.json` and `.codex/hooks.json` | At tool-call time                                                    | Claude Code and Codex; not humans, not other agents | The same rule as a row above, **in addition**, when early denial saves a round trip. Alone only for tool-choice rules that never reach a commit (`npm` → `pnpm`) |
| `AGENTS.md`                                                                                                      | Every session, at startup                                            | Every agent                                         | Not derivable from source **and** needed on ~every task **and** tool-agnostic                                                                                    |
| `.claude/CLAUDE.md`                                                                                              | Every Claude Code session, at startup                                | Claude Code                                         | The same, but Claude-Code-specific only. Opens with a bare `@../AGENTS.md` — never a second copy, never a symlink                                                |
| Skill (`.claude/skills/<n>/SKILL.md`, `.agents/skills/<n>/SKILL.md`)                                             | When its trigger matches                                             | Claude Code, Codex                                  | Steering needed by a _fraction_ of sessions — a workflow, a runbook, a subsystem's procedure                                                                     |
| Path-scoped rule (`.claude/rules/<n>.md` with `paths:`)                                                          | When Claude reads a matching file                                    | Claude Code only                                    | A convention for one language or directory. Prefer it over a nested file when the audience is Claude only                                                        |
| Nested `AGENTS.md` **+** nested `CLAUDE.md` containing only `@AGENTS.md`                                         | Claude Code: on reading a file there. Codex: only when started there | Both, asymmetrically                                | A package-scoped convention every agent needs. Neither file alone is enough                                                                                      |
| `REVIEW.md`                                                                                                      | Only during review                                                   | The reviewer                                        | Detectable, repo-specific failure conditions                                                                                                                     |
| `README.md`                                                                                                      | Never, by an agent                                                   | Humans                                              | Setup, deploy steps, operational runbooks                                                                                                                        |
| **Nowhere — delete**                                                                                             | —                                                                    | —                                                   | Discoverable from source, duplicated from config, or stale-prone                                                                                                 |

### Routing heuristics

- An imperative about a CLI or an artefact (`use pnpm`, `read-only aws profile`) → **git hook /
  CI / IAM first**, agent hook second. Markdown lowers the probability of a violation;
  enforcement below the agent makes it impossible for every agent, not one.
- A rule whose only enforcement is an agent hook is a **gap** — for humans, for agents without
  hook support, and for Codex users who have not re-trusted it. Add a layer above it, or record
  the gap in `## Enforced automatically`. Do not delete the prose until a cross-agent layer
  exists.
- An exact file path _as an assertion_ ("auth lives in `src/auth/handlers.ts`") → **delete**. The
  tree already answers it, and it misleads the moment the file moves. A path as a _pointer_ under
  Further reading is not the same thing — that is the disclosure mechanism.
- A command list → **delete**. It duplicates `package.json` / `Makefile`. Exception: the one
  canonical test or lint invocation when it is not the language default.
- Architecture, module layout, or data flow → **delete**. The file system is the documentation.
- A rule you added because an agent annoyed you once → **hook or skill**. Context files are not
  a complaints box.

## One hop, not three

A root file plus a **flat** set of referenced documents. Never a tree of references-to-references.

_Is Progressive Disclosure All You Need for Long-Context Agents?_
([arXiv:2607.17598](https://arxiv.org/abs/2607.17598), He et al., July 2026) compares raw
navigation, flat disclosure and hierarchical disclosure across three agent harnesses. Flat
disclosure pays off at scale — over a 20-document library, English open QA went from 0.257 to
0.462, about 1.7×. Hierarchical depth "never helps on a single book and sometimes hurts": one
model's multiple-choice accuracy collapsed from 0.9126 to 0.6398 under recursive packing. Strong
navigators gained nothing from extra depth.

Two limits on carrying that paper: it measures document _question-answering_, so it is about
whether an agent can **find** content, not whether it **complies** — and compliance has the
harder ceiling. And its gains appear at library scale; a single repo with one subsystem is the
"single book" case, where structure bought nothing. Do not split a small repo's context at all.

## Reading a file is not the same as being instructed by it

By default, content an agent reads as a file does not enter its automatic instruction chain.
Only the sanctioned memory channel — a memory filename the tool loads, or an `@import` into one
— makes text bind without being asked. Codex demonstrates the gap plainly: told to read a nested
`AGENTS.md` outright, it **described the rule correctly and then ignored it**.

So _"the agent will read `docs/CONVENTIONS.md` and follow it"_ is not a mechanism. If a rule must
bind, `@import` it into the memory file or enforce it below the agent. Links under **Further
reading** are reference material the agent consults when relevant — that is their correct use.
Do not move a must-follow rule behind a link and consider the job done.

## Anti-patterns — reject on sight

| Pattern                                               | Why it fails                                              |
| ----------------------------------------------------- | --------------------------------------------------------- |
| Raw generator output, shipped unedited                | Optimises for comprehensiveness; the opposite of the goal |
| A "Commands" / "Scripts" table                        | Duplicates `package.json` / `Makefile`                    |
| An "Architecture" / "Project structure" section       | Discoverable; stale on every refactor                     |
| A path as an assertion about where code lives         | The tree answers it, and it misleads once the file moves  |
| Two rules that conflict                               | Accumulates silently as files grow                        |
| Vague instructions ("write clean code", "add tests")  | Spends budget, changes nothing                            |
| "Always …" rules scoped to one domain                 | Global cost, local benefit                                |
| A must-hold rule enforced only by an agent hook       | Silently absent for humans and for Codex until re-trusted |
| A reference chain more than one hop deep              | Recursive disclosure measured worse than flat             |
| Duplication of a user-scope or shared-standard rule   | Duplication is how conflicting rules start                |
| HTML comments in a shipped `AGENTS.md` or `REVIEW.md` | Only Claude Code strips them; every other reader pays     |

## Per-line acceptance checklist

A line ships only if every answer is the good one.

- [ ] Could the agent discover this by reading the repo? → must be **no**
- [ ] Is it needed on nearly every task in this repo? → must be **yes**
- [ ] Does it name a literal file path _as an assertion about where code lives_? → must be **no**
- [ ] Does it duplicate `package.json`, `Makefile`, `pyproject.toml`, or CI config? → must be **no**
- [ ] Does it duplicate a user-scope, org-scope, or `review-standard.md` rule? → must be **no**
- [ ] Is it an "always/never" rule about a command or an artefact? → must be **no** (enforce it)
- [ ] Does it contradict another line in the same file, or in a merged file? → must be **no**
- [ ] Would deleting it change any agent behaviour? → must be **yes**

<!-- END principles -->
