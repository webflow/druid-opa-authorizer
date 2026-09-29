"""pr-body -- checks a `gh pr create`/`gh pr edit` body against the fleet's PR structure.

Optional, and an agent-only rule by nature: a PR body is not an artefact a git hook can see (it
does not exist at commit time) and it is edited on the web afterwards, so this catches the
common case -- an agent composing a body on the command line -- and nothing else. It is
guidance at the point of writing, not a gate.
"""

from __future__ import annotations

import os
import re
import subprocess

from helpers import event as ev
from helpers.policy import ALLOW, Decision, deny
from helpers.shell import invocations, positionals

NAME = "pr-body"
EVENT = "PreToolUse:Bash"
DESCRIPTION = "Checks a `gh pr create`/`edit` body for the required blocks and keeps it short."
MANDATORY = False

BODY_FLAGS = {"--body", "-b"}
BODY_FILE_FLAGS = {"--body-file", "-F"}

KNOWN_BLOCKS = ("Changes", "Background", "TODOs")

# The limits are the point of this hook: a body can be structurally correct and three times too
# long. Length is the part of "not an inventory of the diff" a rule can measure, and the denial
# message carries the rest.
MAX_CHANGES_BULLETS = 4
MAX_LINE = 100
MAX_BACKGROUND_SENTENCES = 4
# ~5x a well-written body: loose enough that a legitimately busy PR passes, tight enough to
# catch an essay.
MAX_BODY_CHARS = 1200

SENTENCE_END = re.compile(r"[.!?](?:\s|$)")

# A block label is a bold line on its own -- `**Changes**`. Letters and spaces only, so inline
# bold in a sentence (`**Model (D8):** ...`) is prose, not a malformed block.
BLOCK_RE = re.compile(r"^\*\*([A-Za-z][A-Za-z ]*)\*\*[ \t]*$", re.MULTILINE)
TICKET_RE = re.compile(
    r"https?://[A-Za-z0-9.-]+\.atlassian\.net/browse/([A-Za-z]+-[0-9]+)"
    r"|https?://linear\.app/[A-Za-z0-9_-]+/issue/([A-Za-z]+-[0-9]+)")
CHECKLIST_RE = re.compile(r"^[ \t]*[-*] \[[ xX]\]", re.MULTILINE)
ATTRIBUTION_RE = re.compile(r"generated with .*claude|co-authored-by: *claude|🤖 generated",
                            re.IGNORECASE)


def _blocks(body: str) -> dict[str, str]:
    """Each bold label mapped to the text under it, up to the next label."""
    found: dict[str, str] = {}
    marks = list(BLOCK_RE.finditer(body))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        found[m.group(1)] = body[m.end():end].strip()
    return found


def _findings(body: str, branch: str) -> list[str]:
    out: list[str] = []
    tickets = [a or b for a, b in TICKET_RE.findall(body)]
    if not tickets:
        out.append("no ticket link. Link the Jira or Linear issue: "
                   "[Ticket](https://<org>.atlassian.net/browse/ABC-123)")
    else:
        # Where the branch is <TICKET>-short-desc the body must link that ticket -- the same
        # anti-drift check commit-msg.sh makes on a commit message.
        on_branch = re.match(r"^([A-Za-z]+-[0-9]+)", branch)
        if on_branch and on_branch.group(1).upper() not in {t.upper() for t in tickets}:
            out.append(f"the branch is '{on_branch.group(1)}' but the body links "
                       f"{', '.join(tickets)} -- link the branch's ticket.")

    blocks = _blocks(body)
    if "Changes" not in blocks:
        out.append("no '**Changes**' block. State what was done, one short line per change.")
    elif not blocks["Changes"]:
        out.append("'**Changes**' is empty.")

    for name in ("Background", "TODOs"):
        if name in blocks and not blocks[name]:
            out.append(f"'**{name}**' is present but empty. Fill it or remove the block.")
    if blocks.get("TODOs") and not CHECKLIST_RE.search(blocks["TODOs"]):
        out.append("'**TODOs**' must be a checklist: '- [ ] <test or validation step>'.")

    for name in blocks:
        if name not in KNOWN_BLOCKS:
            out.append(f"unknown block '**{name}**'. The PR body is a ticket link plus "
                       f"{', '.join(KNOWN_BLOCKS)}.")
    if ATTRIBUTION_RE.search(body):
        out.append("remove the AI attribution footer.")

    out.extend(_length_findings(body, blocks))
    return out


