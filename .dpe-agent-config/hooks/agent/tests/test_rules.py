import json

from catalog import CATALOG, REQUIRED_ATTRS
from helpers import event as ev

# Each rule's own policy is tested in its own file; what is left here is the catalog contract.


def test_catalog_integrity():
    """Every catalog entry declares the full contract and NAME is unique (build-time check
    in catalog.py already enforces this at import; this test pins the expected set)."""
    assert set(CATALOG) == {"aws-readonly", "infra-readonly", "block-rm",
                            "log-instructions", "pr-body"}
    assert CATALOG["aws-readonly"].mandatory is True
    assert CATALOG["infra-readonly"].mandatory is True
    assert CATALOG["log-instructions"].mandatory is False
    assert CATALOG["aws-readonly"].event == "PreToolUse:Bash"
    assert CATALOG["log-instructions"].event == "InstructionsLoaded"


def test_policy_sets_cover_the_catalog():
    """Every catalog hook is classified fail-open or fail-closed, in exactly one set.

    Both sets are hand-maintained and `run()` reads only FAIL_OPEN, so a hook in neither would
    be silently fail-open."""
    from helpers.policy import FAIL_CLOSED, FAIL_OPEN
    assert not (FAIL_CLOSED & FAIL_OPEN), "a hook cannot be both fail-open and fail-closed"
    unclassified = set(CATALOG) - FAIL_CLOSED - FAIL_OPEN
    assert not unclassified, f"catalog hooks in neither policy set: {sorted(unclassified)}"
    stale = (FAIL_CLOSED | FAIL_OPEN) - set(CATALOG)
    assert not stale, f"policy sets name hooks not in the catalog: {sorted(stale)}"


def test_fail_open_fallback_is_not_silent(tmp_path, capsys):
    """A denial announces itself and an allow does not, so a rule that raises on every
    invocation would otherwise allow forever in silence."""
    from helpers import policy
    d = policy.fallback("log-instructions", "the rule raised RuntimeError: boom", str(tmp_path))
    assert d.allow is True
    assert "fail-open" in capsys.readouterr().err
    logged = (tmp_path / ".agents" / ".log" / "denials.jsonl").read_text()
    assert "fail-open fallback" in logged


def test_fail_closed_fallback_denies_and_names_the_rule(tmp_path):
    from helpers import policy
    d = policy.fallback("aws-readonly", "the rule raised RuntimeError: boom", str(tmp_path))
    assert d.allow is False
    assert "aws-readonly" in d.reason


def test_stats_separates_fail_open_allows_from_denials(tmp_path, capsys):
    """A fail-open allow is logged but is not a denial; counting it as one would report a broken
    hook as a well-behaved agent."""
    from cli import _cmd_stats
    from helpers import policy
    policy.log(str(tmp_path), "aws-readonly", "aws s3 rm s3://b/k", "blocked")
    policy.fallback("log-instructions", "the rule raised RuntimeError: boom", str(tmp_path))
    capsys.readouterr()
    _cmd_stats(str(tmp_path))
    out = capsys.readouterr().out
    denials, _, allows = out.partition("allowed after the rule could not be reached")
    assert "aws-readonly" in denials and "log-instructions" not in denials
    assert "log-instructions" in allows


def test_a_row_without_a_decision_field_counts_as_a_denial(tmp_path, capsys):
    """Logs written before the field existed must not silently become allows."""
    import json

    from cli import _cmd_stats
    d = tmp_path / ".agents" / ".log"
    d.mkdir(parents=True)
    (d / "denials.jsonl").write_text(json.dumps({"rule": "block-rm", "reason": "old row"}) + "\n")
    _cmd_stats(str(tmp_path))
    out = capsys.readouterr().out
    assert "block-rm" in out.partition("allowed after")[0]


def test_catalog_modules_declare_required_attrs():
    import catalog as catalog_module
    for module in catalog_module._MODULES:
        for attr in REQUIRED_ATTRS:
            assert hasattr(module, attr), f"{module.__name__} missing {attr}"


def test_log_instructions_writes_and_allows(tmp_path):
    raw = {"hook_event_name": "InstructionsLoaded", "session_id": "s", "path": "AGENTS.md"}
    event = ev.Event(tool_name="", command="", cwd=str(tmp_path), raw=raw)
    d = CATALOG["log-instructions"].rule(event, {}, str(tmp_path))
    assert d.allow is True
    logged = (tmp_path / ".agents" / ".log" / "instructions-loaded.jsonl").read_text()
    assert json.loads(logged.split(" ", 1)[1]) == raw
