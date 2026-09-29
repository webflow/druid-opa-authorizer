import json
from pathlib import Path

import pytest

from cli import _cmd_check_registration, _cmd_resolve
from helpers.registry import (
    covers,
    extract_name,
    launcher_problem,
    parse_command,
    registered,
)

CLAUDE_CMD = "$CLAUDE_PROJECT_DIR/.dpe-agent-config/hooks/agent/run "

GOOD_CLAUDE = {
    "hooks": {
        "PreToolUse": [{
            "matcher": "Bash",
            "hooks": [
                {"type": "command", "command": CLAUDE_CMD + "aws-readonly"},
                {"type": "command", "command": CLAUDE_CMD + "infra-readonly"},
                {"type": "command", "command": CLAUDE_CMD + "block-rm"},
            ],
        }],
        "InstructionsLoaded": [{
            "hooks": [
                {"type": "command",
                 "command": CLAUDE_CMD + "log-instructions"},
            ],
        }],
    }
}

GOOD_CODEX = {
    "hooks": {
        "PreToolUse": [{
            "matcher": "Bash",
            "hooks": [
                {"type": "command",
                 "command": 'bash "$(git rev-parse --show-toplevel)'
                            '/.dpe-agent-config/hooks/agent/run" aws-readonly'},
                {"type": "command",
                 "command": 'bash "$(git rev-parse --show-toplevel)'
                            '/.dpe-agent-config/hooks/agent/run" infra-readonly'},
                {"type": "command",
                 "command": 'bash "$(git rev-parse --show-toplevel)'
                            '/.dpe-agent-config/hooks/agent/run" block-rm'},
            ],
        }],
    }
}


LAUNCHER = ".dpe-agent-config/hooks/agent/run"


def _write(root: Path, rel: str, data: dict) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data))


def _launcher(root: Path, rel: str = LAUNCHER) -> None:
    """A consumer always has a launcher, so a fixture without one would test an impossible
    state and mask the possible one: a registration pointing at the old path."""
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("#!/usr/bin/env bash\n")
    p.chmod(0o755)


def test_extract_name():
    assert extract_name(CLAUDE_CMD + "aws-readonly") == "aws-readonly"
    cmd = 'bash "$(git rev-parse --show-toplevel)/x/hook" infra-readonly'
    assert extract_name(cmd) == "infra-readonly"
    assert extract_name(".dpe-agent-config/hooks/agent/run") is None  # no trailing name
    assert extract_name("") is None


def test_registered_parses_event_and_matcher(tmp_path):
    _write(tmp_path, ".claude/settings.json", GOOD_CLAUDE)
    reg = registered(tmp_path / ".claude" / "settings.json")
    assert set(reg["PreToolUse:Bash"]) == {"aws-readonly", "infra-readonly", "block-rm"}
    assert set(reg["InstructionsLoaded"]) == {"log-instructions"}
    assert reg["PreToolUse:Bash"]["aws-readonly"] == (CLAUDE_CMD.strip(), None)


def test_check_registration_passes_when_complete(tmp_path):
    _write(tmp_path, ".claude/settings.json", GOOD_CLAUDE)
    _write(tmp_path, ".codex/hooks.json", GOOD_CODEX)
    _launcher(tmp_path)
    assert _cmd_check_registration(str(tmp_path), ".claude/settings.json", ".codex/hooks.json") == 0


def test_check_registration_fails_on_missing_mandatory_hook(tmp_path):
    bad = json.loads(json.dumps(GOOD_CLAUDE))
    bad["hooks"]["PreToolUse"][0]["hooks"].pop()  # drop infra-readonly
    _write(tmp_path, ".claude/settings.json", bad)
    _write(tmp_path, ".codex/hooks.json", GOOD_CODEX)
    _launcher(tmp_path)
    assert _cmd_check_registration(str(tmp_path), ".claude/settings.json", ".codex/hooks.json") == 1


def test_check_registration_passes_without_optional_hook(tmp_path):
    no_optional = json.loads(json.dumps(GOOD_CLAUDE))
    del no_optional["hooks"]["InstructionsLoaded"]
    _write(tmp_path, ".claude/settings.json", no_optional)
    _write(tmp_path, ".codex/hooks.json", GOOD_CODEX)
    _launcher(tmp_path)
    assert _cmd_check_registration(str(tmp_path), ".claude/settings.json", ".codex/hooks.json") == 0


