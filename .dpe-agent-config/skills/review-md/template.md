# Code Review Guidelines — [repo name]

[One sentence: what this repo is, and what a reviewer is therefore mainly protecting.
Example: "Pulumi IaC for a stateful Druid cluster — the main risk is a change that forces
resource replacement and destroys segment metadata."]

Style, severity tokens, and summary shape follow `.dpe-agent-config/docs/review-standard.md`.
This file lists only the failure modes specific to this repository.

## What to flag

- [Condition — **severity**. Consequence, if not obvious. (#PR where it bit.)]
- [One bullet per failure mode, ordered blocking → follow-up → nit.]

## What not to flag

- [Generated paths specific to this repo. Note which must stay out of ignoredFilePatterns
  because a rule above keys on them.]
- [Change shapes that are routine here — a release PR that only merges one branch into another,
  a version bump with no logic change.]
