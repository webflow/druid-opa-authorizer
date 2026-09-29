from __future__ import annotations

import json
import os
import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass

from . import event as ev


@dataclass
class Decision:
    allow: bool
    reason: str = ""

ALLOW = Decision(True)

def deny(reason: str) -> Decision:
    return Decision(False, reason)

# Unparseable event: safety rules deny, convenience rules allow. Kept independent of catalog
# MANDATORY, which governs registration rather than parse-failure behavior; every catalog name
# must appear in exactly one set, which test_policy_sets_cover_the_catalog asserts.
FAIL_CLOSED = {"aws-readonly", "infra-readonly", "block-rm"}
FAIL_OPEN = {"log-instructions", "pr-body"}

def fallback(rule_name: str, why: str, root: str | None = None) -> Decision:
    """What to decide when the rule could not be reached at all.

    An unknown name -- a local rule in .agents/rules/, or a catalog hook nobody classified --
    denies, because only exit 2 blocks and anything else lets the command through unrecorded.

    The fail-open branch announces itself on stderr and in the log, since an allow is otherwise
    invisible and a rule that raises on every call would allow forever in silence.
    """
    if rule_name not in FAIL_OPEN:
        return deny(f"{rule_name}: {why}; refusing by policy.")
    print(f"{rule_name}: {why}; allowing (fail-open).", file=sys.stderr)
    if root is not None:
        log(root, rule_name, None, f"fail-open fallback: {why}", decision="allow")
    return ALLOW


def matcher(event: str) -> str:
    """The tool a hook's EVENT applies to.

    `PreToolUse:Bash` -> `Bash`; an event with no matcher (`InstructionsLoaded`) -> "".
    """
    return event.split(":", 1)[1] if ":" in event else ""


def applies_to(event: str, tool_name: str) -> bool:
    """Does a hook declaring this EVENT apply to the tool this call is for?

    Unscoped or `*` applies to everything; otherwise the matcher is a name, a `|`/`,` list of
    names, or a regex, exactly as a registration's `matcher` field may be. Kept deliberately in
    step with registry.covers(), which asks this of a registration rather than a declaration.
    """
    want = matcher(event)
    if not want or want == "*":
        return True
    if not tool_name:
        return True  # nothing to compare against: run the rule rather than skip it
    if want == tool_name or any(p.strip() == tool_name for p in re.split(r"[|,]", want)):
        return True
    try:
        return re.fullmatch(want, tool_name) is not None
    except re.error:
        return False


def run(
    rule_name: str,
    rule: Callable[[ev.Event, dict[str, str], str], Decision],
    e: ev.Event | None,
    cfg: dict[str, str],
    root: str,
    event: str,
) -> int:
    if e is None:
        d = fallback(rule_name, "could not parse the tool event", root)
    # The hook's OWN matcher: a rule declaring `PreToolUse:Write` has to run on Write, not on
    # whichever tool the launcher happens to be wired to.
    elif not applies_to(event, e.tool_name):
        d = ALLOW
    else:
        try:
            d = rule(e, cfg, root)
        except Exception as exc:  # noqa: BLE001 - any rule bug must not become exit 1
            d = fallback(rule_name, f"the rule raised {type(exc).__name__}: {exc}", root)
    if not d.allow:
        log(root, rule_name, e.command if e else None, d.reason)
        print(d.reason, file=sys.stderr)
        return 2
    return 0

def log(root: str, rule: str, command: str | None, reason: str, decision: str = "deny") -> None:
    """Append one decision to the log. `decision` separates a fail-open allow from a denial, so
    a hook that raises on every call does not read as denials for commands that in fact ran; rows
    predating the field have none and count as denials."""
    try:
        d = os.path.join(root, ".agents", ".log")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "denials.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                "rule": rule, "command": command, "reason": reason,
                                "decision": decision}) + "\n")
    except Exception:
        pass
