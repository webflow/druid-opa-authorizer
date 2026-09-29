from __future__ import annotations

import shlex
from dataclasses import dataclass, field

# Tokens that end one invocation and begin another. Grouping characters count too: a command
# wrapped in `(...)` or a spaced `{ ...; }` is still a command every rule has to see.
OPERATORS = {";", "&&", "||", "|", "&", "\n", "(", ")", "{", "}"}

# Any token made only of these is a boundary, however they run together: shlex groups adjacent
# punctuation into one token, so `((rm -rf /))` arrives as the single token `((`.
_OPERATOR_CHARS = frozenset(";&|()\n{}")


def _is_operator(token: str) -> bool:
    # `{}` is find's placeholder, never a brace group -- a shell group needs its braces spaced
    # and separated (`{ cmd; }`), so this exact token is only ever an argument.
    if token == "{}":
        return False
    return token in OPERATORS or bool(token) and all(c in _OPERATOR_CHARS for c in token)


# Arguments whose VALUE is a command the program runs itself, keyed by program. find spawns it
# directly rather than through a shell, so the tokens up to `;` or `+` are a whole invocation.
#
# find only: `fd` spells this `-x`/`-X` with different terminator rules, and a half-right entry
# here eats the program rather than finding it.
EXEC_ARGS = {"find": {"-exec", "-execdir", "-ok", "-okdir"}}
WRAPPERS = {"sudo", "doas", "env", "command", "nohup", "time", "nice", "xargs", "timeout",
            "flock", "setsid", "stdbuf", "ionice", "unbuffer"}

# Deliberately absent: `taskset` and `chrt`, whose leading positional is OPTIONAL. A positional
# count that is wrong in that direction eats the program and fails open.

# Wrappers that take a positional ARGUMENT before the command: how many leading non-flag tokens
# to drop, so `timeout 5 rm -rf /` does not read "5" as the program.
WRAPPER_POSITIONALS = {"timeout": 1, "flock": 1}

# Flags a wrapper takes a VALUE for. Only these consume the next token; a missing entry leaves
# the value to be read as the program, which bypasses every rule that keys on the program name.
WRAPPER_VALUE_FLAGS = {
    "sudo": {"-u", "--user", "-g", "--group", "-p", "--prompt", "-h", "--host",
             "-R", "--chroot", "-D", "--chdir", "-C", "--close-from", "-T", "--command-timeout",
             "-r", "--role", "-t", "--type"},
    # -P (BSD, altpath) has no GNU equivalent; both spellings of the rest are listed because a
    # consumer's machine may be either.
    "env": {"-u", "--unset", "-C", "--chdir", "-P", "-a", "--argv0"},
    "nice": {"-n", "--adjustment"},
    # REQUIRED-argument flags only: `-i`, `-l`, `-e` and their long forms take an *optional*
    # argument GNU xargs accepts only glued, so listing them would eat the program instead.
    # -J/-R/-S are BSD-only and required-argument, and macOS is a supported platform here.
    "xargs": {"-n", "--max-args", "-P", "--max-procs", "-I", "-d", "--delimiter",
              "-s", "--max-chars", "-a", "--arg-file", "-E", "-L",
              "-J", "-R", "-S"},
    "time": {"-f", "--format", "-o", "--output"},
    "timeout": {"-s", "--signal", "-k", "--kill-after"},
    # `-a style`, `-C config` and `-u user` take values; `-L`, `-n` and `-s` are boolean.
    "doas": {"-u", "-C", "-a"},
    "flock": {"-w", "--wait", "--timeout", "-E", "--conflict-exit-code"},
    "stdbuf": {"-i", "--input", "-o", "--output", "-e", "--error"},
    "ionice": {"-c", "--class", "-n", "--classdata", "-p", "--pid"},
    "command": set(),
    "nohup": set(),
}


@dataclass
class Invocation:
    """One program and the arguments and env-prefix assignments it was given."""

    program: str
    args: list[str] = field(default_factory=list)     # everything after the program name
    env: dict[str, str] = field(default_factory=dict)  # VAR=value prefixes, e.g. AWS_PROFILE=x
    nested: str = ""      # a shell string to parse instead, e.g. the value of `flock -c "..."`