def _bullets(text: str) -> list[str]:
    """Top-level bullets, each with any wrapped continuation lines folded back in."""
    items: list[str] = []
    for line in text.splitlines():
        if re.match(r"^[ \t]*[-*] ", line):
            items.append(line.strip())
        elif line.strip() and items:
            items[-1] += " " + line.strip()      # a wrapped bullet is still one bullet
    return items


def _length_findings(body: str, blocks: dict[str, str]) -> list[str]:
    """The limits from the PR standard. Structure is easy to get right and easy to pad."""
    out: list[str] = []
    if len(body) > MAX_BODY_CHARS:
        out.append(f"the body is {len(body)} characters; keep it under {MAX_BODY_CHARS}. "
                   "State what was done -- the reviewer reads the diff for detail.")

    changes = _bullets(blocks.get("Changes", ""))
    if len(changes) > MAX_CHANGES_BULLETS:
        out.append(f"'**Changes**' has {len(changes)} bullets; {MAX_CHANGES_BULLETS} is the max. "
                   "It is not an inventory of the diff -- describe what is worth attention or "
                   "needs justifying, and let the reviewer read the rest.")
    for b in changes:
        if len(b) > MAX_LINE:
            out.append(f"a '**Changes**' bullet is {len(b)} characters and carries explanation: "
                       f"{b[:60]}... One line per bullet; the why goes in '**Background**'.")

    background = blocks.get("Background", "")
    sentences = len([s for s in SENTENCE_END.split(background) if s.strip()])
    if sentences > MAX_BACKGROUND_SENTENCES:
        out.append(f"'**Background**' is {sentences} sentences; "
                   f"{MAX_BACKGROUND_SENTENCES} is the max. Why, in general wording -- not a "
                   "narrative of what you tried.")

    for todo in _bullets(blocks.get("TODOs", "")):
        if len(todo) > MAX_LINE:
            out.append(f"a '**TODOs**' item is {len(todo)} characters. One short line each, "
                       "no justification -- reasons go in the PR thread.")
    return out


def _flag_value(args: list[str], names: set[str]) -> str | None:
    """The value of `--flag value` or `--flag=value`, whichever spelling was used."""
    for i, arg in enumerate(args):
        if arg in names and i + 1 < len(args):
            return args[i + 1]
        for name in names:
            if arg.startswith(name + "="):
                return arg[len(name) + 1:]
    return None


def _body(args: list[str], cwd: str) -> str | None:
    """The body text, whether given inline or by file.

    `--body-file` resolves against `cwd`, not the repo root, because that is where gh resolves
    it -- and an unreadable path reads as "no body", which skips the check entirely."""
    body = _flag_value(args, BODY_FLAGS)
    if body is not None:
        return body
    path = _flag_value(args, BODY_FILE_FLAGS)
    if path is None:
        return None
    try:
        with open(os.path.join(cwd, path), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def _branch(root: str) -> str:
    try:
        # `branch --show-current`, not `rev-parse --abbrev-ref HEAD`: the latter errors on an
        # unborn branch and the empty result silently skips the drift check.
        out = subprocess.run(["git", "branch", "--show-current"], cwd=root,
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip()
    except Exception:
        return ""


def rule(event: ev.Event, cfg: dict[str, str], root: str) -> Decision:
    del cfg
    # A `cd` earlier in the same chain moves the directory `--body-file` resolves against, and
    # event.cwd predates it. invocations() keeps the chain in order, so the last cd is knowable.
    cwd = event.cwd or root
    for inv in invocations(event.command):
        if inv.program == "cd":
            target = inv.args[0] if inv.args else ""
            # A bare `cd` goes home and `cd -` goes back; neither is resolvable from here.
            if target and not target.startswith("-"):
                cwd = target if os.path.isabs(target) else os.path.normpath(
                    os.path.join(cwd, target))
            continue
        if inv.program != "gh":
            continue
        words = positionals(inv.args, BODY_FLAGS | BODY_FILE_FLAGS)
        if words[:2] not in (["pr", "create"], ["pr", "edit"]):
            continue
        # No body on the command line means gh opens an editor; there is nothing to judge yet.
        body = _body(inv.args, cwd)
        if not body:
            continue
        findings = _findings(body, _branch(root))
        if findings:
            listed = "\n".join(f"  - {f}" for f in findings)
            return deny(f"Blocked: this PR body does not match the required structure.\n{listed}")
    return ALLOW
