"""infra-readonly -- which pulumi commands are denied, and through which invocation forms.

The pulumi cases here encode the invocation forms that can hide the verb from the rule.
"""

import pytest

from helpers import event as ev
from infra_readonly import rule


def _event(cmd: str) -> ev.Event:
    return ev.Event(tool_name="Bash", command=cmd, cwd=".", raw={})


def _blocked(cmd: str) -> None:
    d = rule(_event(cmd), {}, "/tmp/unused-root")
    assert d.allow is False, f"should block: {cmd}"
    assert d.reason.startswith("Blocked:")


def _allowed(cmd: str) -> None:
    d = rule(_event(cmd), {}, "/tmp/unused-root")
    assert d.allow is True, f"should allow: {cmd} ({d.reason})"


class TestPulumiDenied:
    @pytest.mark.parametrize("verb", ["up", "update", "destroy", "watch", "cancel", "refresh"])
    def test_deploy_and_teardown_verbs(self, verb):
        _blocked(f"pulumi {verb}")

    def test_update_is_an_alias_for_up(self):
        _blocked("pulumi update --yes")

    @pytest.mark.parametrize("sub", [
        "delete", "move", "protect", "rename", "repair", "unprotect", "upgrade",
        "some-future-subcommand",
    ])
    def test_every_state_subcommand(self, sub):
        _blocked(f"pulumi state {sub} urn:x")

    def test_state_alone(self):
        _blocked("pulumi state")

    @pytest.mark.parametrize("sub", ["rm", "import", "change-secrets-provider"])
    def test_denied_stack_subcommands(self, sub):
        _blocked(f"pulumi stack {sub}")

    @pytest.mark.parametrize("cmd", [
        "pulumi import aws:s3/bucket:Bucket b my-bucket",
        "pulumi import --yes aws:ec2/vpc:Vpc v vpc-123",
        "pulumi -v 3 import aws:s3/bucket:Bucket b my-bucket",
    ])
    def test_import_writes_to_state(self, cmd):
        """`import` adds a resource to the stack's state, the same class of write as the
        `stack import` pair."""
        _blocked(cmd)

    @pytest.mark.parametrize("cmd", [
        "cd /repo && pulumi destroy",
        "AWS_PROFILE=x pulumi up",
        "/usr/local/bin/pulumi destroy",
        "pulumi --cwd=infra up",
        "pulumi --stack dev destroy",
        "pulumi -C infra update",
        # Every global flag pulumi takes a value for: one missing entry shifts the verb out of
        # the positional slot and the command is allowed through.
        "pulumi -v 3 destroy",
        "pulumi --verbose 3 up",
        "pulumi --tracing-header x up",
        "pulumi --memprofilerate 5 destroy",
        "pulumi --profiling p --tracing t -v 3 destroy",
    ])
    def test_invocation_forms(self, cmd):
        _blocked(cmd)

    def test_a_flag_value_is_not_the_subcommand(self):
        # Without PULUMI_VALUE_FLAGS this reads as the verb "infra" and is allowed.
        _blocked("pulumi --cwd infra up")

    @pytest.mark.parametrize("cmd", [
        "pulumi --logtostderr destroy",
        "pulumi --logflow up",
        "pulumi --non-interactive destroy",
        "pulumi --emoji destroy",
    ])
    def test_boolean_globals_do_not_swallow_the_verb(self, cmd):
        """The mirror of the test above: a boolean flag listed in PULUMI_VALUE_FLAGS would
        consume the verb as its value."""
        _blocked(cmd)


class TestPulumiAllowed:
    @pytest.mark.parametrize("verb", ["preview", "version", "about", "whoami", "logs", "console"])
    def test_read_only_verbs(self, verb):
        _allowed(f"pulumi {verb}")

    def test_read_only_subcommands(self):
        _allowed("pulumi stack ls")
        _allowed("pulumi stack output")
        _allowed("pulumi config get somekey")

    def test_refresh_as_a_flag_on_an_allowed_verb(self):
        _allowed("pulumi preview --refresh")

    def test_help_runs_nothing(self):
        _allowed("pulumi up --help")
        _allowed("pulumi destroy -h")

    def test_named_inside_an_argument(self):
        _allowed("echo 'remember to run pulumi up tomorrow'")
        _allowed('grep -rn "pulumi destroy" .')

    def test_currently_allowed_deliberate_scope(self):
        # Listed so the scope is visible, not implied by absence.
        _allowed("pulumi config set foo bar")
        _allowed("pulumi stack select dev")

class TestUnrelated:
    def test_unrelated_commands(self):
        _allowed("ls -la")
        _allowed("git status")