def invocations(command: str) -> list[Invocation]:
    """Split a shell line into its Invocations, honouring quotes: a `;` or a denied word inside a
    quoted argument is data, not a command.

    A malformed tail (an unterminated quote, say) yields whatever parsed before it, so a caller
    enforcing a MANDATORY rule still sees the real invocations earlier in the line.
    """
    found: list[Invocation] = []
    current: Invocation | None = None
    in_prefix = False       # still peeling wrapper/env-assignment tokens for `current`
    last_wrapper = ""       # the most recent WRAPPERS token peeled, for its flags
    skip_value = False      # the previous token was a wrapper flag that takes a value
    take_nested = False     # the previous token was a flag whose value is a command string
    pending_positional = 0  # leading non-flag tokens still owed to the wrapper (timeout's delay)
    in_exec = False         # inside a command spawned by `find -exec`, where `+` terminates

    for token in _tokenize(command):
        if _is_operator(token):
            current = None
            in_prefix = False
            last_wrapper = ""
            skip_value = False
            take_nested = False
            pending_positional = 0
            in_exec = False
            continue

        # `+` closes a `find -exec ... {} +` batch. Everywhere else it is an ordinary argument
        # (`chmod +x`), so it must never become a global operator.
        if in_exec and token == "+":
            current = None
            in_exec = False
            continue

        if current is None:
            current = Invocation(program="")
            found.append(current)
            in_prefix = True
            last_wrapper = ""
            skip_value = False
            take_nested = False
            pending_positional = 0

        if in_prefix:
            if take_nested:
                current.nested = token
                take_nested = False
                continue
            if skip_value:
                skip_value = False
                continue
            name, _, value = token.partition("=")
            if "=" in token and not token.startswith("=") and name.isidentifier():
                current.env[name] = value
                continue
            if token in WRAPPERS:
                last_wrapper = token
                pending_positional += WRAPPER_POSITIONALS.get(token, 0)
                continue
            # A flag belongs to the wrapper that precedes it, whichever wrapper that is.
            if last_wrapper and token.startswith("-") and token != "--":
                kind, inline = _wrapper_flag(token, last_wrapper)
                if kind == "command":
                    if inline is None:
                        take_nested = True
                    else:
                        current.nested = inline
                elif kind == "value":
                    skip_value = True
                continue
            if last_wrapper and token == "--":
                continue
            # The wrapper's own positional argument, not the command it wraps.
            if pending_positional > 0:
                pending_positional -= 1
                continue
            in_prefix = False
            current.program = token.rsplit("/", 1)[-1]
        else:
            current.args.append(token)
            if token in EXEC_ARGS.get(current.program, ()):
                current = None
                in_exec = True

    resolved: list[Invocation] = []
    for inv in found:
        if inv.nested:
            resolved.extend(invocations(inv.nested))
            continue
        if not inv.program:
            continue
        nested = _shell_c_value(inv) if inv.program in SHELLS else None
        if nested is not None:
            resolved.extend(invocations(nested))
        else:
            resolved.append(inv)
    return resolved


SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}

# Long shell options that consume the NEXT word. The short ones (`-o`, `-O`) are matched by
# letter instead, because they cluster: `-euo pipefail` spends the next word just as `-o` does.
SHELL_LONG_VALUE_FLAGS = {"--rcfile", "--init-file"}


def _shell_c_value(inv: Invocation) -> str | None:
    """The command string `-c` was given, whatever spelling its flags arrived in.

    `c` anywhere in a short cluster counts, since bash takes -c's operand from the next word
    wherever the letter sits; `-C` is noclobber, and no shell here spells this one `--command`.
    """
    skip = False
    for i, a in enumerate(inv.args):
        if skip:
            skip = False
            continue
        if a == "--" or not a.startswith(("-", "+")):
            break  # the first operand -- for a shell without -c, the script to run
        if a in SHELL_LONG_VALUE_FLAGS:
            skip = True
            continue
        if a.startswith("--"):
            continue
        letters = a.lstrip("-+")
        if "c" in letters:
            return inv.args[i + 1] if i + 1 < len(inv.args) else None
        if "o" in letters or "O" in letters:
            skip = True  # -o/-O take the next word, clustered or not
    return None


# Wrapper flags whose value is a shell COMMAND, not data. That value has to be parsed in turn,
# or the command it names is never seen by any rule.
WRAPPER_COMMAND_FLAGS = {
    "flock": {"-c", "--command"},
    "env": {"-S", "--split-string"},
}


def _wrapper_flag(token: str, wrapper: str) -> tuple[str, str | None]:
    """Classify one wrapper flag: ("plain" | "value" | "command", inline value or None).

    Short options cluster and the FIRST recognised letter ends the token: everything after it is
    that flag's value, not more flags.
    """
    values: frozenset[str] | set[str] = WRAPPER_VALUE_FLAGS.get(wrapper, frozenset())
    commands: frozenset[str] | set[str] = WRAPPER_COMMAND_FLAGS.get(wrapper, frozenset())

    if token.startswith("--"):
        name, sep, inline = token.partition("=")
        if name in commands:
            return "command", (inline if sep else None)
        if name in values:
            return ("plain", None) if sep else ("value", None)
        return "plain", None

    for i, ch in enumerate(token[1:], start=1):
        flag = f"-{ch}"
        if flag in commands:
            return "command", (token[i + 1:] or None)
        if flag in values:
            # A glued remainder IS the value; only a bare trailing letter takes the next token.
            return ("plain", None) if i < len(token) - 1 else ("value", None)
    return "plain", None


