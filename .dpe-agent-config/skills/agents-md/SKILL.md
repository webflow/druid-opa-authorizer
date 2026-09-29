---
name: agents-md
description: Write, audit, or shrink a repo's root AGENTS.md — the context file every agent loads at startup. Use when creating AGENTS.md for a repo that has none, migrating a bloated one, adding a nested per-directory AGENTS.md, or when `verification.sh lint` reports AGENTS.md findings.
---

# Writing AGENTS.md

`AGENTS.md` is an open standard, tool-agnostic, checked into git, loaded at startup by every
agent, and sitting below the system prompt. It is the one file in the repo that every tool
reads, so it is also the most expensive place to put anything.

This procedure is **mostly subtractive**. Most of the work is deleting what the source tree
already answers and routing "always/never" rules into an enforcement layer. Expect the finished
file to be short — prose under ~40 lines.

Companion files: `.claude/CLAUDE.md` is written with the `claude-md` skill and is required (it
is what makes any of this reach Claude Code); `REVIEW.md` is written with the `review-md` skill.

## 1. Inventory before you write

Do not open the template-shaped file and fill in headings. Collect candidate facts first, from
sources the source tree cannot supply:

- the existing docs, and the file you are replacing
- the git log
- code comments marked `TODO` / `WARNING` / `HACK`
- incident notes
- the questions people actually ask in review

`/init` output (Claude Code, `CLAUDE_CODE_NEW_INIT=1`) is acceptable as a **fact inventory** for
this step. It is not acceptable as the file: its default is comprehensiveness, which is the
opposite of this standard. Route its proposal line by line like any other candidate.

Skipping this step and then concluding the repo has no traps is the single most common failure.

## 2. Route every candidate

Run each fact through the routing table below. Write the destination next to it. For an
enforcement rule, name the **layer** — "agent hook" alone is not a finished destination.

## 3. Write the file from the survivors

Fixed section names, fixed order. `verification.sh lint` enforces both.

| #   | Section                      | Tier                         |
| --- | ---------------------------- | ---------------------------- |
| 1   | `# <repo>` plus one sentence | **required**                 |
| 2   | `## Environments`            | **required** (see exception) |
| 3   | `## Non-obvious commands`    | conditional                  |
| 4   | `## AWS access`              | conditional                  |
| 5   | `## What a merge reaches`    | conditional                  |
| 6   | `## Traps`                   | **required**                 |
| 7   | `## Cross-repo coupling`     | conditional                  |
| 8   | `## Enforced automatically`  | conditional                  |
| 9   | `## Further reading`         | **required**                 |

**Required** means present and non-empty. **Conditional** means omitted entirely, never left
empty — the value of the fixed list is being forced to consider all nine and consciously drop
what does not apply. Do not invent a section, rename one, or reorder them.

Order is fixed so scanning transfers between repos: environment and access before you run
anything, traps and merge consequences before you change anything, routing last.

### What goes in each section

**`# <repo>` + one sentence.** What this repo is and what it produces. Not a paragraph, not a
feature list.

**`## Environments`** — usually the highest-value section in a data-infrastructure repo, and
almost never derivable from a quick read: which account is which, which region, which is
protected, which stack a given change actually lands in. Get it wrong and the agent acts on the
wrong account. A table of env / account / region / notes. Check the security policy on
committing account IDs first; if they may not be committed, name the accounts and point at
where the mapping lives.

_Exception:_ required for deploy-target repos (sandbox/dev/prod). For a library or connector
with no deploy targets it is noise — omit it and say so in the PR.

**`## Non-obvious commands`** — only what is unguessable. The package manager if it is not the
language default; the one canonical test invocation if it is not the obvious one; anything that
cannot be guessed, such as an env var the tests need. If you are writing a table of scripts,
delete it — the agent reads `package.json` / `Makefile` / `pyproject.toml` anyway.

**`## AWS access`** — the tool-agnostic half of the credential convention: which profile a
session uses, that it is read-only, how to assume it. What _makes_ it read-only is IAM, not this
text; name that under `## Enforced automatically`. The hook-specific invocation shape belongs in
`.claude/CLAUDE.md`.

**`## What a merge reaches`** — only half of this passes the admission tests, so keep only that
half. The _mechanism_ (a push to main triggers a deploy) is discoverable from
`.github/workflows/`: one line at most. The _gap_ — what passing CI does not prove — is
discoverable from nowhere, and is what earns the section. It matters most in a repo whose hooks
block every local mutation: an agent that has watched its own commands get denied all session
reads the whole repo as safe, and merge is then the one destructive path left unguarded.