def test_check_registration_fails_on_unresolved_name(tmp_path):
    unknown = json.loads(json.dumps(GOOD_CLAUDE))
    unknown["hooks"]["PreToolUse"][0]["hooks"].append(
        {"type": "command", "command": CLAUDE_CMD + "not-a-real-hook"}
    )
    _write(tmp_path, ".claude/settings.json", unknown)
    _write(tmp_path, ".codex/hooks.json", GOOD_CODEX)
    _launcher(tmp_path)
    assert _cmd_check_registration(str(tmp_path), ".claude/settings.json", ".codex/hooks.json") == 1


def test_check_registration_missing_file(tmp_path):
    _write(tmp_path, ".codex/hooks.json", GOOD_CODEX)
    _launcher(tmp_path)
    assert _cmd_check_registration(str(tmp_path), ".claude/settings.json", ".codex/hooks.json") == 1


def test_resolve_local_rule(tmp_path):
    rules_dir = tmp_path / ".agents" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "custom_check.py").write_text(
        "NAME = 'custom-check'\nEVENT = 'PreToolUse:Bash'\nDESCRIPTION = 'd'\nMANDATORY = False\n"
        "def rule(event, cfg, root):\n"
        "    from helpers.policy import ALLOW\n"
        "    return ALLOW\n"
    )
    assert _cmd_resolve(str(tmp_path), "custom-check") == 0
    assert _cmd_resolve(str(tmp_path), "no-such-hook") == 1


def test_parse_command_splits_launcher_and_name():
    assert parse_command(f"{LAUNCHER} aws-readonly") == (LAUNCHER, "aws-readonly", None)
    codex = f'bash "$(git rev-parse --show-toplevel)/{LAUNCHER}" infra-readonly'
    # The interpreter is carried, not dropped: it decides whether the file's mode matters.
    assert parse_command(codex) == (f"$(git rev-parse --show-toplevel)/{LAUNCHER}",
                                    "infra-readonly", "bash")
    assert parse_command(LAUNCHER) == (None, None, None)  # no name; no launcher either
    assert parse_command("") == (None, None, None)


def test_launcher_problem_reports_only_what_it_can_resolve(tmp_path):
    _launcher(tmp_path)
    # A relative launcher resolves against the session's cwd, so it is a finding now even
    # though the file exists at that path from the repo root.
    assert launcher_problem(LAUNCHER, str(tmp_path)) is not None
    assert launcher_problem(f"$CLAUDE_PROJECT_DIR/{LAUNCHER}", str(tmp_path)) is None
    assert launcher_problem(f"$(git rev-parse --show-toplevel)/{LAUNCHER}", str(tmp_path)) is None
    assert launcher_problem("$CLAUDE_PROJECT_DIR/.dpe-agent-config/hooks/hook",
                            str(tmp_path)) is not None
    # A substitution we don't understand is not a finding, since a false red across the fleet
    # costs more than a missed edge.
    assert launcher_problem("$SOME_OTHER_VAR/run", str(tmp_path)) is None
    assert launcher_problem(None, str(tmp_path)) is None


def test_check_registration_fails_on_stale_launcher_path(tmp_path):
    """Syncs replace the vendored directory but never the consumer-owned registration files, so
    a moved launcher strands them at a 127 the name alone cannot reveal."""
    stale = json.loads(json.dumps(GOOD_CLAUDE))
    for h in stale["hooks"]["PreToolUse"][0]["hooks"]:
        h["command"] = h["command"].replace("hooks/agent/run", "hooks/hook")
    _write(tmp_path, ".claude/settings.json", stale)
    _write(tmp_path, ".codex/hooks.json", GOOD_CODEX)
    _launcher(tmp_path)
    assert _cmd_check_registration(str(tmp_path), ".claude/settings.json",
                                   ".codex/hooks.json") == 1


