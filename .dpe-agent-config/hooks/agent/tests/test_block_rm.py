"""block-rm -- `rm -rf` blocked outright, however the flags are spelled."""

import pytest

from block_rm import rule
from helpers import event as ev


def _event(cmd: str) -> ev.Event:
    return ev.Event(tool_name="Bash", command=cmd, cwd=".", raw={})


def _blocked(cmd: str) -> None:
    d = rule(_event(cmd), {}, "/tmp/unused-root")
    assert d.allow is False, f"should block: {cmd}"
    assert d.reason.startswith("Blocked:")


def _allowed(cmd: str) -> None:
    d = rule(_event(cmd), {}, "/tmp/unused-root")
    assert d.allow is True, f"should allow: {cmd} ({d.reason})"


class TestEverySpellingOfRecursiveForce:
    """Matching the literal "-rf" would miss `-fr` and `-r -f`, which is what people type."""

    @pytest.mark.parametrize("cmd", [
        "rm -rf build",
        "rm -fr build",
        "rm -f -r build",
        "rm -r -f build",
        "rm -Rf build",          # -R is rm's own synonym for -r
        "rm -rfv build",         # bundled with an unrelated flag
        "rm --recursive --force build",
        "rm --force --recursive build",
        "rm -r --force build",
        "sudo rm -rf /",
        "rm -rf /",
        "rm -rf ~",
        "rm -rf .",
        "rm -rf .git",
        "rm -rf node_modules",   # routine, and blocked on purpose -- see the module docstring
    ])
    def test_denied(self, cmd):
        _blocked(cmd)

    @pytest.mark.parametrize("cmd", [
        "rm file.txt",
        "rm -f file.txt",        # force without recursion: one named file
        "rm -r build",           # recursion without force: rm still prompts
        "rm -i -r build",
        "ls -rf",                # not rm at all
        "git rm -r --cached x",  # `git rm` is a different program
        "echo rm -rf build",
    ])
    def test_allowed(self, cmd):
        _allowed(cmd)

    def test_found_anywhere_in_a_chain(self):
        # invocations() splits the line, so a deletion hidden behind a harmless first command
        # is judged on its own.
        _blocked("cd /tmp && rm -rf x")
        _blocked("make clean; rm -rf dist")
        _blocked("true && sudo rm -rf /var/lib/thing")

    def test_flags_after_a_double_dash_are_paths_not_flags(self):
        # `rm -- -rf` deletes a FILE named "-rf"; it is not a recursive force delete.
        _allowed("rm -- -rf")


class TestAbbreviatedLongOptions:
    """GNU getopt_long accepts any unambiguous abbreviation, so these really do delete."""

    @pytest.mark.parametrize("cmd", [
        "rm --rec --for build",
        "rm --r --f build",
        "rm --recur --forc build",
        "rm --recursive --for build",
    ])
    def test_blocked(self, cmd):
        _blocked(cmd)

    @pytest.mark.parametrize("cmd", [
        "rm --recursive build",     # recursive without force
        "rm --for build",           # force without recursive
        "rm --interactive build",
    ])
    def test_not_blocked(self, cmd):
        _allowed(cmd)


class TestExecWrappers:
    """A wrapper runs the real command, so the rule has to see past it. Each one here is modelled
    in `WRAPPERS`, with its value-taking flags and any leading positional."""

    @pytest.mark.parametrize("cmd", [
        "flock /tmp/lock rm -rf /",
        "flock -w 5 /tmp/lock rm -rf /",
        "setsid rm -rf /",
        "stdbuf -oL rm -rf /",
        "ionice -c3 rm -rf /",
        "ionice -c 3 rm -rf /",
        "doas -u root rm -rf /",
        "timeout 5 rm -rf /",
        "timeout -k 10 5 rm -rf /",
        "sudo timeout 5 rm -rf /",
        "doas -a persist rm -rf /",
        "doas -L rm -rf /",
        "unbuffer -p rm -rf /",
        "flock /tmp/l -c 'rm -rf /'",
    ])
    def test_blocked(self, cmd):
        _blocked(cmd)

    @pytest.mark.parametrize("cmd", [
        "grep rm notes.txt",
        "echo 'rm -rf /'",
        "git rm --cached x",
        "ls rm",
        "docker rm -f container",     # -f without -r is not a recursive delete
        "flock /tmp/l -c 'ls -la'",
    ])
    def test_not_blocked(self, cmd):
        _allowed(cmd)


class TestFindExec:
    """`find -exec` runs the command itself, so its value has to reach this rule as an
    invocation rather than as arguments to `find`."""

    @pytest.mark.parametrize("cmd", [
        "find . -type d -exec rm -rf {} +",
        "find . -execdir rm -rf {} +",
        "find . -ok rm -rf {} \\;",
        "find /tmp -name 'x*' -exec rm -rf {} \\;",
        "find . -exec sudo rm -rf {} +",
    ])
    def test_blocked(self, cmd):
        _blocked(cmd)

    def test_find_without_an_exec_is_untouched(self):
        _allowed("find . -name '*.log' -type f")


class TestShellDashC:
    """Every spelling of `-c` must be unwrapped, or this rule sees the program `bash` with the
    real command hidden in an argument."""

    @pytest.mark.parametrize("cmd", [
        "bash -ec 'rm -rf /'",
        "sh -xc 'rm -rf /'",
        "bash -euo pipefail -c 'rm -rf /'",
        "bash --noprofile -c 'rm -rf /'",
        "sudo bash -ec 'rm -rf /'",
    ])
    def test_blocked(self, cmd):
        _blocked(cmd)

    def test_a_script_argument_that_merely_looks_like_one_is_not(self):
        _allowed("bash script.sh -c 'rm -rf /'")


class TestMultiLineScripts:
    """A newline separates commands, so each line of a multi-line script has to reach this rule
    as its own invocation."""

    @pytest.mark.parametrize("cmd", [
        "ls\nrm -rf /",
        "set -e\nrm -rf /tmp/x",
        "cd /tmp\n\nrm -rf x",
        "echo start\r\nrm -rf /tmp/x\r\necho done",
    ])
    def test_blocked(self, cmd):
        _blocked(cmd)

    def test_a_newline_inside_quotes_is_not_a_boundary(self):
        _allowed('echo "rm -rf /"')
        _allowed('echo "a\nb"')


class TestCommentsAndHeredocs:
    def test_a_trailing_comment_does_not_hide_the_next_line(self):
        _blocked("set -e  # fail fast\nrm -rf /tmp/build")
        _blocked("cd /tmp # go\nrm -rf x")

    def test_a_heredoc_body_is_written_not_run(self):
        _allowed("cat > setup.sh <<'EOF'\nrm -rf /tmp/x\nEOF")

    def test_but_a_command_after_the_delimiter_still_counts(self):
        _blocked("cat > s.sh <<'EOF'\necho hi\nEOF\nrm -rf /tmp/x")

    def test_and_so_does_the_rest_of_the_line_the_heredoc_opens_on(self):
        _blocked("cat <<EOF && rm -rf /tmp/build\nhi\nEOF")
        _blocked("cat > s.sh <<'EOF'; rm -rf /tmp/x\nhi\nEOF")

    @pytest.mark.parametrize("cmd", [
        "bash <<'EOF'\nrm -rf /\nEOF",
        "sh <<EOF\nrm -rf /tmp/x\nEOF",
        "cat <<EOF | bash\nrm -rf /tmp/x\nEOF",
    ])
    def test_an_interpreter_runs_its_heredoc_body(self, cmd):
        """A body handed to a shell is a script, not a file being written."""
        _blocked(cmd)
