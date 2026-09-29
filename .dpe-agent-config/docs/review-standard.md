# Review standard

How to write a review. Identical for every repository; only the failure modes in each repo's
`REVIEW.md` are local. Source of truth for the severity vocabulary is `md-standards.md` §5.3;
this file restates it once because the reviewer reads this file and not that one.

This document lives in `dpe-agent-config/shared/docs/` and is vendored into every repository as
`.dpe-agent-config/docs/review-standard.md` by the release sync, then listed **first** in that
repository's document config. It is team-scoped; it is never copied into a repository's
`REVIEW.md` and never edited inside a consumer repository.

## Severity

Three tokens, defined by merge consequence. State the token in bold inside each finding.

| Token         | Merge consequence                                                        |
| ------------- | ------------------------------------------------------------------------ |
| **blocking**  | Cannot be merged or approved until it is addressed.                      |
| **follow-up** | Does not hold this PR. Real and worth doing, in a later one.             |
| **nit**       | Never influences approval. Safe to ignore now. At most three per review. |

Nothing else — "high", "P1", "important", "error" map to nothing.

Some findings need work outside the PR because the exposure already exists and merging the fix
does not undo it: a credential in a merged commit is in history and in every clone. That is an
instruction, not a severity. Put it in the finding:

> **blocking**: A live AWS key is committed in plaintext. Remove it, then rotate it and check
> CloudTrail for use — the fix does not undo the exposure.

More than three nits is a pattern, not three more nits. Raise it once as a single follow-up
naming the pattern, or drop it. Pick the three most worth the author's attention, not the first
three you noticed. Zero nits is a good review.

## Comments

Write for scanning. The reader is deciding whether to merge, not reading an essay.

**Shape:** `<token>: <problem>. <impact, only if not obvious>. <smallest reasonable fix>.`

One to three sentences, flat prose — no headings or sections inside a comment. One issue per
comment; consolidate findings that share a root cause instead of repeating them per line. Never
restate code the author can see. Never explain basic engineering concepts.

Hedged, padded, upbeat prose is the failure mode. Delete on sight:

| Do not write                                          | Write instead                     |
| ----------------------------------------------------- | --------------------------------- |
| "There appears to potentially be a scenario where..." | Name the scenario.                |
| "This could potentially cause issues."                | Name the issue.                   |
| "It's worth noting that..."                           | Just say the thing.               |
| "I'd recommend considering whether..."                | "Do X."                           |
| "Great catch!" / "Nice work!"                         | Nothing. Praise is not a finding. |
| A comment that only says the code looks good          | Post nothing.                     |
| Emoji, exclamation marks                              | Plain text.                       |

Hedging is not politeness — it makes the author guess whether you found a real problem. If you
are unsure, say so in four words and lower the severity.

**Good:**

> **blocking**: The rendered config under `components/druid/rendered/` was not regenerated
> after the input changed. What deploys will not match what was reviewed. Run the render and
> commit the output.

> **follow-up**: The retry wraps the whole batch, so one bad row re-sends the good ones.
> Retry per row.

> **nit**: `maxLowPct` — the property is `maxLowPercent`; the typo is repeated three times.

**Bad** — the author still does not know what is wrong:

> This might not be ideal and could lead to unexpected behaviour in some cases. Consider
> whether a different approach would be more aligned with best practices here.

## The summary

A merge decision, not a description of the PR. One or two sentences.

**Shape:** `<verdict> — <the single most important finding, if any>.` Omit the clause when
there are none.

Never state a count of findings — the reader can count, and a number is a second place to be
wrong. Never restate what the PR does. Never say what it did _not_ change ("X is untouched"
implies X was at risk). Never narrate the review or note whether earlier threads were addressed.
Never repeat a finding's detail — that is what the inline comment is for.

**Good:**

> **Blocking** — the rendered configs were not regenerated after the input change.

> **Looks good** — no findings.

**Bad:**

> The PR does what the description says: it adds X, moves Y, and reduces Z — all the review
> threads look properly addressed. The main problem is in the scoping itself...

## What never needs a comment

- Anything a git hook, CI job, IAM policy, or branch protection already rejects. If a change
  cannot reach `main` without it, it does not need a comment. Agent hooks do not count: they
  run only inside Claude Code and Codex sessions, so a rule they guard can still arrive from a
  human or another tool.
- Generated files, lock files, and vendored code, unless the repo's `REVIEW.md` names a
  condition that keys on them.
- Style that a formatter enforces.

Verify before blocking: a blocking finding you have not checked against the diff is a guess
with a badge on it.
