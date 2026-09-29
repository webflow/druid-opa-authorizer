from __future__ import annotations

from helpers import event as ev
from helpers.policy import ALLOW, Decision, deny
from helpers.shell import invocations, positionals

NAME = "infra-readonly"
EVENT = "PreToolUse:Bash"
DESCRIPTION = "Blocks pulumi commands that alter infrastructure or stack state."
MANDATORY = True

# `state` is denied as a whole verb because every one of its subcommands writes, which covers
# any a future release adds. `update` is pulumi's alias for `up`, and `import` writes state.
PULUMI_DENIED = {"up", "update", "destroy", "state", "watch", "cancel", "refresh", "import"}

# Denied only as these pairs.
PULUMI_DENIED_PAIRS = {
    ("stack", "rm"),
    ("stack", "import"),
    ("stack", "change-secrets-provider"),
}

# Flags taking the next argument as their value, so the verb stays findable by position --
# `pulumi --cwd infra up` otherwise reads as the verb "infra". Every global flag pulumi takes a
# value for belongs here, since one omission hides the verb and lets the command through.
PULUMI_VALUE_FLAGS = {
    "--cwd", "-C",
    "--stack", "-s",
    "--config-file",
    "--color",
    "--profiling",
    "--tracing",
    "--tracing-header",
    "--verbose", "-v",
    "--memprofilerate",
}
# Boolean globals (--logtostderr, --logflow, --non-interactive, --emoji) are deliberately absent:
# one listed here would consume the verb as its value.

def _subcommand(args: list[str], value_flags: frozenset[str] | set[str]) -> tuple[str, str]:
    """The verb and subverb, flags dropped. `--cwd infra state delete` -> ("state", "delete")."""
    words = positionals(args, value_flags)
    padded = (words + ["", ""])[:2]
    return padded[0], padded[1]


def rule(event: ev.Event, cfg: dict[str, str], root: str) -> Decision:
    del cfg, root
    for inv in invocations(event.command):
        if inv.program == "pulumi":
            if "--help" in inv.args or "-h" in inv.args:
                continue          # help text runs nothing
            verb, subverb = _subcommand(inv.args, PULUMI_VALUE_FLAGS)
            if verb in PULUMI_DENIED:
                return deny(f"Blocked: 'pulumi {verb}' alters real infrastructure or stack "
                            "state. Open a PR (AGENTS.md → What a merge reaches).")
            if (verb, subverb) in PULUMI_DENIED_PAIRS:
                return deny(f"Blocked: 'pulumi {verb} {subverb}' alters stack state. Open a PR "
                            "(AGENTS.md → What a merge reaches).")
    return ALLOW
