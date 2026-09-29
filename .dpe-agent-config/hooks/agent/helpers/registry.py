from __future__ import annotations

import json
import os
import re
import shlex
from pathlib import Path

_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")

# Codex registers `bash "<abs path>/run" <name>`; Claude Code invokes the launcher directly.
_INTERPRETERS = {"bash", "sh"}

# The only substitutions the two tools' templates use. Anything else is left unresolved.
_ROOT_PREFIXES = (
    "$(git rev-parse --show-toplevel)/",
    "${CLAUDE_PROJECT_DIR}/",
    "$CLAUDE_PROJECT_DIR/",
)


def parse_command(command: str) -> tuple[str | None, str | None, str | None]:
    """Split a registered hook command into (launcher path, hook name, interpreter).

    The name is the last token; the launcher is what remains once an optional `bash`/`sh` is
    dropped. Any of the three is None rather than a guess when the shape isn't recognised, and
    the interpreter is kept because it decides whether the launcher's executable bit matters."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None, None, None
    if not tokens:
        return None, None, None

    candidate = tokens[-1]
    name = candidate if _NAME_PATTERN.fullmatch(candidate) else None

    head = tokens[:-1]
    interpreter = None
    if head and os.path.basename(head[0]) in _INTERPRETERS:
        interpreter = head[0]
        head = head[1:]
    launcher = head[0] if len(head) == 1 else None
    return launcher, name, interpreter


def launcher_problem(launcher: str | None, root: str,
                     interpreter: str | None = None) -> str | None:
    """Why this registration's launcher wouldn't run, or None if it's fine or unknowable.

    Only exit 2 blocks, so a launcher that has moved (127) or isn't executable (126) leaves the
    hook registered and nothing enforced; syncs replace the vendored directory but never the
    consumer-owned registration files (D10), which is how a launcher gets stranded.

    An unresolvable path returns None rather than a guess, since a false red across the fleet
    costs more than a missed edge."""
    if launcher is None:
        return None  # shape we don't recognise; don't guess
    # A relative launcher resolves against the SESSION's working directory, not the repo root, so
    # only the anchored form runs from a subdirectory. A `$` that is none of ours is a
    # substitution we cannot resolve, so it is left alone.
    if (not launcher.startswith(_ROOT_PREFIXES) and "$" not in launcher
            and not os.path.isabs(launcher)):
        return (f"launcher '{launcher}' is a relative path; it resolves against the session's "
                f"working directory. Prefix it with $CLAUDE_PROJECT_DIR/ (Claude Code) or "
                f"$(git rev-parse --show-toplevel)/ (Codex)")
    path = launcher
    for prefix in _ROOT_PREFIXES:
        if path.startswith(prefix):
            path = path[len(prefix) :]
            break
    if "$" in path:
        return None  # some other substitution; not ours to resolve
    resolved = Path(path) if os.path.isabs(path) else Path(root) / path
    if not resolved.is_file():
        return f"launcher '{launcher}' does not exist (would exit 127, which does not block)"
    # Only when the tool execs the file itself: Claude Code does, so a missing +x is a silent
    # 126, while Codex hands the file to bash, which reads it whatever its mode is.
    if interpreter is None and not os.access(resolved, os.X_OK):
        return f"launcher '{launcher}' is not executable (would exit 126, which does not block)"
    return None


def covers(key: str, declared: str) -> bool:
    """Does a registration key cover the event a catalog hook declares?

    Both tools accept a matcher broader than one tool name -- omitted or empty (every tool on
    that event), `*`, or a regex like `Bash|Edit` -- and any of those covers the declared tool.
    Broader counts, narrower does not: `Edit` never satisfies a hook declaring `Bash`.
    """
    key_event, _, key_matcher = key.partition(":")
    want_event, _, want_tool = declared.partition(":")
    if key_event != want_event:
        return False
    if not want_tool:
        # The hook declares no tool (InstructionsLoaded); only an equally unscoped
        # registration covers it.
        return not key_matcher or key_matcher == "*"
    if not key_matcher or key_matcher == "*":
        return True
    # Literal first, because both tools read a matcher as a name before anything else, and
    # because a hook may declare an alternation of its own (`PreToolUse:Edit|Write`).
    if key_matcher == want_tool:
        return True
    # `Bash|Edit` and `Bash, Edit` are name lists to the tools, not regexes.
    if any(part.strip() == want_tool for part in re.split(r"[|,]", key_matcher)):
        return True
    try:
        return re.fullmatch(key_matcher, want_tool) is not None
    except re.error:
        # Not a valid regex, so the tools would not match it either. The literal and list
        # comparisons above have already had their say.
        return False


def registered(path: Path) -> dict[str, dict[str, tuple[str | None, str | None]]]:
    """{"<event>[:<matcher>]": {name: (launcher, interpreter)}} registered in a Claude Code or
    Codex hooks-settings JSON file — both tools share the same `hooks` block shape.

    The interpreter rides along because whether the launcher's mode matters depends on it."""
    data = json.loads(path.read_text())
    out: dict[str, dict[str, tuple[str | None, str | None]]] = {}
    for event_name, groups in (data.get("hooks") or {}).items():
        for group in groups:
            matcher = group.get("matcher")
            key = f"{event_name}:{matcher}" if matcher else event_name
            names = out.setdefault(key, {})
            for h in group.get("hooks", []):
                launcher, name, interpreter = parse_command(h.get("command", ""))
                if name:
                    names[name] = (launcher, interpreter)
    return out


def extract_name(command: str) -> str | None:
    """The hook name alone."""
    return parse_command(command)[1]