**`## Traps`** — see step 4. If genuinely none, write `None recorded yet.`

**`## Cross-repo coupling`** — only what reaches outside this repo: another stack's outputs,
another repo's contract, a shared bucket or catalog. Not derivable by definition — the agent
cannot read a repo it does not have. Name the repo and what flows across. Do not name file paths.

**`## Enforced automatically`** — a _notice_, not a rule set. The rules live in the layer named
in the table. This section exists so an agent that gets blocked understands why and corrects,
instead of retrying variations of the same command. The "Where" column is the point: it tells a
non-Claude agent whether the gate applies to it.

A rule listed here must **not** also appear as prose elsewhere in the file. A rule whose only
layer is an agent hook is a gap for humans — either add a git/CI/IAM layer, or leave the row as
written so the gap is visible, and say so in the PR.

Describe each hook by what it actually does, not by what you wish it did. `aws-readonly`, for
instance, is deliberately blind to the verb: it enforces that a credentialed call **names an
allowed profile**, and IAM is what rejects a write. A row claiming the hook "blocks aws writes"
promises something no layer delivers.

**`## Further reading`** — the progressive-disclosure mechanism, and how the file stays short.
Point at documents that load only when relevant instead of inlining them. Name each document by
what it is for, so the agent knows when to open it. A handful of links, one hop deep.

These links are **reference material, not rules** — content reached by following a link is data
the agent may consult, not an instruction it is bound by. A rule that must bind goes in this
file, in an `@import`, or in an enforcement layer.

If a subdirectory has its own `AGENTS.md`, say so here: Codex only picks it up when started in
that directory, so this pointer is how a root-started session learns it exists.

### Never in this file

