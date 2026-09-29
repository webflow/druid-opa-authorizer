import json
import os
import pathlib
import shutil
import subprocess
import tempfile

import pytest

HOOK = os.path.join(os.path.dirname(__file__), "..", "run")

CLAUDE_EVENT = {"session_id": "s", "hook_event_name": "PreToolUse", "tool_name": "Bash",
                "tool_input": {"command": "rm -rf build", "description": "clean"}, "cwd": "."}
CODEX_EVENT = {"session_id": "thr_1", "hook_event_name": "PreToolUse", "tool_name": "Bash",
               "tool_use_id": "t1", "tool_input": {"command": "rm -rf build"}, "cwd": ".",
               "permission_mode": "default", "model": "gpt", "turn_id": "x"}

def run(rule, payload, env=None):
    """Runs the real launcher in a throwaway directory outside any git repo, so a denial this
    test provokes never gets logged into whatever repo pytest happens to be invoked from."""
    e = {**os.environ, **(env or {})}
    with tempfile.TemporaryDirectory() as cwd:
        p = subprocess.run(["bash", HOOK, rule], input=payload, capture_output=True, text=True,
                            env=e, cwd=cwd)
    return p.returncode, p.stderr

@pytest.mark.parametrize("event", [CLAUDE_EVENT, CODEX_EVENT])
def test_denies_with_exit_2_and_reason(event):
    code, err = run("block-rm", json.dumps(event))
    assert code == 2 and "rm -rf" in err