def test_a_launcher_without_the_executable_bit_is_a_finding(tmp_path):
    """Claude Code execs the launcher directly, so a file without +x exits 126, which does not
    block any more than the 127 above."""
    _launcher(tmp_path)
    path = tmp_path / LAUNCHER
    registered_as = f"$CLAUDE_PROJECT_DIR/{LAUNCHER}"

    path.chmod(0o755)
    assert launcher_problem(registered_as, str(tmp_path)) is None

    path.chmod(0o644)
    problem = launcher_problem(registered_as, str(tmp_path))
    assert problem is not None and "126" in problem



class TestCoversAcceptsABroaderMatcher:
    """Both tools accept a matcher broader than one tool name, and a registration that genuinely
    covers the declared tool must not be reported as missing."""

    @pytest.mark.parametrize("key", [
        "PreToolUse:Bash",       # exactly the declared tool
        "PreToolUse",            # matcher omitted or empty: every tool on the event
        "PreToolUse:*",
        "PreToolUse:Bash|Edit",  # regex alternation including it
        "PreToolUse:Bash.*",
    ])
    def test_covered(self, key):
        assert covers(key, "PreToolUse:Bash")

    @pytest.mark.parametrize("key", [
        "PreToolUse:Edit",       # a different tool
        "PreToolUse:Edit|Write",
        "PreToolUse:bash",       # matchers are case-sensitive, as the tools treat them
        "PreToolUse:[",          # not a valid regex: compared literally, not raised
        "PostToolUse:Bash",      # right tool, wrong event
        "PostToolUse",
    ])
    def test_not_covered(self, key):
        assert not covers(key, "PreToolUse:Bash")

    def test_a_hook_declaring_no_tool_needs_an_equally_unscoped_registration(self):
        assert covers("InstructionsLoaded", "InstructionsLoaded")
        assert covers("InstructionsLoaded:*", "InstructionsLoaded")
        assert not covers("InstructionsLoaded:Bash", "InstructionsLoaded")


@pytest.mark.parametrize("matcher", ["*", None, "", "Bash|Edit"])
def test_check_registration_accepts_a_broader_matcher_end_to_end(tmp_path, matcher):
    """The unit cases above in the shape a consumer actually writes: the same three hooks, on a
    matcher wider than `Bash`."""
    settings = json.loads(json.dumps(GOOD_CLAUDE))
    group = settings["hooks"]["PreToolUse"][0]
    if matcher is None:
        group.pop("matcher")
    else:
        group["matcher"] = matcher
    _write(tmp_path, ".claude/settings.json", settings)
    _write(tmp_path, ".codex/hooks.json", GOOD_CODEX)
    _launcher(tmp_path)
    assert _cmd_check_registration(str(tmp_path), ".claude/settings.json",
                                   ".codex/hooks.json") == 0


def test_check_registration_still_fails_on_a_matcher_that_misses_bash(tmp_path, capsys):
    settings = json.loads(json.dumps(GOOD_CLAUDE))
    settings["hooks"]["PreToolUse"][0]["matcher"] = "Edit|Write"
    _write(tmp_path, ".claude/settings.json", settings)
    _write(tmp_path, ".codex/hooks.json", GOOD_CODEX)
    _launcher(tmp_path)
    assert _cmd_check_registration(str(tmp_path), ".claude/settings.json",
                                   ".codex/hooks.json") == 1
    # The exit code alone would also pass if the run failed for an unrelated reason, such as an
    # unresolved name or a launcher finding.
    err = capsys.readouterr().err
    assert "missing the mandatory hook 'block-rm'" in err


def test_codex_style_registration_is_not_reported_as_non_executable(tmp_path):
    """Codex registers `bash <launcher> <name>`, and bash reads a file it is handed whatever its
    mode is, so the 126 check does not apply there."""
    _launcher(tmp_path)
    (tmp_path / LAUNCHER).chmod(0o644)
    direct = f"$CLAUDE_PROJECT_DIR/{LAUNCHER}"
    assert launcher_problem(direct, str(tmp_path)) is not None            # exec'd: mode matters
    assert launcher_problem(direct, str(tmp_path), "bash") is None        # interpreted: it does not
    # A launcher that is not there at all is still a finding either way.
    missing = "$CLAUDE_PROJECT_DIR/.dpe-agent-config/hooks/agent/gone"
    assert launcher_problem(missing, str(tmp_path), "bash") is not None
