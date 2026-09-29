from __future__ import annotations

from helpers import event as ev
from helpers.policy import ALLOW, Decision, deny
from helpers.shell import Invocation, invocations

NAME = "aws-readonly"
EVENT = "PreToolUse:Bash"
DESCRIPTION = "Blocks aws/pulumi calls that don't name a read-only AWS profile (dev or prod)."
MANDATORY = True

ALLOWED_PROFILES = {"date-dev-read-only", "date-read-only"}

# Deliberately blind to the verb: IAM decides what a read-only profile may do. A verb denylist
# would have to track every operation AWS adds, and each gap would read as a guarantee.

# pulumi resolves the profile from AWS_PROFILE, with no CLI flag, so it is checked here too.
CREDENTIAL_PROGRAMS = {"aws", "pulumi"}

# Environment variables that outrank a profile name: the first three are credentials botocore
# prefers outright, the rest redirect where the profile is read from. Any of them present means
# the name this hook checked is not what the call will authenticate with.
CREDENTIAL_ENV_VARS = {
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_SHARED_CREDENTIALS_FILE",
    "AWS_CONFIG_FILE",
    "AWS_WEB_IDENTITY_TOKEN_FILE",
    "AWS_CONTAINER_CREDENTIALS_FULL_URI",
    "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
}


def _profiles_named(inv: Invocation) -> set[str]:
    """Every profile this one invocation names, via flag or environment."""
    found: set[str] = set()

    if "AWS_PROFILE" in inv.env:
        found.add(inv.env["AWS_PROFILE"])

    args = inv.args
    for i, a in enumerate(args):
        if a == "--profile" and i + 1 < len(args):
            found.add(args[i + 1])
        elif a.startswith("--profile="):
            found.add(a.split("=", 1)[1])

    return found


def rule(event: ev.Event, cfg: dict[str, str], root: str) -> Decision:
    del cfg, root
    allowed = " ".join(sorted(ALLOWED_PROFILES))

    # Per invocation, so an approved profile in front cannot launder the one behind it.
    for inv in invocations(event.command):
        if inv.program not in CREDENTIAL_PROGRAMS:
            continue
        if "--help" in inv.args or "-h" in inv.args:
            continue

        overridden = sorted(CREDENTIAL_ENV_VARS & set(inv.env))
        if overridden:
            return deny(f"Blocked: '{inv.program}' is given credentials directly via "
                        f"{', '.join(overridden)}, which outranks any profile name. Name an "
                        f"allowed profile instead: {allowed} (AGENTS.md \u2192 AWS access).")

        named = _profiles_named(inv)
        if not named:
            return deny(f"Blocked: '{inv.program}' uses AWS credentials but names no profile. "
                        f"Allowed: {allowed} (AGENTS.md → AWS access).")
        for profile in sorted(named - ALLOWED_PROFILES):
            return deny(f"Blocked: profile '{profile}' is not allowed. Allowed: {allowed} "
                        f"(AGENTS.md → AWS access).")
    return ALLOW
