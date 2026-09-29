import pytest

from helpers.shell import first_words, invocations, segments


@pytest.mark.parametrize("cmd,expect", [
    ("npm install", ["npm"]),
    ("cd x && npm install", ["cd", "npm"]),
    ("pnpm i; npm run build", ["pnpm", "npm"]),
    ("env CI=1 npm test", ["npm"]),
    ("CI=1 npm test", ["npm"]),
    ("sudo -E npm i", ["npm"]),
    ('bash -c "npm install"', ["npm"]),
    ('echo "npm install"', ["echo"]),
    ("ls | grep npm", ["ls", "grep"]),
    ("", []),
])
def test_first_words(cmd, expect):
    assert first_words(cmd) == expect

@pytest.mark.parametrize("cmd,expect", [
    # find runs -exec's value itself, so it is an invocation, not arguments to find.
    ("find . -type d -exec rm -rf {} +", ["find", "rm"]),
    ("find . -execdir rm -rf {} +", ["find", "rm"]),
    ("find . -ok rm -rf {} \\;", ["find", "rm"]),
    ("find . -okdir rm -rf {} \\;", ["find", "rm"]),
    ("find . -name x -exec aws s3 rm s3://prod/k \\;", ["find", "aws"]),
    ("find . -exec env FOO=1 rm -rf {} +", ["find", "rm"]),
    # `+` closes the batch and nothing more -- the next clause is still its own invocation.
    ("find . -exec rm -rf {} + && echo ok", ["find", "rm", "echo"]),
    # ...and outside an -exec batch `+` is an ordinary argument, not a boundary.
    ("chmod +x file", ["chmod"]),
    ("echo a + b", ["echo"]),
    # -exec on a program that does not have one is just an argument.
    ("grep -exec rm foo", ["grep"]),
])
def test_find_exec_starts_a_new_invocation(cmd, expect):
    assert first_words(cmd) == expect

@pytest.mark.parametrize("cmd,expect", [
    # Every spelling of -c hands the next word to the shell to run, so it must be parsed.
    ("bash -c 'rm -rf /'", ["rm"]),
    ("bash -ec 'rm -rf /'", ["rm"]),
    ("bash -ce 'rm -rf /'", ["rm"]),
    ("sh -xc 'rm -rf /'", ["rm"]),
    ("zsh -lc 'rm -rf /'", ["rm"]),
    ("dash -c 'rm -rf /'", ["rm"]),
    # -o takes the next word, bare or clustered -- it is not the script to run.
    ("bash -o pipefail -c 'rm -rf /'", ["rm"]),
    ("bash -euo pipefail -c 'rm -rf /'", ["rm"]),
    ("bash --noprofile -c 'rm -rf /'", ["rm"]),
    ("bash --rcfile myrc -c 'rm -rf /'", ["rm"]),
    ("sudo bash -ec 'rm -rf /'", ["rm"]),
    # ...and the other direction: none of these runs a nested command.
    ("bash -C file", ["bash"]),          # -C is noclobber; case matters
    ("bash deploy.sh", ["bash"]),
    ("bash -euo pipefail script.sh", ["bash"]),
    ("bash -c", ["bash"]),               # no operand to take
    # the script receives `-c foo` as arguments; bash does not run foo
    ("bash script.sh -c 'rm -rf /'", ["bash"]),
])
def test_shell_dash_c_in_every_spelling(cmd, expect):
    assert first_words(cmd) == expect

@pytest.mark.parametrize("cmd,expect", [
    # A newline separates commands exactly as `;` does.
    ("ls\nrm -rf /", ["ls", "rm"]),
    ("set -e\nrm -rf /tmp/x\necho done", ["set", "rm", "echo"]),
    ("echo hi\naws s3 ls", ["echo", "aws"]),
    ("ls\n\n  rm -rf /", ["ls", "rm"]),      # blank lines and indentation
    ("ls\r\nrm -rf /", ["ls", "rm"]),        # CRLF
    # ...but a newline INSIDE quotes is data, not a boundary.
    ('echo "a\nb"', ["echo"]),
    ("echo 'a\nb'", ["echo"]),
])
def test_newlines_separate_invocations(cmd, expect):
    assert first_words(cmd) == expect