def test_a_non_bash_rule_still_runs_on_its_own_event(tmp_path):
    """A rule declaring PreToolUse:Write has to run on a Write call, rather than be skipped for
    the tool the launcher happens to be wired to."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    rules = tmp_path / ".agents" / "rules"
    rules.mkdir(parents=True)
    (rules / "no_write.py").write_text(
        "NAME = 'no-write'\nEVENT = 'PreToolUse:Write'\nDESCRIPTION = 'd'\n"
        "MANDATORY = False\n"
        "def rule(event, cfg, root):\n"
        "    from helpers.policy import deny\n"
        "    return deny('Blocked: no writes.')\n"
    )
    payload = {"tool_name": "Write", "tool_input": {"file_path": "/etc/passwd"},
               "cwd": str(tmp_path)}
    p = subprocess.run(["bash", HOOK, "no-write"], input=json.dumps(payload),
                       capture_output=True, text=True, cwd=tmp_path)
    assert p.returncode == 2, f"exit {p.returncode} is not a block; stderr: {p.stderr}"

    # ...and it still ignores a tool that is not its own.
    other = {**payload, "tool_name": "Bash", "tool_input": {"command": "ls"}}
    p2 = subprocess.run(["bash", HOOK, "no-write"], input=json.dumps(other),
                        capture_output=True, text=True, cwd=tmp_path)
    assert p2.returncode == 0


def test_non_bash_tool_is_ignored():
    code, _ = run("block-rm", json.dumps({**CLAUDE_EVENT, "tool_name": "Read"}))
    assert code == 0

def test_garbage_event_fail_open_vs_closed():
    # pr-body is the only fail-open hook on PreToolUse:Bash; log-instructions covers the same
    # branch on a different event.
    assert run("pr-body", "not json")[0] == 0
    assert run("log-instructions", "not json")[0] == 0
    assert run("aws-readonly", "not json")[0] == 2
    assert run("infra-readonly", "not json")[0] == 2
    assert run("block-rm", "not json")[0] == 2

class TestNothingOnThisPathCanExitOne:
    """Only exit 2 blocks, so every way a decision can fail to be reached -- an unparseable
    event, a raising rule, a consumer-owned config.env that will not decode -- must still land
    on the hook's fail policy.
    """

    def _repo(self, tmp_path):
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        (tmp_path / ".agents").mkdir()
        return tmp_path

    def _run(self, cwd, rule, command):
        payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)}
        p = subprocess.run(["bash", HOOK, rule], input=json.dumps(payload),
                           capture_output=True, text=True, cwd=cwd)
        return p.returncode

    @pytest.mark.parametrize("rule,command", [
        ("aws-readonly", "aws s3 rm s3://b/k"),
        ("infra-readonly", "pulumi destroy"),
        ("block-rm", "rm -rf /"),
    ])
    def test_unreadable_config_does_not_disable_a_mandatory_hook(self, tmp_path, rule, command):
        repo = self._repo(tmp_path)
        (repo / ".agents" / "config.env").write_bytes(b"AGENT_X=\xff\xfe\n")
        assert self._run(repo, rule, command) == 2

    def test_unreadable_config_still_allows_a_fail_open_hook(self, tmp_path):
        repo = self._repo(tmp_path)
        (repo / ".agents" / "config.env").write_bytes(b"AGENT_X=\xff\xfe\n")
        assert self._run(repo, "log-instructions", "ls") == 0

    def test_a_rule_that_raises_denies(self, tmp_path):
        repo = self._repo(tmp_path)
        rules = repo / ".agents" / "rules"
        rules.mkdir()
        (rules / "boom.py").write_text(
            "NAME = 'boom'\nEVENT = 'PreToolUse:Bash'\nDESCRIPTION = 'raises'\n"
            "MANDATORY = False\n"
            "def rule(event, cfg, root):\n"
            "    raise RuntimeError('kaboom')\n"
        )
        assert self._run(repo, "boom", "ls") == 2

    def test_a_local_rule_that_cannot_import_denies(self, tmp_path):
        repo = self._repo(tmp_path)
        rules = repo / ".agents" / "rules"
        rules.mkdir()
        (rules / "broken.py").write_text("syntax error here (\n")
        assert self._run(repo, "broken", "ls") == 2


def test_launcher_refuses_when_no_interpreter_is_usable(tmp_path):
    """With no usable python3, `exec` would exit 127 and not block, so the safety hooks refuse.

    The probe path is substituted because the guard only fires where no interpreter exists;
    everything else about the script, including the fail-closed list, is the real thing.
    """
    launcher = tmp_path / "run"
    launcher.write_text(
        pathlib.Path(HOOK).read_text().replace("/usr/bin/python3", str(tmp_path / "nope")))
    launcher.chmod(0o755)
    # bash is symlinked in so it stays reachable; only python3 must be absent, or the run fails
    # before reaching the guard.
    empty = tmp_path / "bin"
    empty.mkdir()
    (empty / "bash").symlink_to(shutil.which("bash") or "/bin/bash")
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "rm -rf /"},
                          "cwd": str(tmp_path)})
    env = {**os.environ, "PATH": str(empty)}   # keeps bash reachable, hides python3

    for name in ("aws-readonly", "infra-readonly", "block-rm"):
        p = subprocess.run(["bash", str(launcher), name], input=payload, capture_output=True,
                           text=True, env=env, cwd=tmp_path)
        assert p.returncode == 2, f"{name}: exit {p.returncode} does not block"
        assert "no usable python3" in p.stderr

    # An optional hook allows: a broken interpreter must not block every command in a session.
    p = subprocess.run(["bash", str(launcher), "pr-body"], input=payload, capture_output=True,
                       text=True, env=env, cwd=tmp_path)
    assert p.returncode == 0


def test_launcher_fail_closed_list_matches_policy():
    """The launcher hard-codes the fail-closed names because no interpreter is left to ask, so
    the two lists have to say the same thing."""
    import re

    from helpers.policy import FAIL_CLOSED
    src = open(HOOK, encoding="utf-8").read()
    m = re.search(r'case "\$1" in\s*\n\s*([a-z|-]+)\)', src)
    assert m, "could not find the fail-closed case list in the launcher"
    assert set(m.group(1).split("|")) == FAIL_CLOSED


def test_unknown_rule_is_usage_error():
    assert run("nope", "{}")[0] == 1

def test_list_shows_catalog():
    e = {**os.environ}
    p = subprocess.run(["bash", HOOK, "list"], input="", capture_output=True, text=True, env=e)
    assert p.returncode == 0
    assert "aws-readonly" in p.stdout
    assert "infra-readonly" in p.stdout
    assert "central" in p.stdout

def test_stats_with_no_log_reports_none(tmp_path):
    e = {**os.environ}
    p = subprocess.run(
        ["bash", HOOK, "stats"], input="", capture_output=True, text=True, env=e, cwd=tmp_path
    )
    # outside any git repo, repo_root() falls back to cwd; no .agents/.log there yet
    assert p.returncode == 0
    assert "no denials recorded" in p.stdout

def test_local_rule_resolves_and_runs(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    rules_dir = tmp_path / ".agents" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "no_shouting.py").write_text(
        "from __future__ import annotations\n"
        "NAME = 'no-shouting'\n"
        "EVENT = 'PreToolUse:Bash'\n"
        "DESCRIPTION = 'repo-local test rule'\n"
        "MANDATORY = False\n"
        "def rule(event, cfg, root):\n"
        "    from helpers.policy import ALLOW, deny\n"
        "    if 'YELL' in event.command:\n"
        "        return deny('Blocked: no yelling.')\n"
        "    return ALLOW\n"
    )
    event = {"session_id": "s", "hook_event_name": "PreToolUse", "tool_name": "Bash",
             "tool_input": {"command": "echo YELL"}, "cwd": str(tmp_path)}
    p = subprocess.run(["bash", HOOK, "no-shouting"], input=json.dumps(event),
                        capture_output=True, text=True, cwd=tmp_path)
    assert p.returncode == 2
    assert "no yelling" in p.stderr

    p_list = subprocess.run(["bash", HOOK, "list"], capture_output=True, text=True, cwd=tmp_path)
    assert "no-shouting" in p_list.stdout
    assert "local" in p_list.stdout

    # A local rule is in neither policy set, so an unparseable event denies: allowing whatever
    # is unclassified would leave a rule registered and not enforcing.
    p_garbage = subprocess.run(["bash", HOOK, "no-shouting"], input="not json",
                               capture_output=True, text=True, cwd=tmp_path)
    assert p_garbage.returncode == 2


class TestConsumerRepoCannotShadowVendoredModules:
    """Script-path launch keeps the consumer's repo root off sys.path, so a directory of theirs
    named like a vendored module cannot shadow it."""

    def _consumer_repo(self, tmp_path, *names):
        """A repo root holding modules named exactly like the vendored ones."""
        for name in names:
            if name.endswith(".py"):
                (tmp_path / name).write_text("raise RuntimeError('consumer module shadowed it')\n")
            else:
                pkg = tmp_path / name
                pkg.mkdir()
                (pkg / "__init__.py").write_text(
                    "raise RuntimeError('consumer package shadowed it')\n")
        return tmp_path

    def _deny(self, cwd, rule, command):
        payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)}
        p = subprocess.run(["bash", HOOK, rule], input=json.dumps(payload),
                           capture_output=True, text=True, cwd=cwd)
        return p.returncode, p.stderr

    def test_still_blocks_with_colliding_helpers_package(self, tmp_path):
        repo = self._consumer_repo(tmp_path, "helpers")
        code, err = self._deny(repo, "infra-readonly", "pulumi destroy")
        assert code == 2, f"exit {code} is not a block; stderr: {err}"

    def test_still_blocks_with_colliding_top_level_modules(self, tmp_path):
        repo = self._consumer_repo(tmp_path, "helpers", "catalog.py", "cli.py", "aws_readonly.py")
        code, err = self._deny(repo, "aws-readonly", "aws s3 rm s3://b/k")
        assert code == 2, f"exit {code} is not a block; stderr: {err}"
