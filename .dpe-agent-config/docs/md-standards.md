# md-standards.md

Operative rules for writing and auditing agent context files (`AGENTS.md`, `CLAUDE.md`,
`REVIEW.md`) in Data Engineering repos.

**This file is a rubric, not an essay.** It is written to be handed to an agent that must
mechanically accept or reject candidate content. Every rule below is either a test you can
apply to a single line, or a routing decision. If a section here reads as advice rather than
a test, it is a defect in this file.

**This file is the contract; the skills are the procedure.** It says what each file _is_, what
must hold, and which layer enforces it. _How to produce one_ lives in `skills/agents-md/`,
`skills/claude-md/` and `skills/review-md/`, which load only when that is the task — this file
stays loaded-on-demand reference for the rules and the rationale.

The skills, the shared `review-standard.md`, and `./verification.sh lint` are all derived from
this file. When they disagree, this file wins and the other artefact is the bug. Lint hardcodes
its own copy of the canonical section list (`verification.sh`); keep the two in step by hand when
either changes.

Sources, checked 2026-09-01. Official docs first; blog posts are secondary and dated:

- [Claude Code — How Claude remembers your project](https://code.claude.com/docs/en/memory)
  (memory files, imports, `.claude/rules/`, comment stripping, compaction behaviour)
- [Claude Code — Hooks](https://code.claude.com/docs/en/hooks-guide) (`PreToolUse`,
  `InstructionsLoaded`)
- [OpenAI Codex — AGENTS.md](https://developers.openai.com/codex/guides/agents-md) (discovery
  order for `AGENTS.md`)
- [OpenAI Codex — Hooks](https://developers.openai.com/codex/hooks) (`.codex/hooks.json`,
  `PreToolUse` contract, trust review)
- [lefthook](https://github.com/evilmartians/lefthook) (git hook manager; config and scripts are vendored)
- [Is Progressive Disclosure All You Need for Long-Context Agents?](https://arxiv.org/abs/2607.17598),
  He et al., July 2026
- [A complete guide to AGENTS.md](https://www.aihero.dev/a-complete-guide-to-agents-md)
- [How to use Claude Code hooks to enforce the right CLI](https://www.aihero.dev/how-to-use-claude-code-hooks-to-enforce-the-right-cli)
- [Never run claude init](https://www.aihero.dev/never-run-claude-init) — partly superseded,
  see §6 step 1

Anything below marked _measured_ was observed by us on the date given, not read from docs.
Re-measure before relying on it after a tool upgrade.

---

## 1. The three constraints everything follows from

**Constraint 1 — the instruction budget.** Models have no known fixed instruction limit.
Reliability declines as the number, complexity, and interaction of active constraints increase.
Always-loaded context costs tokens and creates interference even when most rules are inactive,
so repository instructions must be concise, clearly scoped, and loaded only where relevant.

**Constraint 2 — load timing.** Startup context files are hardwired into the session before
the task is known and cannot adapt to it. Everything in them is paid for on every request,
whether the session is about a DAG, a Pulumi stack, or a typo in a README.

**Constraint 3 — the audience is every agent, not one.** These repos are worked on by Claude
Code, Codex, and whatever comes next. A mechanism that only one tool honours is not a repo
rule; it is a per-tool convenience. Anything that must hold has to hold in a layer every agent
passes through (§3, §5.4).

All three point the same way: **the correct default for any candidate line is to exclude it,
and the correct default for any rule is to enforce it below the agent layer.** Inclusion must
be argued for.

---

## 2. The two admission tests

A line may live in a startup-loaded context file (`AGENTS.md` / `CLAUDE.md`) only if it
passes **both**:

| Test                          | Question                                               | Fails when                                                                        |
| ----------------------------- | ------------------------------------------------------ | --------------------------------------------------------------------------------- |
| **Not derivable from source** | Could the agent reach this by reading the source tree? | It restates `package.json`, the `Makefile`, the directory layout, or the imports. |
| **Globally relevant**         | Is this needed on ~every task in this repo?            | It applies to one subsystem, one language, one workflow, or one kind of change.   |

Derivable-and-global → delete. Not-derivable-but-local → route it (§3).
Not-derivable-and-global → it belongs in the file. That set is small; expect 10–40 lines.

### "Not derivable from source" does not mean unknowable

The test is scoped to **the source tree**, not to knowledge in general. Read it as "unknowable"
and you get a paradox: if an agent cannot discover the content, an agent cannot write the file
either, and only an engineer can. That is not the situation. Three different things sit under
this test, and they have different authors:

| Kind                         | Example                                                                                                                             | Who authors it                                                                                                      |
| ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| **Scattered but present**    | Account IDs and the env→account mapping both sit in `Pulumi.*.yaml`                                                                 | An agent. It _can_ assemble this; the point is that it should not pay for the lookup on every task                  |
| **Surface reading misleads** | `protect: true` reads as prod-only and applies everywhere; an empty `blockDeviceMappings` silently voids the configured volume size | An agent, but only with care — a normal read reaches the _wrong_ conclusion. This is where the file is load-bearing |
| **Intent and history**       | "dev reads prod buckets by design — do not fix it"; "this typo is load-bearing"; "this broke prod twice"                            | Not in the tree at any depth                                                                                        |

Only the third kind needs a human, and usually as confirmation rather than authorship. It still
lives somewhere an agent can reach — git log, incident notes, `TODO`/`WARNING`/`HACK` comments,
PR threads, and the file being replaced. §6 points at exactly those, and it works: the traps in
the worked examples came from spotting the same JVM property set wrongly in two consecutive
commits, and from a prod failure cited by PR number — neither from reading the code.

Two consequences worth holding on to:

- **This rubric is mostly subtractive.** Deleting what the tree already answers, routing
  "always/never" rules into enforcement, enforcing the section schema — none of that needs
  privileged knowledge, and it is most of the value.
- **Where an agent cannot author, it can interrogate.** It cannot invent a trap. It can report
  that `## Traps` is empty and ask what has cost someone a debugging session here. An empty
  required section is a question pointed at an engineer, which is half the reason that section
  is required.

The canonical example of a passing line, from the source article, is a developer whose entire
context file read: _"you are on WSL on Windows."_ Six words. Undiscoverable from source,
relevant to every path the agent resolves.

---

## 3. The routing table

This is the core of the standard. Every candidate fact routes to exactly **one** destination
(a rule may additionally get an agent hook as an early signal — see the hook row). Two axes
make multiple files coherent rather than three overlapping context taxes: **when it is loaded**
and **who it reaches**.

| Destination                                                                                                                                                      | Loaded / applied                                                                                                                                             | Reaches                                                                                     | Admission test                                                                                                                                                                                                                                           |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `AGENTS.md`                                                                                                                                                      | Every session, at startup                                                                                                                                    | Every agent                                                                                 | Not derivable from source **and** needed on ~every task **and** tool-agnostic                                                                                                                                                                            |
| `.claude/CLAUDE.md`                                                                                                                                              | Every Claude Code session, at startup                                                                                                                        | Claude Code                                                                                 | Same, but _Claude-Code-specific only_. Opens with a bare `@../AGENTS.md` import — never a second copy, never a symlink                                                                                                                                   |
| `REVIEW.md`                                                                                                                                                      | Only during review                                                                                                                                           | The reviewer                                                                                | Detectable, repo-specific failure conditions. On-demand loading is the only reason a third file is defensible                                                                                                                                            |
| **git hook** (`commit-msg`, `pre-commit`, `pre-push` via lefthook / pre-commit) + **CI check**                                                                   | At commit / push / PR                                                                                                                                        | Every agent and every human                                                                 | An enforcement rule about the _artefact_ — commit format, branch name, lint, generated files in sync                                                                                                                                                     |
| **IAM / branch protection / CODEOWNERS**                                                                                                                         | Always, by the platform                                                                                                                                      | Everyone, regardless of tool                                                                | An enforcement rule about _access_ — read-only credentials, no direct push to `main`, human approval before deploy                                                                                                                                       |
| Agent `PreToolUse` hook — a named catalog module in `.dpe-agent-config/hooks/agent/`, registered by name in both `.claude/settings.json` and `.codex/hooks.json` | At tool-call time                                                                                                                                            | Claude Code and Codex (same script, same stdin/exit contract); not humans, not other agents | The same rule as a row above, **in addition**, when denying at the tool call saves a round trip. Alone only for tool-choice rules that never reach a commit (`npm` → `pnpm`). Codex users must trust the hook via `/hooks`, and again after every change |
| Skill (`.claude/skills/<n>/SKILL.md`)                                                                                                                            | When its trigger matches                                                                                                                                     | Claude Code (Codex: only if also exposed as its skill format)                               | Steering needed by a _fraction_ of sessions — a workflow, a runbook, a subsystem's procedure                                                                                                                                                             |
| `README.md`                                                                                                                                                      | Never, by an agent                                                                                                                                           | Humans                                                                                      | Setup, deploy steps, operational runbooks                                                                                                                                                                                                                |
| Path-scoped rule (`.claude/rules/<n>.md` with `paths:` frontmatter)                                                                                              | When Claude reads a file matching the glob; re-applied after `/compact` when a matching file is read again                                                   | Claude Code only                                                                            | A convention for one language, directory, or subsystem. Native to Claude Code — prefer it over a nested file **when the audience is Claude only**                                                                                                        |
| Nested `AGENTS.md` **+** nested `CLAUDE.md` containing only `@AGENTS.md`                                                                                         | Claude Code: when it reads a file in that directory (not re-applied after `/compact` until it reads there again). Codex: only when started in that directory | Both, asymmetrically — see §5.1                                                             | A package-scoped convention that every agent needs. Neither file alone is enough                                                                                                                                                                         |
| Path-scoped review rule (e.g. `.agentflow/rules/<n>.md`)                                                                                                         | When a changed file matches its declared paths                                                                                                               | The reviewer                                                                                | A review rule that matters only for one subsystem — it gets its own budget instead of taxing every review                                                                                                                                                |
| **Nowhere — delete**                                                                                                                                             | —                                                                                                                                                            | —                                                                                           | Discoverable from source, duplicated from config, or stale-prone                                                                                                                                                                                         |

### Routing heuristics

- Contains an imperative about a CLI or an artefact (`use pnpm`, `prefix branches with`,
  `read-only aws profile`) → **git hook / CI / IAM first**, agent hook second. Markdown lowers
  the probability of a violation; enforcement below the agent makes it impossible for every
  agent, not one.
- A rule whose only enforcement is an agent hook is a **gap** for humans and for any agent
  without hook support, and for Codex users who have not re-trusted it. Either add a layer
  above it, or record the gap in `## Enforced automatically`. Do not delete the
  prose from `AGENTS.md` until a cross-agent layer exists.
- Contains an exact file path _as an assertion_ → **delete**, or move to a skill that is re-read
  on use. Paths go stale the moment code is reorganised, and a stale path actively misleads.
- Contains a command list → **delete**. It duplicates `package.json` / `Makefile` and the agent
  reads those anyway. The exception: the _one_ canonical test/lint invocation when it is not the
  language default — one line, because an agent that does not read `package.json` first will
  guess wrong.
- Describes architecture, module layout, or data flow → **delete**. The file system is the
  documentation. If the layout is not self-evident, fix the layout.
- Is a rule you added because an agent annoyed you once → **hook or skill**, not a global rule.
  Context files are not a complaints box.

---

## 4. Anti-patterns — reject on sight

Grep for these when auditing an existing file:

| Pattern                                                                                        | Why it fails                                                                         | Action                                                         |
| ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | -------------------------------------------------------------- |
| Raw output of `/init` or any generator, shipped unedited                                       | Optimises for comprehensiveness; the opposite of the goal                            | Delete the file, start from the template (§6 step 1)           |
| A "Commands" / "Scripts" table                                                                 | Duplicates `package.json` / `Makefile`                                               | Delete; keep at most the one unguessable invocation            |
| "Architecture" / "Project structure" section                                                   | Discoverable; goes stale on every refactor                                           | Delete                                                         |
| A path **as an assertion about where code lives** ("auth lives in `src/auth/handlers.ts`")     | The tree already answers it, and it misleads the moment the file moves               | Delete (same test as §8)                                       |
| A path **as a pointer** in **Further reading** ("Review conventions — [REVIEW.md](REVIEW.md)") | Progressive disclosure; the agent opens the file on demand                           | Keep — not an anti-pattern (§5.1, §8)                          |
| Two rules that conflict                                                                        | Accumulates silently as files grow                                                   | Reconcile or delete both                                       |
| Vague or obvious instructions ("write clean code", "add tests")                                | Spends budget, changes nothing                                                       | Delete                                                         |
| "Always …" rules scoped to one domain                                                          | Global cost, local benefit                                                           | Move to a skill or a path-scoped rule — one level, not a tree  |
| A must-hold rule enforced **only** by an agent hook                                            | Silently absent for humans, for agents without hooks, and for Codex until re-trusted | Add a git/CI/IAM layer, or record the gap                      |
| A hook script or `review-standard.md` edited inside a consumer repo                            | Drifts from the fleet copy; the next sync overwrites it                              | Change it in `dpe-agent-config`; CI `drift` check fails the PR |
| A reference chain more than one hop deep                                                       | Recursive disclosure measured worse than flat, sometimes much worse (§5.1)           | Flatten it                                                     |
| Duplication of a user-scope, org-scope, or shared-standard rule                                | Duplication is how conflicting rules start                                           | Reference, do not copy                                         |
| HTML comments left in a shipped `AGENTS.md` or `REVIEW.md`                                     | Only Claude Code strips them; every other reader pays for them                       | Delete before merge — lint fails on `<!--` in these two files  |

---

## 5. Per-file specification

### 5.1 `AGENTS.md` (root)

Open standard, tool-agnostic, checked into git, sits below the system prompt. What it must
contain, for this fleet, is the canonical section list below — fixed names, fixed order.
Everything else is a **light reference link** to a file loaded on demand — progressive
disclosure:

```markdown
For deployment conventions, see docs/DEPLOY.md
```

**Keep disclosure one level deep.** Rules then load only when relevant, each file stays focused,
and the set survives model changes.

Do **not** build a tree of references-to-references. The aihero article suggests nesting
hierarchically (`docs/TYPESCRIPT.md` → `docs/TESTING.md` → a specific runner); measurement
disagrees. _Is Progressive Disclosure All You Need for Long-Context Agents?_
([arXiv:2607.17598](https://arxiv.org/abs/2607.17598), He et al., July 2026) compares raw
navigation, flat disclosure (one indexed level) and hierarchical disclosure (recursive levels)
across three agent harnesses:

- **Flat disclosure pays off at scale.** Over a 20-document library, English open QA went from
  0.257 (raw) to 0.462 — about 1.7×.
- **Hierarchical depth "never helps on a single book and sometimes hurts."** One model's
  multiple-choice accuracy collapsed from 0.9126 to 0.6398 under recursive packing.
- **Strong navigators gain nothing from extra depth.** Flat structure mostly rescues weak
  navigators; Codex showed no benefit from the deeper packing on a single document.

So: a root file plus a **flat** set of referenced documents. One hop, not three.

**Two limits on how far to carry that paper.** It measures document _question-answering_, so its
subject is whether an agent can _find_ content — not whether it _complies_ with rules. Those are
different problems, and the compliance one has a harder ceiling: see "Reading a file is not the
same as being instructed by it" below. And its gains appear at library scale. A single repo with
one subsystem is the "single book" case, where structure bought nothing and sometimes cost
accuracy — so do not split a small repo's context into files at all. Keep one `AGENTS.md` until
the material genuinely justifies more.

### The canonical section list

`AGENTS.md` uses **fixed section names in a fixed order**. This is not stylistic. A survey of the
six repos that already had context files found **no H2 heading common to all six** — yet every one
of them had traps, recorded in prose under a different name or no name at all. Only one had a
section for them. Filler in an empty section is a manageable risk; a section nobody thought to
write is not, because nothing prompts for it.

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

**Required** means present and non-empty. A repo with no known traps writes `None recorded yet.` —
that is information (nobody has hit one) where silence is ambiguous (the author skipped it), and it
makes the first real trap an edit rather than a section someone has to invent.

**Conditional** means omitted entirely, never left empty. The value of the fixed _list_ is being
forced to consider all nine and consciously drop what does not apply.

**`## AWS access`** holds the tool-agnostic part of credential conventions: which profile or role
an agent session uses, that it is read-only, how to assume it. It is conditional because a library
has none. The _Claude-hook-specific_ invocation shape (what the hook accepts) belongs in
`.claude/CLAUDE.md` (§5.2); the IAM policy that actually makes it read-only is the enforcement
layer (§5.4) and is named in `## Enforced automatically`, not described here.

**Order is fixed** so that scanning transfers between repos: environment and access before you run
anything, traps and merge consequences before you change anything, routing last.

`./verification.sh lint` enforces the names, the order, and the three required sections.

**Exception:** `Environments` is required for the DATE fleet, where every repo targets
sandbox/dev/prod. For a library or a connector with no deploy targets it is noise — drop it and say
so in the PR. `lint` cannot make that judgement, so declare it: `AGENTS_MD_NO_ENVIRONMENTS=1` in
`.agents/config.env`, which shows up in the diff. Silence means the section is required.

**How to write one:** the `agents-md` skill (`.dpe-agent-config/skills/agents-md/`) — what belongs
in each section, the four-signal procedure for sourcing `## Traps`, the caps, the migration
accounting, and the template the file starts from. It is registered as a stub in
`.claude/skills/` and
`.agents/skills/`, so asking either tool to write or audit an `AGENTS.md` reaches it.

### Nesting — the two tools disagree, and not symmetrically

Documented behavior on both sides, not folklore — confirmed against each vendor's own docs, then
reproduced by obedience: a root file said "end every reply with ROOT-11", a nested one said "in
this subdirectory use SUB-22 instead".

|                          | Ancestor files (cwd upward)               | Descendant files (below cwd)                                                                              |
| ------------------------ | ----------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Claude Code, `CLAUDE.md` | loaded at startup, concatenated root-down | **included** when it reads a file in that directory; **dropped by `/compact`** until it reads there again |
| Codex, `AGENTS.md`       | loaded at startup, merged                 | **excluded from the instruction chain** — the walk stops at the starting directory and never descends     |

**Claude Code: inclusion and obedience are two different facts, and only one is guaranteed.**
Anthropic's own docs state inclusion plainly — a nested `CLAUDE.md` is "included when Claude
reads files in those subdirectories" — but they state just as plainly that obedience isn't
guaranteed once included: `CLAUDE.md` content "is delivered as a user message after the system
prompt... there's no guarantee of strict compliance." Reproducing this: reading the nested
`AGENTS.md` file itself produced no switch to SUB-22 in one run; reading an unrelated file in the
same directory did, in another. Both most likely included the nested pair either way — the
difference was whether that run's reasoning chose to follow it, not whether it loaded. To tell
"included but ignored" apart from "never included" for certain in a given session, use the
`InstructionsLoaded` hook (`log-instructions` in the catalog) rather than reading the final
answer alone — closing that out for real is still open (`iterate-1.md` I1).

**Codex has no equivalent ambiguity.** OpenAI's own docs state the walk "stops searching once it
reaches your current directory" — a descendant `AGENTS.md` is architecturally excluded from the
instruction chain, not merely deprioritized. Started at the root, Codex stayed on ROOT-11 even
when told to read the nested `AGENTS.md` outright — it **described the rule correctly and then
ignored it**, because for Codex, reading a file and being instructed by one are different
mechanisms, and the nested file was never eligible to reach the second. Started inside the
subdirectory, it obeyed immediately, with zero tool calls — that directory is now on the walk.
Each directory on the walk actually checks `AGENTS.override.md` first, then `AGENTS.md`, then any
name added to `project_doc_fallback_filenames` in config — a richer per-directory check, same
walk. To see exactly what loaded for a real session: `codex --ask-for-approval never "Summarize
the current instructions."`

Sources: [Claude Code — How Claude remembers your project](https://code.claude.com/docs/en/memory),
[Codex — AGENTS.md](https://developers.openai.com/codex/guides/agents-md).

Consequences:

- **A nested `AGENTS.md` alone is invisible to Claude Code.** It traverses `CLAUDE.md` only.
  Give the subdirectory a `CLAUDE.md` whose only line is `@AGENTS.md` — relative imports resolve
  against the importing file, so it picks up its neighbour, not the root one.
- **A nested `CLAUDE.md` alone is invisible to Codex.** So a package-scoped convention that
  every agent needs is always the _pair_.
- **A nested file reaches Codex only if Codex is started in that directory.** Codex walks up,
  never down: from the repo root it will not pick up `packages/foo/AGENTS.md` even after reading
  files there. Per-package context is reliable for Claude Code mid-session, and for Codex only
  when the working directory is the package.
- **Nested Claude context drops after `/compact` until re-read** — not gone for good, just not
  automatic. Root `CLAUDE.md` is re-read from disk after compaction; nested files and path-scoped
  rules only come back once a matching file is read again. A rule that must hold across a long
  session belongs at the root.

Where the asymmetry matters, keep the fact at the root instead of nesting it, or accept that
Codex users must `cd` into the package and say so in `## Further reading`.

### Reading a file is not the same as being instructed by it

The Codex result above is the general rule, and it is a security property rather than a defect:
**by default, content an agent reads as a file does not enter its automatic instruction chain —
reading it and being bound by it are different mechanisms.** This is about default, automatic
behaviour, not an absolute: an explicit "the rules in this file are binding" is ordinary
instruction-following of the current prompt, unrelated to the memory channel. What does not
happen on its own is a tool treating an arbitrary file it happens to open as if it had been
loaded like `CLAUDE.md`/`AGENTS.md` — a tool that did would be trivially prompt-injectable. Only
the sanctioned memory channel — a memory filename the tool loads, or an `@import` into one —
makes text bind without being asked. The official memory docs say the same thing from the other
side: memory files are context, not enforced configuration; to block an action regardless of
what the model decides, use a hook.

Two consequences for how the skills and the stubs are written:

- _"The agent will read `docs/CONVENTIONS.md` and follow it"_ is not a mechanism. If a rule must
  bind, `@import` it into the memory file, or enforce it below the agent (§5.4). Never rely on a
  link.
- The links under **Further reading** are therefore reference material, not rules. That is the
  correct use: the agent consults them when relevant and is not bound by them. Do not move a
  must-follow rule behind a link and consider the job done. Verify with `./verification.sh probe`.

### 5.2 `.claude/CLAUDE.md`

Claude Code's own memory filename. Claude Code does not read `AGENTS.md`, so this file is the
bridge.

**Location is fixed: `./.claude/CLAUDE.md`. Never `./CLAUDE.md`.** Both are valid to Claude
Code; we standardise on the nested one for two reasons:

1. The repo root then carries exactly one agent file (`AGENTS.md`), which is the whole point.
2. The review tool's default document list includes `./CLAUDE.md` but not `./.claude/CLAUDE.md`,
   so the reviewer loads `AGENTS.md` once instead of once directly and once via the import.

Whether Claude Code loads both locations when both exist is not documented. We do not find out
per repo: `./verification.sh lint` **fails** if `./CLAUDE.md` exists.

**Always the `@../AGENTS.md` import. Never a symlink.**

A symlink is not broken — the reviewer reads docs from the working tree with `readFile`, which
follows symlinks. The problem is subtler and costs you the thing you care about:

- **A symlink makes the reviewer load the same content twice.** `AGENTS.md` and `CLAUDE.md` are
  both in the reviewer's default document list, and it dedupes by **path, never by content**.
  Both get appended and both are charged against the shared byte budget (default 30,720). The
  loader skips _whole files_ when that budget runs out — so the duplicate can silently push
  `REVIEW.md` out of the review entirely.
- **A symlink cannot carry Claude-only content.** The moment you need one line about a hook, you
  are converting to an import anyway.
- **Windows.** Creating a symlink needs Administrator or Developer Mode, and a Windows checkout
  may materialise it as a text file containing the target path.

The import has none of these properties and one requirement: write it bare on its own line.
Backticks and code fences suppress it silently. Paths resolve **relative to the file that contains
the import**, not the working directory and not the repo root. Imports nest to a maximum depth of
four hops.

| `CLAUDE.md` location       | `AGENTS.md` location       | Import line     |
| -------------------------- | -------------------------- | --------------- |
| `./.claude/CLAUDE.md`      | `./AGENTS.md`              | `@../AGENTS.md` |
| `./packages/foo/CLAUDE.md` | `./packages/foo/AGENTS.md` | `@AGENTS.md`    |

Copy-pasting `@AGENTS.md` into `./.claude/CLAUDE.md` silently resolves to a non-existent
`.claude/AGENTS.md` and loads nothing. Lint checks the import resolves to a file that exists.

**What belongs below the import.** Most repos need nothing beyond the import and the one-line
bridge sentence. Add a line only when **both** hold: the fact is meaningless outside Claude Code,
and discovering it by being hook-blocked would waste a round trip while the correct form remains
non-obvious. Typical survivors: the credential invocation shape the hook accepts (e.g.
`AWS_PROFILE=<n> pulumi …` vs `aws --profile`), a pointer to run
`.dpe-agent-config/hooks/agent/test-hooks.sh` after editing hooks, a one-line note that
`.claude/rules/` exists. Do **not** add: a skills table
(auto-discovered and already in context), a hook inventory (denial messages are the
documentation), slash commands, subagents, or anything that belongs in `AGENTS.md` or
`REVIEW.md`.

**Never a second full copy.** Two files describing the same repo drift, and drift is the
conflicting-rules failure mode.

**Comments are free here, and only here.** Claude Code strips block-level HTML comments from
memory files before injection, so instructional comments in `CLAUDE.md` cost nothing at runtime
and may stay for the next maintainer. `AGENTS.md` and `REVIEW.md` get no such treatment — strip
theirs before shipping (§4).

**Verification.** `/context` lists memory files loaded at startup. It does not show nested files
or path-scoped rules, which load later; for those, register an `InstructionsLoaded` hook that
appends to a log file, and check the log after reading a file in the nested directory.

**How to write one:** the `claude-md` skill (`.dpe-agent-config/skills/claude-md/`) — the import
mechanics, what qualifies as Claude-only content, the nested pair, path-scoped rules, and worked
examples.

### 5.3 `REVIEW.md`

Justified by load timing: it is read when reviewing, not on every task, so it may be longer
than `AGENTS.md` without spending the startup budget. Under a review tool it spends a _different_
budget, which is shared and fails silently (see wiring below).

It must contain **detectable failure conditions specific to this repo**. A bullet that would read
identically in any repo ("check for SQL injection", "ensure tests are added") is generic advice —
delete it. Every bullet should be traceable to something that has actually broken, or plausibly
can break, in _this_ codebase.

**Only two sections: `## What to flag`, `## What not to flag`.** Nothing else — `verification.sh
lint` enforces the heading list exactly, the same way it enforces `AGENTS.md`'s. A finding's
one-line bullet (condition, severity, consequence) is what the reviewer needs; the incident that
proves it — the exact error string, the metric name, the percentile distribution that sized a
threshold — is not review-time content, and inlining it (a `## Lessons` or `## Background`
section, a numbered evidence appendix) counts against the reviewer's shared byte budget on every
PR regardless of whether that PR touches the relevant code at all. Route that evidence to a
skill instead: it triggers only when its file pattern matches, which is also _earlier_ — an
agent that reads it while writing the change catches the mistake before a diff exists, not after.

This is not hypothetical: a real `REVIEW.md` grew a `## Lessons (the evidence behind the flags)`
section, one paragraph per numbered finding, cited from the bullets above as `(§N)`. Of its
twelve lessons, one genuinely duplicated its bullet's actionable content (drop it or fold the one
useful detail into the bullet itself); the rest added real incident evidence the bullets couldn't
hold at one line, and two carried guidance with no bullet at all (a CLI workflow for replaying a
monitor's own evaluation against history; a cross-repo dependency note). All of it belongs in a
skill — keep the bullet's `(§N)` citation, point it at the skill's own numbering instead.

**Review style lives in one place, and it is not this file.** Comment shape, summary shape,
the severity vocabulary, the hedging table, and the nit cap are identical in every repo. They
live in `review-standard.md` — one file, one copy — and reach the reviewer by being listed
**first** in every repo's document config. They are _not_ reached via `~/.claude/CLAUDE.md` or
org settings: an automated reviewer runs as a separate service and reads only the documents its
own config names. Any repo `REVIEW.md` that restates them is a second copy to drift and a tax on
the shared budget. Lint fails on a `## How to write a review` heading in a repo `REVIEW.md`.

How `review-standard.md` is delivered: it lives in `dpe-agent-config/shared/docs/` and is vendored
into every repo as `.dpe-agent-config/docs/review-standard.md` by the release sync, then listed first
in that repo's document config. It is team-scoped by construction — no org-level reviewer baseline is
assumed. If the reviewer can read a document by URL, that is an acceptable alternative to
vendoring this one file; N hand-maintained inline copies is not.

**Severity vocabulary** — defined once here, restated once in `review-standard.md`, nowhere
else. Three tokens, each defined by what it means for the merge decision:

| Token       | Merge consequence                                                        |
| ----------- | ------------------------------------------------------------------------ |
| `blocking`  | Cannot be merged or approved until it is addressed.                      |
| `follow-up` | Does not hold this PR. Real and worth doing, in a later one.             |
| `nit`       | Never influences approval. Safe to ignore now. **At most 3 per review.** |

Some findings need work **outside** the PR, because the exposure already exists and merging the
fix does not undo it — a credential in a merged commit is in git history and in every clone. That
is an instruction, not a severity. Write it in the finding.

**State the token, in bold, inside each bullet** rather than grouping bullets under severity
headings. The three tokens are schema-validated by the review tool and map mechanically to the
review event; "high severity", "P1" and "error" map to nothing.

**Wiring.** If a tooling integration consumes `REVIEW.md`, these fail silently and must be
checked on a real PR (verified 2026-08-31 against `webflow/reviewflow` @ 1d9e193 — if the repo
uses a different reviewer, find that tool's equivalent of "which docs does the reviewer read"):

- `REVIEW.md` is **not** in the default document list. Unlisted, it never reaches the reviewer.
- Paths are matched **literally**. A glob matches nothing.
- The listed documents share a byte budget (default 30,720) and the loader skips a whole file
  rather than truncating it. Order: `review-standard.md`, `REVIEW.md`, `AGENTS.md`. Drop docs
  with no review value (a long operator README).
- The reviewer is not a linter: a stated severity is prompt-driven, and a changes-requested
  review does not itself block merge. A policy that must never be missed also gets a CI check.

**How to write one:** the `review-md` skill (`.dpe-agent-config/skills/review-md/`) — the two
tests, how to source failure modes, where evidence goes instead, the full wiring procedure, and
the template the file starts from.

### 5.4 Enforcement — the deterministic layers

Markdown instructions about commands fail twice: they spend the global instruction budget for an
occasionally-relevant rule, and they only _reduce the probability_ of a violation.

Enforcement replaces probability with code. Layers, ordered by who they reach. A must-hold rule
gets the highest layer that can express it; an agent hook is added on top when the early denial
is worth it.

| Layer                                                                                                                                                                                                                                                                                                | Reaches                                 | Expresses                                                                                                                                                                                                                                                                   |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| IAM, branch protection, CODEOWNERS, required checks                                                                                                                                                                                                                                                  | Everyone, every tool, every clone       | Access. Read-only credentials for agent profiles. No direct push to `main`. Human approval before deploy.                                                                                                                                                                   |
| git hooks (`commit-msg`, `pre-commit`, `pre-push`) managed by lefthook; the rules and scripts live in `.dpe-agent-config/lefthook.yml` and `.dpe-agent-config/hooks/git/` (vendored, whole-directory checksummed), extended by the consumer's own root `lefthook.yml`, **plus** the same check in CI | Every agent and every human who commits | Artefact rules. Commit message format, branch naming, lint, formatting, generated files in sync. CI is the backstop for `--no-verify`.                                                                                                                                      |
| Agent `PreToolUse` (or other event) hook — a named module in the catalog, registered by name in `.claude/settings.json` and `.codex/hooks.json`                                                                                                                                                      | Claude Code and Codex sessions          | The same rule again, at the tool call, so the agent is corrected before it wastes a cycle. Also the only place to express "no `npm`, use `pnpm`" style tool-choice rules that never reach a commit. Codex skips a new or changed hook until the user trusts it in `/hooks`. |

**Lint and style belong in the git-hook layer, not the agent-hook layer.** A real prior version
of this (`druid`'s `require-lint-pass.sh`/`check-style.sh`) lived as Claude-Code-only agent
hooks — no Codex coverage, no human coverage, because an agent hook only ever reaches an agent
session. Lint failures are exactly the "must hold for every agent AND every human" case the
table above already routes to git hooks + CI. Unlike `commit-msg`/`branch-name`, there is no one
vendored script for this: the actual tooling (`npm run lint`, `prettier`, something else
entirely) isn't fleet-uniform, so it's a documented pattern each repo wires into its own root
`lefthook.yml`, not a script shipped from `.dpe-agent-config/`:

```yaml
pre-commit:
  commands:
    lint:
      run: npm run lint_ci # or whatever this repo's real lint/format check invokes
```

`lint_ci` (a check-only variant, not the `--write`/autofix one) so the hook never mutates files
on its own — the same reasoning `druid`'s original script already applied.

**Catalog, not policy.** Central ships a _catalog_ of hooks under
`.dpe-agent-config/hooks/agent/`, one Python module per hook. Each module is the one
source of truth for that hook — it declares its own metadata and its own logic, nothing else
holds either:

```python
NAME = "aws-readonly"                    # the name a registration file's command line ends in
EVENT = "PreToolUse:Bash"                 # or "InstructionsLoaded", etc. — event[:matcher]
DESCRIPTION = "Blocks aws/pulumi calls that don't name a read-only AWS profile (dev or prod)."
MANDATORY = True                          # must be registered in every consumer; lint enforces it

def rule(event, cfg, root) -> Decision:
    ...
```

`run list` and the generated `CATALOG.md` are both rendered from this metadata — never
maintained separately. A consumer **registers a hook by listing it**, one line per hook, by
name: not listed = not running. There is no separate on/off switch in `config.env`; the
registration file _is_ the selection. A consumer can add a genuinely repo-specific hook the same
way, as `.agents/rules/<name>.py` with the same four-attribute contract plus its own test file —
the launcher resolves the central catalog first, then `.agents/rules/`.

**One launcher, two registrations, both consumer-owned.** Both tools hand the hook the tool call
as JSON on stdin (`tool_input.command` for a shell hook) and treat exit code 2 with a reason on
stderr as a block, so the script is written once: `.dpe-agent-config/hooks/agent/run <name>` runs the
named hook, resolving it from the catalog or `.agents/rules/`. Unlike the registration files
below, this launcher itself — like the rest of `.dpe-agent-config/` — is vendored and
whole-directory checksummed; only _which names_ appear in the two files below is the consumer's
choice, never synced over.

Claude Code, `.claude/settings.json` (consumer-owned; a starter copy comes from
`.dpe-agent-config/templates/`, written by `verification.sh init` only if the file is absent):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "$CLAUDE_PROJECT_DIR/.dpe-agent-config/hooks/agent/run aws-readonly" },
          { "type": "command", "command": "$CLAUDE_PROJECT_DIR/.dpe-agent-config/hooks/agent/run infra-readonly" },
          { "type": "command", "command": "$CLAUDE_PROJECT_DIR/.dpe-agent-config/hooks/agent/run block-rm" }
        ]
      }
    ]
  }
}
```

Codex, `.codex/hooks.json` — same shape, git-root path because Codex may be started in a
subdirectory (also consumer-owned):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$(git rev-parse --show-toplevel)/.dpe-agent-config/hooks/agent/run\" aws-readonly"
          },
          {
            "type": "command",
            "command": "bash \"$(git rev-parse --show-toplevel)/.dpe-agent-config/hooks/agent/run\" infra-readonly"
          },
          {
            "type": "command",
            "command": "bash \"$(git rev-parse --show-toplevel)/.dpe-agent-config/hooks/agent/run\" block-rm"
          }
        ]
      }
    ]
  }
}
```

The hook receives the tool call as JSON on stdin and controls execution by exit code:
**0** proceeds, **2** blocks and feeds stderr back to the agent as a correction.

**The denial message is the documentation.** Write it so the agent gets the correct form on the
retry. A hook with a good message needs no prose in `CLAUDE.md`.

**Test hooks like code.** `.dpe-agent-config/hooks/agent/test-hooks.sh` feeds sample tool calls
through every hook and asserts the exit code. A hook that silently allows is worse than no hook,
because the prose it replaced is gone.

**Implementation rules for agent hooks.**

- **Python 3, stdlib only, one package.** `shared/hooks/agent/` — the catalog modules
  sit directly in it, one per rule, alongside the shared `helpers/` (event parsing, the
  tokenizer, the fail-open/closed dispatch). Not bash: shell-command parsing (`a && npm i`,
  `bash -c "npm i"`, `env X=1 npm`, `echo "npm"`) needs a real tokeniser, `jq` is a dependency
  every machine must have, and bash does not run natively on Windows. Python's `json` and
  `shlex` are stdlib; Codex's own examples invoke `python3`; startup cost is ~40 ms per tool call.
- **One launcher, one process per tool call.** `.dpe-agent-config/hooks/agent/run <name>`
  resolves and runs the named hook; both registration files call it. Hooks share the event
  parser and the command splitter.
- **Registration is the mandatory/optional contract, enforced by `lint`.** Every `MANDATORY`
  catalog entry must be registered, on its declared event, in _both_ registration files — checked
  by `run check-registration`, shelled out to by `verification.sh lint`, not reimplemented as
  bash JSON-parsing. Every registered name must resolve, whether central or local. Optional
  hooks (`log-instructions`) are the consumer's choice, made by listing them or not.
- **Fail-closed for safety, fail-open for convenience — independent of `MANDATORY`.** If the
  event cannot be parsed, `aws-readonly` and `infra-readonly` deny; `log-instructions` allows.
  This is a runtime robustness question, not a registration one, so it is a separate, explicit
  set in `policy.py` — kept in sync by hand as hooks are added, tested.
- **Log every denial** to `.agents/.log/denials.jsonl` (timestamp, rule, command); `run stats`
  summarises it. This is how false positives are found in the first weeks, and it is the
  evidence for the rollout report.
- **Tests in the central repo, run on every push:** `pytest` table-driven cases per rule, the
  tokeniser tested hardest, a contract test that feeds one real Claude Code event and one real
  Codex event through the launcher and asserts exit code and stderr, and a registration test that
  the catalog integrity check and `check-registration` correctly flag a missing mandatory hook or
  an unresolved name. `ruff` and `mypy --strict` gate merges. CI also fails if `CATALOG.md` is
  stale relative to the modules' own metadata. `test-hooks.sh` in the consumer is a thin wrapper
  that runs the same suite.
- **Denial message names the fix.** The message is the documentation (§5.2).

### 5.5 Skills

The destination for legitimate steering that is not globally relevant — subsystem conventions,
a deploy runbook, a testing pattern. Discovered and loaded when their trigger matches, so they
cost nothing at startup. If a rule is real but fails the "every task" test, a skill is usually
the right home, not a nested markdown file. Note the audience: Claude Code reads
`.claude/skills/`, Codex reads `.agents/skills/`; both use the same `SKILL.md` format, so a
shared skill is one directory linked or copied into both paths. Optional skills are distributed
through the `dpe-acrana` plugin (dual-host: Claude marketplace plus a `.codex-plugin/`
manifest); enforcement is never distributed as a plugin because plugins are per-user.

**Three tiers of skill, and only the first is central.**

1. **Fleet standards** — `agents-md`, `claude-md`, `review-md`. These _are_ the standard's own
   procedures, so they ship the way every other enforcement artefact ships: vendored under
   `.dpe-agent-config/skills/`, whole-directory checksummed, changed only upstream. A consumer
   registers each one by a **stub** at `.claude/skills/<n>/SKILL.md` and `.agents/skills/<n>/SKILL.md`
   — frontmatter plus a pointer at the vendored file, written by `verification.sh stubs` and
   checked by `lint`, exactly as hook registration works (§5.4). Stub files are consumer-owned so
   a sync never touches them; their _content_ is generated, and lint fails when it drifts from
   the skill it points at, because the description is the trigger and a drifted description is a
   skill that silently stops firing.
2. **Optional shared skills** — distributed through the `dpe-acrana` plugin (dual-host: Claude
   marketplace plus a `.codex-plugin/` manifest), per-user install. Enforcement is never
   distributed this way, because plugins are per-user and a standard that only some people have
   installed is not a standard.
3. **Repo-local skills** — a normal consumer-owned file, same tier as a repo-specific
   `.agents/rules/<name>.py` hook, never vendored. This is the destination for a review finding's
   evidence (the incident, the exact error, the data) once its one-line bullet moves to
   `REVIEW.md` — see §5.3.

**Why a stub rather than the skill itself.** A stub is a pointer, and by the rule above a file an
agent is merely _told to read_ does not automatically bind. That is why the stub carries the two
admission tests inline rather than only a path: if a tool treats the pointer as data, the rules
that must hold are already in the loaded text, and only the procedure is behind the hop. Whether
each tool follows the pointer is a measured question, not an assumed one.

---

## 5.6 Distribution — where shared files live and how they reach a repo

Team-scoped. Nothing here uses managed settings, MDM, or org-level reviewer configuration.

| Artefact                                                                                                                                                                      | Source of truth                                                                                                                         | In each consumer repo                                                                         | Delivered by                                                                                              |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `md-standards.md`, `review-standard.md`                                                                                                                                       | `dpe-agent-config/shared/docs/`                                                                                                         | `.dpe-agent-config/docs/`                                                                     | release sync PR on every tag                                                                              |
| hook catalog (`hooks/agent/*.py`, each declaring `NAME`/`EVENT`/`DESCRIPTION`/`MANDATORY`), `test-hooks.sh`, `verification.sh`, git-hook scripts, the vendored `lefthook.yml` | `dpe-agent-config/shared/`                                                                                                              | `.dpe-agent-config/` (whole directory; `VERSION` + `CHECKSUM` cover all of it, no exclusions) | release sync PR on every tag                                                                              |
| fleet-standard skills (`skills/{agents-md,claude-md,review-md}/`, each a `SKILL.md` plus a `template.md`)                                                                     | `dpe-agent-config/shared/skills/`                                                                                                       | `.dpe-agent-config/skills/`                                                                   | release sync PR on every tag (part of the whole-directory copy above)                                     |
| `.claude/settings.json`, `.codex/hooks.json`, root `lefthook.yml`, `.claude/CLAUDE.md`                                                                                        | consumer repo, starter copy from `dpe-agent-config/shared/templates/` (`.claude/CLAUDE.md` is written inline — it is three fixed lines) | same paths, **consumer-owned**                                                                | human, via `verification.sh init` once (writes only when the file is absent); a sync never touches these  |
| skill stubs at `.claude/skills/<n>/SKILL.md` and `.agents/skills/<n>/SKILL.md`                                                                                                | generated from the vendored skill's own frontmatter                                                                                     | same paths, **consumer-owned**                                                                | `verification.sh stubs` (the one command that overwrites); `lint` fails when a stub is missing or drifted |
| `AGENTS.md`, `REVIEW.md`                                                                                                                                                      | the consumer repo — nothing central to copy                                                                                             | same paths, **consumer-owned**                                                                | an agent, via the `agents-md` / `review-md` skills. `init` deliberately does not write them               |
| Repo-wide `CODEOWNERS` owner, plus a line for the vendored directory                                                                                                          | `dpe-agent-config/shared/CODEOWNERS.snippet`                                                                                            | prepended and appended in `.github/CODEOWNERS`                                                | `verification.sh init`, once                                                                              |
| optional skills, commands, subagents                                                                                                                                          | `dpe-acrana` (dual-host plugin)                                                                                                         | not in the repo                                                                               | per-user plugin install                                                                                   |
| `.agents/config.env`, `.agents/rules/<name>.py` (+ its test)                                                                                                                  | the consumer repo                                                                                                                       | `.agents/` — never central-owned, never synced                                                | human                                                                                                     |

Rules:

- **Vendor, do not reference.** The reviewer, both agents, and CI read the working tree.
  Submodules and remote URLs are not checked out by default and fail silently.
- **Central writes `.dpe-agent-config/` only.** A sync PR never touches `.claude/settings.json`,
  `.codex/hooks.json`, root `lefthook.yml`, `AGENTS.md`, or `REVIEW.md` — the failure mode this
  design avoids is exactly what happened when those _were_ synced: a consumer's own
  `.gitignore` (a blanket `.claude/` entry, say) silently dropped `.claude/settings.json` from a
  sync PR with no error anywhere. Central instead _verifies_ the contract on them
  (`verification.sh lint`, shelling out to the vendored `run check-registration`): every
  `MANDATORY` catalog hook registered on its declared event in both registration files, every
  registered name resolving (a catalog entry or a `.agents/rules/<name>.py` with its own test
  file), every vendored skill carrying a matching stub in both `.claude/skills/` and
  `.agents/skills/`, root `lefthook.yml` containing `extends: [.dpe-agent-config/lefthook.yml]`. A
  consumer that breaks the contract gets a red required check naming the exact missing line, and
  the repair is a command they run (`verification.sh stubs`), never a central edit.
- **`.dpe-agent-config/` has no consumer-owned exception.** Because nothing consumer-owned lives
  inside it any more, `CHECKSUM` covers the whole directory (only itself and build-cache
  directories excluded — a file cannot include its own hash, and a stray local `pytest`/`mypy`
  run should not trip drift). `verification.sh drift` fails CI on any local change, full stop.
  `CODEOWNERS` routes any attempt to the owning team, which owns the repository. Consumer-owned
  agent material — `config.env`, `rules/` (+ tests), the Codex skill stubs — lives in `.agents/`,
  entirely outside the vendored tree, so it needs no carve-out.

  The stubs are the one thing that is consumer-owned _and_ content-checked, and they sit outside
  the checksum by construction. `drift` cannot see them; `lint` is the only thing that can, which
  is why it compares their bytes rather than merely asserting the files exist.

- **The Codex re-trust warning applies less often now.** Codex records trust against a hook's
  hash and skips a changed hook silently until re-trusted. Because `.codex/hooks.json` is
  consumer-owned and a routine release only changes hook _logic_ inside `.dpe-agent-config/`,
  most releases never touch the registration file Codex actually hashes — only a consumer's own
  edit to `.codex/hooks.json` should trigger the gate. Verify this holds in practice before
  relying on it (Stage 3, `iterate-1.md` I4).
- **Cross-repo PRs need a token beyond `GITHUB_TOKEN`.** A team-owned GitHub App with
  contents and pull-request write on the consumer repos; a fine-grained PAT only for tests.

---

## 6. Procedure — writing a new set

The procedure itself lives in the skills, which load when writing a context file is the task:
`skills/agents-md/` (inventory, routing, the section-by-section guide, the four-signal `## Traps`
sourcing procedure, the caps), `skills/review-md/`, `skills/claude-md/`. Each ships worked
template each file starts from — the same skeletons that used to live in `shared/templates/`,
now sitting beside the instructions instead of carrying them in comments that had to be deleted
before shipping.

What the procedure must produce, and what this file holds you to:

1. **No generator output shipped unedited.** `/init` (Claude Code, `CLAUDE_CODE_NEW_INIT=1`) is
   acceptable as a _fact inventory_; its default is comprehensiveness, which is the opposite of
   this standard. Route its proposal through §3 line by line like any other candidate.
2. **An inventory step that reaches outside the source tree** — existing docs, git log,
   `TODO`/`WARNING`/`HACK` comments, incident notes, the questions asked in review. Skipping this
   and then concluding the repo has no traps is the common failure.
3. **A destination for every candidate**, per §3, with the enforcement _layer_ named. "Agent
   hook" alone is not a finished destination.
4. **`AGENTS.md` written from the survivors only**, within the caps (§5.1).
5. **Every enforcement rule implemented in its layer**, with a test. Hook modules go in
   `dpe-agent-config/shared/hooks/agent/`, never directly in a consumer repo.
6. **`REVIEW.md` from the failure-mode inventory** (§5.3), and **`.claude/CLAUDE.md`** as the
   import plus at most a handful of Claude-only lines (§5.2).
7. **Loading verified**: `/context` for the root, an `InstructionsLoaded` log for anything nested
   or path-scoped, a real PR for `REVIEW.md`, `./verification.sh probe` for obedience.
8. **`./verification.sh lint` clean.**

## 7. Procedure — migrating an existing file

Also in `skills/agents-md/`. The rule this file holds you to: shrinking a context file is only
safe if nothing is silently lost, so the migration produces a **written accounting** — every
dropped line with its destination (`→ git hook + CI`, `→ IAM`, `→ agent hook (early signal)`,
`→ skill`, `→ README`, `→ nested pair`, `→ rule`, or `→ dropped: discoverable`), kept in the repo
as a `MIGRATION.md` or a PR comment.

Facts that are genuinely not derivable from source — account IDs, environment mappings, protected
resources, cross-repo coupling, known traps — must each appear in that accounting with a real
destination. "Dropped: discoverable" is not acceptable for any of them, and that is the one
failure here that is both silent and unrecoverable.

## 8. Acceptance checklist

Apply per line. A line ships only if every answer is the good one.

- [ ] Could the agent discover this by reading the repo? → must be **no**
- [ ] Is it needed on nearly every task in this repo? → must be **yes**
- [ ] Does it name a literal file path **as an assertion about where code lives**? → must be
      **no**. A link to a document that exists for the agent to open is a pointer, not an
      assertion — that is the progressive-disclosure mechanism (§5.1), and it fails loudly
      rather than silently misleading.
- [ ] Does it duplicate `package.json`, `Makefile`, `pyproject.toml`, or CI config? → must be **no**
- [ ] Does it duplicate a user-scope, org-scope, or `review-standard.md` rule? → must be **no**
      (reference instead)
- [ ] Is it an "always/never" rule about a command or an artefact? → must be **no** (enforce it
      in a layer every agent hits — §5.4)
- [ ] Does it contradict another line in the same file, or in a merged file? → must be **no**
- [ ] Would deleting it change any agent behaviour? → must be **yes**

And per file:

- [ ] `AGENTS.md` prose is under ~40 lines, and its traps list is under ~8 bullets
- [ ] `AGENTS.md` and `REVIEW.md` contain no HTML comments
- [ ] No reference chain is more than one hop deep — flat disclosure, not a tree
- [ ] Section names and order match §5.1; the three required ones are present
- [ ] `./.claude/CLAUDE.md` exists, `./CLAUDE.md` does not, and the former opens with a bare
      `@../AGENTS.md` on its own line that resolves to an existing file
- [ ] Every nested instruction directory has both `AGENTS.md` and a `CLAUDE.md` containing
      `@AGENTS.md`
- [ ] Every `REVIEW.md` bullet names a failure mode specific to this repo, carries a bold
      severity token, and the file has no review-style section
- [ ] Every enforcement rule exists in a layer every agent hits, or the gap is recorded in
      `## Enforced automatically`
- [ ] Every vendored skill has a matching stub in both `.claude/skills/` and `.agents/skills/`
      (`verification.sh stubs` writes them; `lint` fails when one is missing or drifted)
- [ ] Every `MANDATORY` catalog hook is registered by name, on its event, in both
      `.claude/settings.json` and `.codex/hooks.json` (`run check-registration`); every local
      `.agents/rules/<name>.py` has a test in `.agents/rules/tests/`
- [ ] `.dpe-agent-config/` matches `.dpe-agent-config/CHECKSUM` (`verification.sh drift`) —
      nothing edited locally
- [ ] Loading was verified: `/context`, an `InstructionsLoaded` log for nested/rules, a real PR
      for `REVIEW.md`
- [ ] A migration accounting exists for anything removed