@pytest.mark.parametrize("cmd,expect", [
    # A trailing comment must not take the newline with it, which is where scripts put the
    # boundary.
    ("set -e  # fail fast\nrm -rf /tmp/build", ["set", "rm"]),
    ("ls # note\nrm -rf /", ["ls", "rm"]),
    # ...and it truncated ordinary arguments that merely contain a '#'.
    ("aws s3 ls s3://bucket/key#frag", ["aws"]),
    ('git commit -m "fix #123"', ["git"]),
])
def test_a_comment_does_not_swallow_the_next_line(cmd, expect):
    assert first_words(cmd) == expect


@pytest.mark.parametrize("cmd,expect", [
    # `cat > file` writes its heredoc body rather than running it, so those lines are not
    # commands.
    ("cat > setup.sh <<'EOF'\nrm -rf /tmp/x\nEOF", ["cat"]),
    ("cat <<-EOF\nrm -rf /\nEOF\nls", ["cat", "ls"]),
    ("cat <<- EOF\nrm -rf /\nEOF\nls", ["cat", "ls"]),
    ("cat <<'EOF'\nrm -rf /tmp/x", ["cat"]),          # unterminated: all body
    # ...but a real command after the delimiter still counts.
    ("cat > s.sh <<'EOF'\necho hi\nEOF\nrm -rf /tmp/x", ["cat", "rm"]),
    ('grep x <<< "rm -rf /"', ["grep"]),               # herestring has no body
    # ...and so does the rest of the line the heredoc is opened on.
    ("cat <<EOF && rm -rf /tmp/x\nhi\nEOF", ["cat", "rm"]),
    ("cat <<EOF; rm -rf /tmp/x\nhi\nEOF", ["cat", "rm"]),
    ("cat > s.sh <<'EOF' || rm -rf /tmp/x\nhi\nEOF\nls", ["cat", "rm", "ls"]),
])
def test_heredoc_bodies_are_not_commands(cmd, expect):
    assert first_words(cmd) == expect


@pytest.mark.parametrize("cmd,expect", [
    # An interpreter runs what it is handed, so its heredoc body is a script, not data.
    ("bash <<'EOF'\nrm -rf /\nEOF", ["bash", "rm"]),
    ("sh <<EOF\nrm -rf /tmp/x\nEOF", ["sh", "rm"]),
    ("/bin/bash <<EOF\nrm -rf /tmp/x\nEOF", ["bash", "rm"]),
    ("cat <<EOF | bash\nrm -rf /tmp/x\nEOF", ["cat", "bash", "rm"]),
    # ...but the shell has to be on the heredoc's own line, not merely somewhere earlier.
    ("bash deploy.sh\ncat <<EOF\nrm -rf /\nEOF", ["bash", "cat"]),
])
def test_a_heredoc_fed_to_an_interpreter_is_parsed(cmd, expect):
    assert first_words(cmd) == expect

def test_unbalanced_quotes_do_not_crash():
    assert segments('echo "oops') != []


