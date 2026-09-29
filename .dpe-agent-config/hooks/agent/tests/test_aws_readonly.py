"""aws-readonly -- which credential profiles an agent may name, via aws or pulumi.

The two allowed profiles (date-dev-read-only, date-read-only) are hardcoded rather than read
from .agents/config.env, because they are a fleet-wide convention and not a per-repo choice.
"""

import pytest

from aws_readonly import ALLOWED_PROFILES, rule
from helpers import event as ev

OK = "date-dev-read-only"
OK_PROD = "date-read-only"
ADMIN = "date"


def _event(cmd: str) -> ev.Event:
    return ev.Event(tool_name="Bash", command=cmd, cwd=".", raw={})


def _blocked(cmd: str) -> None:
    d = rule(_event(cmd), {}, "/tmp/unused-root")
    assert d.allow is False, f"should block: {cmd}"
    assert d.reason.startswith("Blocked:")


def _allowed(cmd: str) -> None:
    d = rule(_event(cmd), {}, "/tmp/unused-root")
    assert d.allow is True, f"should allow: {cmd} ({d.reason})"


class TestAllowedProfiles:
    def test_both_fleet_profiles_are_allowed(self):
        assert ALLOWED_PROFILES == {"date-dev-read-only", "date-read-only"}

    def test_dev_profile_via_aws_flag(self):
        _allowed(f"aws --profile {OK} s3 ls")
        _allowed(f"aws --profile={OK} s3 ls")

    def test_prod_profile_via_aws_flag(self):
        _allowed(f"aws --profile {OK_PROD} s3 ls")

    def test_dev_profile_via_pulumi_env(self):
        _allowed(f"AWS_PROFILE={OK} pulumi preview")

    def test_prod_profile_via_pulumi_env(self):
        _allowed(f"AWS_PROFILE={OK_PROD} pulumi preview")


class TestDisallowed:
    def test_disallowed_profile_via_aws(self):
        _blocked(f"aws --profile {ADMIN} s3 rm s3://b/k")

    def test_disallowed_profile_via_pulumi(self):
        # pulumi has no --profile flag; the env prefix is the only way it names one, so this is
        # the path that would go unchecked if only flags were parsed.
        _blocked(f"AWS_PROFILE={ADMIN} pulumi preview")

    def test_no_profile_at_all(self):
        _blocked("aws s3 ls")
        _blocked("pulumi preview")

    def test_chained_command_is_judged_per_invocation(self):
        # The bypass this closes: an allowed profile in front of a disallowed one. Checking
        # only the first profile named let this pass.
        _blocked(f"aws --profile {OK} sts get-caller-identity && aws --profile {ADMIN} s3 rm s3://b/k")

    def test_each_invocation_needs_its_own_profile(self):
        _blocked(f"aws --profile {OK} s3 ls && aws s3 rm s3://b/k")


class TestUnrelated:
    def test_unrelated_programs_are_ignored(self):
        _allowed("ls -la")
        _allowed("echo aws is fine")
        _allowed(f"grep -rn 'aws --profile {ADMIN}' .")

    def test_help_resolves_no_credentials(self):
        _allowed("aws --help")
        _allowed("pulumi up --help")


@pytest.mark.parametrize("profile,expect_ok", [(OK, True), (OK_PROD, True), (ADMIN, False)])
def test_profile_matrix(profile, expect_ok):
    d = rule(_event(f"aws --profile {profile} s3 ls"), {}, "/tmp/unused-root")
    assert d.allow is expect_ok, d.reason




class TestTheHookDoesNotLookAtTheVerb:
    """One invariant -- every credentialed call names an approved read-only profile -- and
    nothing about what the call does, since IAM on those profiles rejects a destructive verb."""

    @pytest.mark.parametrize("cmd", [
        f"aws --profile {OK_PROD} s3 rm s3://prod/key",
        f"aws --profile {OK_PROD} ec2 terminate-instances --instance-ids i-1",
        f"aws --profile {OK_PROD} iam delete-user --user-name x",
    ])
    def test_a_destructive_verb_under_an_approved_profile_is_allowed_here(self, cmd):
        _allowed(cmd)

    @pytest.mark.parametrize("cmd", [
        "aws s3 rm s3://prod/key",
        "aws ec2 terminate-instances --instance-ids i-1",
        f"aws --profile {ADMIN} s3 rm s3://prod/key",
    ])
    def test_but_the_same_command_without_an_approved_profile_is_not(self, cmd):
        _blocked(cmd)


class TestAProfileNameIsNotWhatAuthenticates:
    """An approved profile name must not be accepted alongside an environment variable that
    outranks it, whether that is a credential itself or a redirect of where the profile is
    read from."""

    @pytest.mark.parametrize("prefix", [
        "AWS_ACCESS_KEY_ID=AKIA0 AWS_SECRET_ACCESS_KEY=s",
        "AWS_SESSION_TOKEN=t",
        "AWS_SHARED_CREDENTIALS_FILE=/tmp/mine",
        "AWS_CONFIG_FILE=/tmp/mine",
        "AWS_WEB_IDENTITY_TOKEN_FILE=/tmp/tok",
        "AWS_CONTAINER_CREDENTIALS_FULL_URI=http://169.254.170.2/x",
        "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI=/x",
    ])
    def test_an_approved_profile_alongside_other_credentials_is_blocked(self, prefix):
        _blocked(f"{prefix} AWS_PROFILE={OK_PROD} aws s3 rm s3://prod/key")
        _blocked(f"{prefix} aws --profile {OK_PROD} s3 rm s3://prod/key")

    def test_pulumi_too_since_it_has_no_profile_flag_to_prefer(self):
        _blocked(f"AWS_ACCESS_KEY_ID=AKIA0 AWS_PROFILE={OK_PROD} pulumi up")

    def test_and_behind_an_approved_invocation_in_the_same_line(self):
        _blocked(f"aws --profile {OK} s3 ls && AWS_ACCESS_KEY_ID=AKIA0 "
                 f"AWS_PROFILE={OK_PROD} aws s3 rm s3://prod/key")

    def test_an_unrelated_aws_variable_still_passes(self):
        _allowed(f"AWS_REGION=us-west-2 AWS_PAGER= AWS_PROFILE={OK_PROD} aws s3 ls")


def test_find_exec_does_not_hide_the_aws_call():
    _blocked(r"find . -name x -exec aws s3 rm s3://prod/key \;")
    _allowed(rf"find . -name x -exec aws --profile {OK_PROD} s3 ls {{}} \;")
