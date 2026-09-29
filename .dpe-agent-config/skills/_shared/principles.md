The three constraints, the two admission tests, and the routing table. Source of truth for the
block that `gen_skills.py` inlines into every `SKILL.md`; edit it here, then regenerate.

Everything below the marker ships into each skill. Everything above it is for whoever maintains
this file. The marker is explicit rather than "the first heading" so that reformatting this note
cannot silently move the cut.

<!-- SHIP BELOW -->

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