class TestInvocations:
    """invocations() -- the per-invocation env capture that segments()/first_words() don't
    expose, which a hook checking AWS_PROFILE needs."""

    def test_env_assignment_is_captured_not_discarded(self):
        [inv] = invocations("AWS_PROFILE=dev pulumi preview")
        assert inv.program == "pulumi"
        assert inv.args == ["preview"]
        assert inv.env == {"AWS_PROFILE": "dev"}

    def test_env_assignment_is_not_the_program(self):
        assert first_words("AWS_PROFILE=dev pulumi preview") == ["pulumi"]

    def test_each_invocation_has_its_own_env(self):
        # An allowed value in front of a disallowed one must not leak across invocations.
        [first, second] = invocations("AWS_PROFILE=ok aws s3 ls && aws s3 rm s3://b/k")
        assert first.env == {"AWS_PROFILE": "ok"}
        assert second.env == {}

    def test_a_program_named_inside_an_argument_is_not_an_invocation(self):
        # The whole reason this parsing exists.
        assert first_words("echo 'remember to run pulumi up tomorrow'") == ["echo"]
        assert first_words('grep -rn "pulumi destroy" .') == ["grep"]

    def test_operator_inside_quotes_does_not_split(self):
        assert first_words('pulumi preview --message "a; pulumi destroy"') == ["pulumi"]

    def test_wrapper_and_env_prefix_in_either_order(self):
        assert first_words("env AWS_PROFILE=x sudo pulumi preview") == ["pulumi"]
        [inv] = invocations("sudo AWS_PROFILE=x pulumi preview")
        assert inv.env == {"AWS_PROFILE": "x"}

    def test_bash_c_unwraps_one_level_and_keeps_env(self):
        [inv] = invocations('bash -c "AWS_PROFILE=x pulumi preview"')
        assert inv.program == "pulumi"
        assert inv.env == {"AWS_PROFILE": "x"}


