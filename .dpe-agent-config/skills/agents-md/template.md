# [repo-name]

[ONE sentence. What this repo is and what it produces. Not a paragraph, not a feature list.]

## Environments

| Env       | Account / cluster | Region   | Notes                                                                          |
| --------- | ----------------- | -------- | ------------------------------------------------------------------------------ |
| [sandbox] | [id]              | [region] | [what makes it different — cheaper instances, different arch, shared with dev] |
| [dev]     | [id]              | [region] |                                                                                |
| [prod]    | [id]              | [region] | [protected — say so]                                                           |

## Non-obvious commands

- Package manager: [only if not the language default — e.g. uv, pnpm]
- Test: [the ONE canonical invocation, only if it is not the obvious default — e.g.
  `pnpm test:ci`, not `mocha`.]
- [Any other invocation that cannot be guessed — e.g. "tests need PULUMI_NODEJS_STACK set; use
  the npm script rather than calling mocha directly". One line.]

## AWS access

- Agent sessions use the [`<profile-name>`] profile, which is read-only. Mutating calls are a
  human action.
- [How to assume it, if not obvious — e.g. `aws sso login --profile <n>` once per day.]

## What a merge reaches

- [What a merge reaches, and whether a human step stands between it and production.]
- [The class of failure that only appears at apply/deploy time. Cite where a green PR broke
  an environment.]
- [Any local command that is not blocked but still touches a live system.]

## Traps

- [Trap. Consequence.]

## Cross-repo coupling

- [`other-repo`] — [what this repo consumes from it, or hands to it]

## Enforced automatically

| Blocked                                                        | Why                                   | Where                                                         |
| -------------------------------------------------------------- | ------------------------------------- | ------------------------------------------------------------- |
| [commit message not matching `<JIRA-ID>: summary`]             | [changelog is generated from it]      | [git commit-msg hook + CI]                                    |
| [branch not matching `<JIRA-ID>-short-desc`]                   | [CI keys on it]                       | [git pre-push hook + CI]                                      |
| [a credentialed `aws`/`pulumi` call naming no allowed profile] | [agent sessions are read-only]        | [agent hook for early denial; IAM is what rejects the write]  |
| [mutating deploy commands]                                     | [deploys are a human action]          | [branch protection + required check; agent hook]              |
| [`rm -rf`]                                                     | [not something an agent session does] | [agent hook only (Claude Code, Codex) — humans are unguarded] |

## Further reading

- Setup, deployment, and runbooks — [README.md](README.md)
- Review conventions — [REVIEW.md](REVIEW.md)
- [Subsystem conventions] — [docs/<topic>.md]
- [`packages/<name>/` has its own `AGENTS.md`; Codex users should start sessions there.]
