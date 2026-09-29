"""block-rm -- `rm -rf` is blocked outright, whatever the target.

No path allowlist: judging a target safe means resolving globs, symlinks and relative paths
exactly as the shell will, and being wrong once costs a repository.

Only catches a literal `rm`. A script or a language's own recursive delete goes unseen.
"""

from __future__ import annotations

from helpers import event as ev
from helpers.policy import ALLOW, Decision, deny
from helpers.shell import invocations

NAME = "block-rm"
EVENT = "PreToolUse:Bash"
DESCRIPTION = "Blocks `rm -rf` (recursive and force together), whatever the target."
MANDATORY = True

RECURSIVE_LONG = "--recursive"
FORCE_LONG = "--force"


def _is_long(arg: str, full: str) -> bool:
    """GNU getopt_long accepts any unambiguous ABBREVIATION of a long option, so `rm --rec --for`
    deletes recursively. Matching the full spelling only, `--rec` read as neither flag and the
    command was allowed -- verified against GNU coreutils rm, which deleted the tree.

    `len(arg) > 2` keeps a bare `--` out. Treating an ambiguous prefix as a match over-blocks,
    which is the direction to be wrong in."""
    return len(arg) > 2 and full.startswith(arg)


def _recursive_and_force(args: list[str]) -> bool:
    """Both recursion and force, however spelled: `-rf`, `-fr`, `-r -f`, `-Rf`, `--recursive
    --force`. Matching the literal "-rf" would miss most of them."""
    recursive = force = False
    for arg in args:
        if arg == "--":
            break
        if arg.startswith("--"):
            recursive = recursive or _is_long(arg, RECURSIVE_LONG)
            force = force or _is_long(arg, FORCE_LONG)
        elif arg.startswith("-") and not arg.startswith("--") and len(arg) > 1:
            letters = set(arg[1:])
            recursive = recursive or bool(letters & {"r", "R"})
            force = force or "f" in letters
    return recursive and force


def rule(event: ev.Event, cfg: dict[str, str], root: str) -> Decision:
    del cfg, root
    for inv in invocations(event.command):
        if inv.program != "rm":
            continue
        if _recursive_and_force(inv.args):
            return deny("Blocked: 'rm -rf' is not something an agent session does. Delete it "
                        "yourself, or narrow the command (no -f, or one path at a time).")
    return ALLOW