class TestWrapperFlagsDoNotBecomeTheProgram:
    """A flag on any wrapper must be peeled with the wrapper, and a value-taking one must
    consume its value, or that value is read as the program."""

    @pytest.mark.parametrize("cmd", [
        "xargs -0 rm -rf x",
        "nice -n 10 rm -rf x",
        "sudo -u root rm -rf /",
        "sudo --user=root rm -rf /",
        "env -u PATH rm -rf /",
        "env -i rm -rf /",
        "xargs -I {} rm -rf {}",
        # Optional-argument flags: the next token is the command, not the flag's value.
        "xargs -i rm -rf {}",
        "xargs -l rm -rf /tmp",
        "xargs -e rm -rf /",
        "xargs --replace rm -rf {}",
        "xargs --eof rm -rf /",
        "xargs --max-lines rm -rf /",
        # ...and the glued spellings GNU actually accepts for them.
        "xargs -i{} rm -rf {}",
        # BSD spellings -- macOS is a supported platform (verification.sh works around bash 3.2).
        "xargs -J % rm -rf /tmp/x",
        "xargs -R 2 rm -rf /",
        "xargs -S 1024 rm -rf /",
        "env -P /bin rm -rf /",
        "env -a x rm -rf /",
        # Clustered short options: the value-taking letter is inside the token.
        "sudo -Eu root rm -rf /",
        "xargs -0I {} rm -rf x",
        "xargs -tJ % rm -rf /tmp/x",
        "env -ia x rm -rf /",
        # ...and a value glued to the letter consumes nothing further.
        "xargs -I{} rm -rf x",
        "sudo -uroot rm -rf /",
        # `timeout` takes a duration positional BEFORE the command, so peeling the wrapper alone
        # would make the duration the program.
        "timeout 5 rm -rf /",
        "timeout 5s rm -rf /",
        "timeout -k 10 5 rm -rf /",
        "timeout --signal=KILL 5 rm -rf /",
        "timeout --preserve-status 5 rm -rf /",
        "sudo timeout 5 rm -rf /",
        # flock's lock file is the same shape.
        "flock /tmp/l rm -rf /",
        "flock -w 5 /tmp/l rm -rf /",
        # ...and the flag-only exec wrappers.
        "setsid rm -rf /",
        "stdbuf -oL rm -rf /",
        "stdbuf -o L rm -rf /",
        "ionice -c 3 rm -rf /",
        "ionice -c3 rm -rf /",
        "doas -u root rm -rf /",
        "doas -a persist rm -rf /",   # -a takes a value
        "doas -L rm -rf /",           # -L is boolean; listing it would eat the command
        "doas -n rm -rf /",
        "unbuffer -p rm -rf /",
        "xargs --replace={} rm -rf {}",
        "sudo -E rm -rf /",
        "nohup rm -rf /",
        "sudo -- rm -rf /",
    ])
    def test_the_real_program_is_found(self, cmd):
        assert first_words(cmd) == ["rm"]

    def test_a_positional_wrapper_argument_is_not_the_program_or_its_args(self):
        """The delay belongs to `timeout`, not to the command it wraps."""
        inv = invocations("timeout 5 rm -rf x")[0]
        assert inv.program == "rm"
        assert inv.args == ["-rf", "x"]

    def test_a_glued_value_is_not_scanned_for_more_flags(self):
        """`-u` takes SHELL, so the S inside it is data rather than env's command flag."""
        inv = invocations("env -uSHELL rm -rf /")[0]
        assert inv.program == "rm"
        assert inv.args == ["-rf", "/"]

    def test_a_wrapper_flag_value_is_not_an_argument_of_the_program(self):
        inv = invocations("nice -n 10 rm -rf x")[0]
        assert inv.program == "rm"
        assert inv.args == ["-rf", "x"]

    @pytest.mark.parametrize("cmd", [
        "flock /tmp/l -c 'rm -rf /'",
        "flock /tmp/l --command='rm -rf /'",
        "flock /tmp/l -c'rm -rf /'",
        "flock -w 5 /tmp/l -c 'rm -rf /'",
        "env -S 'rm -rf /'",
        "env -S'rm -rf /'",
        "env --split-string='rm -rf /'",
        "env -iS 'rm -rf /'",          # clustered: the command letter is inside the token
        "env -iS'rm -rf /'",
        "env -uPATH -S 'rm -rf /'",
        # A letter inside another flag's glued VALUE is not a flag: -u takes SHELL, so the S
        # in -uSHELL must not be read as env's command flag.
        "env -uSHELL rm -rf /",
        "env -uS rm -rf /",
        "timeout 5 sh -c 'rm -rf /'",
    ])
    def test_a_wrapper_command_string_is_parsed_not_dropped(self, cmd):
        """The value of `-c`/`-S` is a command, not data, in every spelling a shell accepts --
        skipped as an ordinary flag value it leaves no program and the invocation is dropped."""
        assert first_words(cmd) == ["rm"]

    def test_a_quoted_program_path_with_a_space_still_resolves(self):
        """Nesting is keyed on the flag, not on whether the token holds whitespace, so a quoted
        program path stays a program."""
        inv = invocations("'/opt/My App/aws' s3 rm s3://b/k")[0]
        assert inv.program == "aws"
        assert inv.args == ["s3", "rm", "s3://b/k"]

    def test_env_assignments_still_survive_a_wrapper_flag(self):
        inv = invocations("sudo -u root env AWS_PROFILE=dev aws s3 ls")[0]
        assert inv.program == "aws"
        assert inv.env == {"AWS_PROFILE": "dev"}


class TestGroupingIsABoundary:
    """shlex emits grouping characters as their own tokens, so a wrapped command must still
    reach the rules as the program it is rather than as an argument to `(`."""

    @pytest.mark.parametrize("cmd", [
        "(rm -rf /)",
        "( rm -rf / )",
        "((rm -rf /))",
        "( ( rm -rf / ) )",
        "{ rm -rf /; }",
        "(cd /tmp && rm -rf x)",
        "( sudo rm -rf / )",
    ])
    def test_the_grouped_program_is_found(self, cmd):
        assert "rm" in first_words(cmd)

    def test_brace_expansion_is_not_a_boundary(self):
        """`{a,b}` is one token, an argument -- not a group wrapping a command."""
        inv = invocations("rm -rf {a,b}")[0]
        assert inv.program == "rm"
        assert inv.args == ["-rf", "{a,b}"]
