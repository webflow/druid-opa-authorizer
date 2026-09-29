---
name: review-md
description: Write or audit a repo's REVIEW.md — the repo-specific failure modes an automated or human reviewer checks, and the reviewer wiring that makes it load. Use when creating REVIEW.md, trimming one that has grown narrative sections, or when `verification.sh lint` reports a REVIEW.md finding.
---

# Writing REVIEW.md

`REVIEW.md` is loaded only when a review is happening, which is the entire reason a third context
file is defensible: it does not spend the startup budget. Under a review tool it spends a
_different_ budget, shared across every listed document, and overflow fails silently — see
**Wiring**.

The file contains **detectable failure conditions specific to this repo**, and nothing else.

## Two tests, both must pass

**Test one — repo specificity.** Would this bullet read identically in another repo?

- Yes → delete it. Generic advice; the reviewer already knows it.
- No → keep it. It names a failure mode specific to _this_ codebase.

"Check for SQL injection", "ensure tests are added" — generic, delete. Every bullet should be
traceable to something that has actually broken, or plausibly can break, here.

**Test two — is it already enforced?** Can the change reach `main` without it? If not — CI, a git
hook, IAM, branch protection — it does not need a bullet.

An agent hook is **not** enforcement for this purpose: humans and agents without hook support
bypass it. A rule whose only layer is an agent hook still earns its bullet.

What survives both is a list of detectable, repo-specific failure conditions, each with a
severity token. That is the whole file.

## Only two sections

```markdown
# Code Review Guidelines — <repo>

<one sentence: what this repo is, and what a reviewer is therefore mainly protecting>

Style, severity tokens, and summary shape follow `.dpe-agent-config/docs/review-standard.md`.
This file lists only the failure modes specific to this repository.

## What to flag

## What not to flag
```

Nothing else. `verification.sh lint` enforces the heading list exactly, and fails on a
`## How to write a review` heading.

## Review style is not in this file

Comment shape, summary shape, the severity vocabulary, the hedging table, and the nit cap are
identical in every repo. They live in `review-standard.md` — one file, one copy — and reach the
reviewer by being listed **first** in the repo's document config.

They are _not_ reached through `~/.claude/CLAUDE.md` or org settings: an automated reviewer runs
as a separate service and reads only the documents its own config names. So "follow the shared
conventions" resolves to nothing unless `review-standard.md` is actually listed. Any repo
`REVIEW.md` that restates them is a second copy to drift and a tax on the shared budget.

## Severity tokens

Three of them — `blocking`, `follow-up`, `nit` — and what each means for the merge decision is
defined in `.dpe-agent-config/docs/review-standard.md`, which is where the definitions live for
the whole fleet. Read them there; do not restate them in the repo's `REVIEW.md`, and note that
this skill deliberately does not restate them either.

What is _authoring_ guidance, and so belongs here:

**State the token, in bold, inside each bullet.** Do not create a heading per severity: it
produces empty sections, and once each bullet carries its token the headings say nothing. The
three tokens are schema-validated by the review tool and map mechanically to the review event;
"high severity", "P1", "important" and "error" map to nothing. This is the single
highest-leverage convention in the file.

A finding that needs work outside the PR is an instruction, not a fourth token — `review-standard.md`
covers the case; write the instruction into the finding.

## Writing a bullet

Phrase each one as a **detectable condition**, not a principle — something a reviewer can check
against the diff without knowing the repo's history. Order the list by severity. One bullet per
failure mode; do not merge two conditions into one. Where it has actually broken, cite the PR or
incident — that is what makes a reviewer act.

> Good — a condition, a severity, a consequence:
> "An input to the checked-in rendered configs changed without a matching regenerated change
> under `components/*/rendered/**` for every affected environment — **blocking**. Preview was not
> run, so the committed configs will not match what deploys."
>
> Good — the gap a gate leaves, phrased as the thing to look for:
> "An Owner tag that is present but is not the team that owns the pipeline — **blocking**. CI
> checks the key exists, not that it is right."
>
> Bad — true anywhere, actionable nowhere: "Ensure error handling is adequate."

## Sourcing failure modes

The inventory is the work, the same way it is for `## Traps` in `AGENTS.md`. Where to look:

- **Reverted and re-fixed PRs.** A change that shipped and came back names a condition a reviewer
  should have caught.
- **Review comments that recur.** If the same correction is written by hand on three PRs, it is a
  bullet.
- **Incident notes**, for the class of failure that reached production.
- **The `## Traps` list in `AGENTS.md`.** Some traps are also review conditions. Keeping one in
  both files is legitimate when it is needed while _writing_ the change and not only while
  reviewing it — record that decision rather than deduplicating on reflex.

## Evidence belongs in a skill, not in this file