A command table (duplicates `package.json` / `Makefile`); an architecture or directory
description (the file system is the documentation); a path asserted as content ("auth lives in
`src/auth/handlers.ts`"); anything a generator produced unedited; HTML comments — only Claude
Code strips them, and `verification.sh lint` fails on `<!--` in a shipped `AGENTS.md`.

## 4. Sourcing the `## Traps` section

Traps are the one required section the code cannot supply, and the one most often left empty by
someone who concluded the repo has none. It does not. Four signals, in yield order — all four
returned real material on a repo that had actually been worked on.

**1. The fix of a fix.** The strongest signal there is. When the same thing is corrected twice
running, the first fix was wrong because the code misleads — which is the definition of a trap.

```bash
git log --oneline -300 | grep -iE 'revert|re-?fix|fix .*(again|properly|correctly)|actually|instead of'
```

On `druid` this returned `1d8832c` "use maxLowPercent instead of maxLowPriorityConcurrency"
followed by `36329c9` "remove erroneous .hilo. prefix" — one JVM property, wrong twice running.
That pair became the trap about Druid config that is valid TypeScript and only fails on the node.

**2. Intent comments.** The "not in the tree at any depth" tier, in the one place an engineer
does write it down.

```bash
grep -rn -iE "on purpose|intentional|deliberate|by design|do not (change|fix|remove)|must not" \
  --include='*.ts' --include='*.py' --include='*.yaml' .
```

On `druid` this surfaced a node-id tag carrying `DO NOT CHANGE`, because the ZooKeeper ensemble
identifies members by it. Note what that means: an engineer had already recorded the trap, and
it still had not reached the context file.

**3. Churn.** Repeat edits cluster on the code that is hard to get right.

```bash
git log --format= --name-only -200 -- '*.ts' | grep -v '^$' | sort | uniq -c | sort -rn | head
```

Not a trap by itself — a map of where to point signals 1 and 2.

**4. The file you are replacing, plus incident notes.** A `Known Gotchas` section, a `#1 rule`
blockquote, a `troubleshooting_reports/` directory. Carry these across; someone already paid for
them. Check whether the directory is gitignored before citing it — if it is, anything quoted
from it will not exist in a fresh clone or in CI.

**Turning a signal into a bullet.** A trap qualifies only if an agent reading the code would
reasonably conclude the opposite. State what it looks like, then what is true, then the
consequence. One bullet per trap, no history, no ticket archaeology. A commit that fixed a bug
is not a trap; a commit that fixed the _same_ bug twice is pointing at one.

> Good: "A typo in an interface field name is misspelled consistently everywhere; correcting it
> in one place breaks the build."
>
> Good: "The rendered config is generated inside `pulumi.apply()`, so `pulumi preview` does not
> show it."
>
> Bad: "Be careful when changing configuration." — true everywhere, actionable nowhere.

**The residue needs a person.** When the four signals are exhausted, what is left lives in
someone's head. Ask a specific question, not "any gotchas?" — ask _"what has cost you or someone
else a debugging session in this repo, where the code looked right?"_ Leave `## Traps` empty and
flag it rather than inventing filler. An unanswered required section is a question; filler is
worse than a gap, because it reads as though someone checked.

## 5. Caps

Prose under ~40 lines. The `## Environments` table and the `## Traps` list are the only sections
allowed past that. If the traps list runs past ~8 bullets, check whether the surplus are review
rules and move those to `REVIEW.md`, where they load only when a review is happening.

**The cap is a prompt to check, not a reason to delete a real trap.** `druid` sits at nine: two
of them are also `REVIEW.md` blocking rules, kept in both deliberately because they are needed
while _writing_ the change, not only while reviewing it. Record that decision rather than
silently trimming to fit.

## 6. Nested directories

When a subsystem needs its own instructions, create **both** files:

```
<dir>/AGENTS.md   # the content
<dir>/CLAUDE.md   # exactly one line: @AGENTS.md
```

Neither alone is enough, and the reason is an asymmetry between the two tools:

- **A nested `AGENTS.md` alone is invisible to Claude Code.** It traverses `CLAUDE.md` only.
- **A nested `CLAUDE.md` alone is invisible to Codex.**
- **A nested file reaches Codex only if Codex is started in that directory.** Codex walks up,
  never down: from the repo root it will not pick up `packages/foo/AGENTS.md` even after reading
  files there.
- **Nested Claude context drops after `/compact`** until a file there is read again. Root
  `CLAUDE.md` is re-read from disk after compaction; nested files and path-scoped rules are not.

So: a rule that must hold all session belongs at the root. Where the audience is Claude only,
prefer a path-scoped rule (`.claude/rules/<topic>.md` with `paths:`) over a nested file — it
reloads on the next matching read. `verification.sh lint` fails on a nested `AGENTS.md` with no
`CLAUDE.md` beside it, and on the reverse.

## 7. Migrating an existing file

Shrinking a context file is only safe if nothing is silently lost.

1. Take the line count before. `/doctor` (Claude Code ≥ 2.1.206) proposes trims for a
   checked-in `CLAUDE.md` — use it as a first pass, not a verdict. Every proposed cut still goes
   through step 2.
2. Route every existing line through the routing table.
3. Produce a written accounting: **every dropped line** with its destination — `→ git hook + CI`,
   `→ IAM`, `→ agent hook (early signal)`, `→ skill`, `→ README`, `→ nested pair`, `→ rule`, or
   `→ dropped: discoverable`.
4. Facts that are genuinely not derivable from source — account IDs, environment mappings,
   protected resources, cross-repo coupling, known traps — must appear in the accounting with a
   real destination. "Dropped: discoverable" is not acceptable for any of them.
5. A rule moved from prose to enforcement must show a cross-agent layer, or an explicit
   "agent-hook only, gap accepted" with a reason.
6. Keep the accounting in the repo (a `MIGRATION.md` or a PR comment). It is what makes the
   shrink reviewable.

## 8. Verify

```bash
.dpe-agent-config/verification.sh lint     # names, order, required sections, no HTML comments
.dpe-agent-config/verification.sh probe    # obedience, not just loading
```

Fix findings and re-run until clean. Then confirm the file actually loads: `/context` in a
Claude Code session lists memory files loaded at startup. It does **not** show nested files or
path-scoped rules — for those, register the `log-instructions` hook and check its log after
reading a file in the nested directory.

## Before you call it done

- [ ] Prose under ~40 lines; traps list under ~8 bullets (or the overflow is justified in the PR)
- [ ] No HTML comments anywhere in the file
- [ ] Section names and order match the table above; the three required ones are present and
      non-empty
- [ ] No reference chain more than one hop deep
- [ ] Every nested instruction directory has both `AGENTS.md` and a `CLAUDE.md` containing
      `@AGENTS.md`
- [ ] Every enforcement rule exists in a layer every agent hits, or the gap is recorded in
      `## Enforced automatically`
- [ ] A migration accounting exists for anything removed
- [ ] `.claude/CLAUDE.md` exists and opens with a bare `@../AGENTS.md` (the `claude-md` skill)

## Template

`template.md`, beside this file — the nine sections in order, with a bracketed placeholder in
each. Start from it and delete every conditional section this repo does not need; a placeholder
left in a shipped file is worse than an omitted section, because it passes the shape check while
saying nothing.

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
