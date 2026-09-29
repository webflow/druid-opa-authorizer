import subprocess

import pytest

from catalog import CATALOG
from helpers import event as ev

GOOD = """[Ticket](https://webflow.atlassian.net/browse/DIN-187)

**Changes**
- Added the thing

**Background**
It was needed.
"""

NO_TICKET = """**Changes**
- Added the thing
"""


@pytest.fixture
def repo(tmp_path):
    """A real git repo on a ticket-named branch: the rule reads the branch to check for drift."""
    subprocess.run(["git", "init", "-q", "-b", "DIN-187-add-the-thing"], cwd=tmp_path, check=True)
    return tmp_path


def _decide(cmd: str, root) -> object:
    event = ev.Event(tool_name="Bash", command=cmd, cwd=str(root), raw={})
    return CATALOG["pr-body"].rule(event, {}, str(root))


def _q(body: str) -> str:
    return body.replace("'", "'\\''")


class TestDenied:
    def test_missing_ticket_link(self, repo):
        d = _decide(f"gh pr create --title x --body '{_q(NO_TICKET)}'", repo)
        assert d.allow is False
        assert "ticket link" in d.reason

    def test_ticket_drift_against_the_branch(self, repo):
        body = GOOD.replace("DIN-187", "DIN-999")
        d = _decide(f"gh pr create --body '{_q(body)}'", repo)
        assert d.allow is False
        assert "DIN-187" in d.reason

    def test_body_file_is_read(self, repo):
        (repo / "body.md").write_text(NO_TICKET)
        d = _decide("gh pr create --body-file body.md", repo)
        assert d.allow is False

    def test_pr_edit_is_checked_too(self, repo):
        d = _decide(f"gh pr edit 1 --body '{_q(NO_TICKET)}'", repo)
        assert d.allow is False


class TestAllowed:
    def test_well_formed_body(self, repo):
        assert _decide(f"gh pr create --body '{_q(GOOD)}'", repo).allow is True

    def test_no_body_flag_leaves_it_to_ci(self, repo):
        """`gh pr create` with no body opens an editor -- there is nothing to judge yet."""
        assert _decide("gh pr create --fill", repo).allow is True

    def test_other_gh_subcommands_are_ignored(self, repo):
        assert _decide(f"gh issue create --body '{_q(NO_TICKET)}'", repo).allow is True
        assert _decide("gh pr view 1", repo).allow is True

    def test_a_quoted_mention_is_not_an_invocation(self, repo):
        assert _decide("echo 'run gh pr create --body bad'", repo).allow is True

    def test_the_standards_own_good_example(self, repo):
        """The worked example in the PR standard must pass, or the limits are wrong."""
        body = ("[Ticket](https://webflow.atlassian.net/browse/DIN-187)\n\n"
                "**Changes**\n"
                "- Added the Reviewflow action so PRs get an automated review\n"
                "- Updated REVIEW.md to be agent-agnostic while still working with Reviewflow\n")
        assert _decide(f"gh pr create --body '{_q(body)}'", repo).allow is True


class TestLength:
    """The reason this hook exists: bodies that are structurally correct and far too long."""

    def test_body_over_the_character_cap(self, repo):
        body = GOOD + "\n" + ("padding prose that says nothing in particular. " * 30)
        d = _decide(f"gh pr create --body '{_q(body)}'", repo)
        assert d.allow is False
        assert "characters" in d.reason

    def test_too_many_changes_bullets(self, repo):
        body = GOOD.replace("- Added the thing", "\n".join(f"- Change {i}" for i in range(6)))
        d = _decide(f"gh pr create --body '{_q(body)}'", repo)
        assert d.allow is False
        assert "bullets" in d.reason

    def test_a_bullet_carrying_explanation(self, repo):
        long_bullet = ("- Generated files and vendored dependencies are excluded from review, and "
                       "the size budget is raised so large infrastructure changes are not "
                       "truncated")
        body = GOOD.replace("- Added the thing", long_bullet)
        d = _decide(f"gh pr create --body '{_q(body)}'", repo)
        assert d.allow is False
        assert "carries explanation" in d.reason

    def test_a_wrapped_bullet_counts_as_one_bullet(self, repo):
        """Wrapping is how a long bullet hides from a per-line check."""
        body = GOOD.replace("- Added the thing",
                            "- Added the thing\n  and then explained it at length across a second "
                            "line and a third one too, well past the limit")
        d = _decide(f"gh pr create --body '{_q(body)}'", repo)
        assert d.allow is False
        assert "carries explanation" in d.reason

    def test_background_over_three_sentences(self, repo):
        body = GOOD + "\n**Background**\nOne. Two. Three. Four. Five.\n"
        d = _decide(f"gh pr create --body '{_q(body)}'", repo)
        assert d.allow is False
        assert "sentences" in d.reason


class TestBodyFileIsResolvedLikeGhResolvesIt:
    """gh reads --body-file relative to the session's working directory, so resolving it from
    the repo root either misses the file -- which reads as "no body" and skips the check -- or
    judges an unrelated file of the same name."""

    @staticmethod
    def _decide_from(cmd: str, root, cwd) -> object:
        event = ev.Event(tool_name="Bash", command=cmd, cwd=str(cwd), raw={})
        return CATALOG["pr-body"].rule(event, {}, str(root))

    def test_a_body_file_beside_the_session_cwd_is_read(self, repo):
        sub = repo / "infra"
        sub.mkdir()
        (sub / "body.md").write_text(NO_TICKET)
        assert self._decide_from("gh pr create --body-file body.md", repo, sub).allow is False

    def test_a_same_named_file_at_the_root_is_not_judged_instead(self, repo):
        sub = repo / "infra"
        sub.mkdir()
        (repo / "body.md").write_text(NO_TICKET)   # would deny if resolved from the root
        (sub / "body.md").write_text(GOOD)         # what gh would actually read
        assert self._decide_from("gh pr create --body-file body.md", repo, sub).allow is True