def _feeds_an_interpreter(tokens: list[str], line_start: int) -> bool:
    """Whether a shell appears on the heredoc's own line, which makes its body a script.

    `bash <<EOF` and `cat <<EOF | sh` run what they are given; a name that merely looks like a
    shell costs an over-block, which is the direction to be wrong in here.
    """
    for token in tokens[line_start:]:
        if token == "\n":
            return False
        if token.rsplit("/", 1)[-1] in SHELLS:
            return True
    return False


def _strip_heredocs(tokens: list[str]) -> list[str]:
    """Drop heredoc BODIES, keeping the delimiter word as the argument it is.

    `cat > setup.sh <<'EOF' ... EOF` writes its body rather than running it, so parsing those
    lines as commands refuses a script that merely mentions `rm -rf`. A body handed to an
    interpreter is kept, and so is the rest of the line the heredoc is opened on.
    """
    out: list[str] = []
    i = 0
    line_start = 0
    while i < len(tokens):
        out.append(tokens[i])
        if tokens[i] == "\n":
            line_start = i + 1
        if tokens[i] != "<<" or i + 1 >= len(tokens):
            i += 1
            continue
        delim = tokens[i + 1]
        out.append(delim)
        if delim == "-" and i + 2 < len(tokens):      # `<<- EOF`
            delim = tokens[i + 2]
            out.append(delim)
            i += 1
        elif delim.startswith("-"):                   # `<<-EOF`
            delim = delim[1:]
        if _feeds_an_interpreter(tokens, line_start):
            j = i + 2
            while j < len(tokens) and tokens[j] != delim:
                out.append(tokens[j])
                j += 1
            i = j + 1
            line_start = i
            continue
        j = i + 2
        # Only the body is dropped: `cat <<EOF && rm -rf /` still runs the rm, and the newline
        # that ends the line is the boundary in front of whatever the body hides.
        while j < len(tokens) and tokens[j] != "\n":
            out.append(tokens[j])
            j += 1
        if j < len(tokens):
            out.append(tokens[j])
            j += 1
        while j < len(tokens) and tokens[j] != delim:
            j += 1
        i = j + 1                                     # past the closing delimiter line
        line_start = i
    return out


def _tokenize(command: str) -> list[str]:
    """Quote-aware tokens for the whole command line, recovering everything read before a
    malformed tail instead of raising: shlex.shlex's iterator raises ValueError only once it
    can no longer make progress (typically an unterminated quote at the very end), and every
    token read up to that point is still valid."""
    # A newline separates commands, so it must be BOTH a punctuation char and absent from
    # whitespace: either half alone loses the boundary or glues the lines into one word.
    lexer = shlex.shlex(command, posix=True, punctuation_chars="();<>|&\n")
    lexer.whitespace_split = True
    lexer.whitespace = " \t\r"
    # `#` is a commenter by default and shlex eats the rest of the line WITH its newline, taking
    # the boundary and truncating arguments like `s3://bucket/key#frag`. The cost of disabling it
    # is that a command named inside a comment parses as one, which over-blocks rather than under.
    lexer.commenters = ""
    tokens: list[str] = []
    while True:
        try:
            token = lexer.get_token()
        except ValueError:
            break
        if token is None:
            break
        tokens.append(token)
    return _strip_heredocs(tokens)


def segments(command: str) -> list[list[str]]:
    """Backward-compatible view: each invocation as [program, *args] (env prefixes dropped).
    For callers that only need argv, not per-invocation env."""
    return [[i.program, *i.args] for i in invocations(command)]


def first_words(command: str) -> list[str]:
    return [i.program for i in invocations(command) if i.program]


def positionals(args: list[str], value_flags: frozenset[str] | set[str] = frozenset()) -> list[str]:
    """The non-flag words of an argument list, in order.

    A subcommand is only findable by position once the flags are gone: `pulumi --cwd infra up`
    otherwise reads as the verb "infra". `value_flags` names flags that consume the next word;
    `--` ends flag parsing, as in getopt."""
    out: list[str] = []
    skip = False
    end_of_flags = False
    for arg in args:
        if skip:
            skip = False
            continue
        if not end_of_flags:
            if arg == "--":
                end_of_flags = True
                continue
            if arg in value_flags:
                skip = True
                continue
            if arg.startswith("-"):
                continue
        out.append(arg)
    return out