A finding's one-line bullet — condition, severity, consequence — is what the reviewer needs. The
incident that proves it, the exact error string, the metric name, the percentile distribution
that sized a threshold, is not review-time content. Inlining it as a `## Lessons` or
`## Background` section, or a numbered evidence appendix, counts against the reviewer's shared
byte budget on **every** PR, whether or not that PR touches the relevant code.

This is not hypothetical. A real `REVIEW.md` grew a `## Lessons (the evidence behind the flags)`
section, one paragraph per numbered finding, cited from the bullets as `(§N)`. Of its twelve
lessons, one genuinely duplicated its bullet's actionable content; the rest carried real incident
evidence a one-line bullet could not hold, and two carried guidance with no bullet at all.

Route that evidence to a skill. It triggers only when its file pattern matches, which is also
_earlier_ — an agent that reads it while writing the change catches the mistake before a diff
exists. Keep the bullet's citation and point it at the skill's own numbering.

## `## What not to flag`

What a reviewer should not spend attention on **in this repo**. High-value: it is what stops a
review drowning in noise. The generic list — lock files, formatter-enforced style, anything a
gate rejects — is already in `review-standard.md`. List only what is specific here.

This is **not** the same as `ignoredFilePatterns` in tool config. An ignored path is dropped from
the changed-file list entirely, which also disables any rule above that keys on it. If a rule in
`## What to flag` fires on a generated path, that path must stay **out** of `ignoredFilePatterns`
and be listed here instead — say so, so nobody "tidies" it into the config later.

Do not enumerate the CI jobs or hook scripts. A "rule | enforced by" table is the repo's own
config restated: discoverable, and stale the first time a job is renamed. What such a table does
carry that is worth keeping is what the gate does _not_ catch — and that is a finding, so it goes
in `## What to flag`.

## Wiring

Every step below fails **silently**. Verified 2026-08-31 against `webflow/reviewflow` @ `1d9e193`;
if the repo uses a different reviewer, find that tool's equivalent of "which docs does the
reviewer read" and re-check the numbers after any upgrade.

1. **Neither file is loaded by default.** `docFilePatterns` defaults to `README.md`,
   `CONTRIBUTING.md`, `AGENTS.md`, `CLAUDE.md`, `.github/CONTRIBUTING.md`, `STYLE_GUIDE.md`.
   `review-standard.md` and `REVIEW.md` are not among them. Unlisted, they never reach the
   reviewer and nothing reports that.
2. **Paths are matched literally.** A glob silently matches nothing.
3. **Order matters and overflow is silent.** `maxDocBytes` (default 30720) is shared by all listed
   docs, and the loader **skips a whole file** rather than truncating it, then continues — so a
   large doc earlier in the list can push a later one out while a smaller later one still loads.
   List the review docs first and drop docs with no review value, and put `REVIEW.md` ahead
   of the shared standard: whole files are dropped, and the repo-specific rules are the ones
   a reviewer cannot infer from the diff.

   ```yaml
   docFilePatterns:
     - REVIEW.md
     - .dpe-agent-config/docs/review-standard.md
     - AGENTS.md
   ```

   `./CLAUDE.md` is not listed because it lives at `./.claude/CLAUDE.md`, so `AGENTS.md` loads
   exactly once.

4. **Path-scoped policy does not belong in this file.** A rule that only matters when a PR touches
   one subsystem is loaded on every review from here, against that shared budget. Put it in a
   path-scoped review rule: it loads only on a match, carries its own budget, and is announced
   with the files that triggered it. Glob patterns need a literal directory anchor — `**/*.ts` and
   `*.md` are dropped before matching, and a malformed rule is skipped silently.
5. **The reviewer is not a linter.** Whether the model honours a stated severity is prompt-driven,
   and a changes-requested review does not itself block merge. For a policy that must never be
   missed, write a CI check as well — it then drops out of this file under test two. Hard gating
   uses the blocking-findings commit status in branch protection, but that status is not posted on
   every PR, so making it a required check can leave PRs waiting forever.
6. **Write provider-neutral conditions.** Do not name the reviewer's internal tools. State what is
   observable in the diff and the repo; let the reviewer choose how to verify it.
7. **Verify it landed.** Open a real PR and confirm (a) a finding that could only come from this
   file, and (b) a comment in the shape `review-standard.md` prescribes. Silent non-delivery is
   the default failure mode of every step above.

## Before you call it done

- [ ] Exactly three headings: the title, `## What to flag`, `## What not to flag`
- [ ] No HTML comments in the shipped file
- [ ] Every bullet names a failure mode specific to this repo and carries a bold severity token
- [ ] No review-style content — it lives in `review-standard.md`, listed first in the doc config
- [ ] No `## Lessons` / `## Background` / evidence appendix; that material moved to a skill
- [ ] Verified on a real PR, not just committed

## Template

`template.md`, beside this file — the title, the `review-standard.md` pointer, and the two
sections. Nothing else may be added to it: lint enforces that heading list exactly.

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
