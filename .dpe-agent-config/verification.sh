#!/usr/bin/env bash
# Usage: .dpe-agent-config/verification.sh lint | drift | checksum | init | stubs | probe
set -uo pipefail
# SELF is resolved BEFORE the cd, and the order is load-bearing: $0 can be a relative path, and
# resolving it after moving to the repo root pointed it at a directory outside the repo. CFG then
# fell back to ".dpe-agent-config", which does not exist here, and lint reported two invented
# failures instead of an error. Where this script lives, relative to the repo root:
# ".dpe-agent-config" in a consumer, "shared" in the source repo -- derived, not hardcoded, so
# this repo can run its own rules.
SELF=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$(git rev-parse --show-toplevel)" && pwd); cd "$ROOT" || exit 1
fail=0; bad() { echo "FAIL: $*"; fail=1; }
CFG=${SELF#"$ROOT"/}
[ "$CFG" = "$SELF" ] && CFG=.dpe-agent-config    # invoked from outside the repo; assume vendored
VENDORED=0; [ "$CFG" = ".dpe-agent-config" ] && VENDORED=1

sha() { if command -v sha256sum >/dev/null; then sha256sum; else shasum -a 256; fi; }

checksum() { # hash of the whole vendored directory; only itself and build caches excluded
  # Names are hashed with the contents. Hashing concatenated contents alone made renames and
  # moves invisible, and a renamed catalog module fails cli.py at import -- exit 1, which does
  # not block, with drift still green.
  ( cd "${1:-$CFG}" && find . -type f ! -name CHECKSUM \
      ! -path '*/__pycache__/*' ! -path '*/.pytest_cache/*' ! -path '*/.mypy_cache/*' \
      ! -path '*/.ruff_cache/*' -print0 \
    | LC_ALL=C sort -z \
    | while IFS= read -r -d '' f; do printf '%s\0' "$f"; cat "$f"; done \
    | sha | cut -d' ' -f1 )
}

section_has_body() { # file, heading prefix -- 0 when the section has a non-blank body line
  # "Required" means present AND non-empty, per md-standards.md 5.1. Only `# ` and `## ` end a
  # section -- the same boundary the heading walker uses -- so a `###` subheading stays inside it.
  awk -v h="$2" 'index($0,h)==1 && !inside { inside=1; next }
                 inside && /^(# |## )/ { exit }
                 inside && NF { found=1; exit }
                 END { exit found ? 0 : 1 }' "$1"
}

denial_log_ignored() { # true if either .gitignore covers .agents/.log/, in any spelling
  # Both files are consumer-owned and committed, so either one ignores the log for every clone.
  # An earlier `init` wrote `.log/` into .agents/.gitignore, which this still accepts.
  grep -qxE '/?\.agents/(\.log/?)?' .gitignore 2>/dev/null ||
    grep -qxE '/?\.log/?' .agents/.gitignore 2>/dev/null
}

lint() {
  [ -f AGENTS.md ] || bad "AGENTS.md missing at root (write it with the agents-md skill)"
  [ -f REVIEW.md ] || bad "REVIEW.md missing at root (write it with the review-md skill)"
  [ -f .claude/CLAUDE.md ] || bad ".claude/CLAUDE.md missing"
  [ -f CLAUDE.md ] && bad "./CLAUDE.md exists; only .claude/CLAUDE.md is allowed"
  head -n1 .claude/CLAUDE.md 2>/dev/null | grep -qx '@../AGENTS.md' || bad ".claude/CLAUDE.md must start with a bare '@../AGENTS.md' line"
  for f in AGENTS.md REVIEW.md; do [ -f $f ] && grep -q '<!--' $f && bad "$f contains HTML comments"; done
  [ -f REVIEW.md ] && grep -qi '^## How to write a review' REVIEW.md && bad "REVIEW.md restates review style"
  # Section order, per md-standards.md §5.1. Guarded on existence so a missing file is
  # reported once above rather than once per sub-check.
  if [ -f AGENTS.md ]; then
    local want=("# " "## Environments" "## Non-obvious commands" "## AWS access" "## What a merge reaches" "## Traps" "## Cross-repo coupling" "## Enforced automatically" "## Further reading")
    local got=() idx line pos i w
    # Not `mapfile`: that is bash 4+, and macOS still ships 3.2 as /bin/bash. Under it the array
    # stayed empty and every heading check reported a bogus failure.
    while IFS= read -r line; do got+=("$line"); done < <(grep -E '^(# |## )' AGENTS.md)
    # One walk answers both "is this heading allowed" and "is it in order": the allowed-check
    # already finds the heading's position, so order compares positions rather than advancing a
    # cursor that one stray section would run to the end of the list.
    idx=0
    for h in ${got[@]+"${got[@]}"}; do
      pos=-1; i=0
      for w in "${want[@]}"; do
        case "$h" in "$w"*) pos=$i; break;; esac
        i=$((i+1))
      done
      if [ "$pos" -lt 0 ]; then
        bad "AGENTS.md heading not allowed: '$h'"
      elif [ "$pos" -lt "$idx" ]; then
        bad "AGENTS.md heading out of order: '$h'"
      else
        idx=$((pos+1))
      fi
    done
    # md-standards.md 5.1 carves out `## Environments` for a repo with no deploy targets. No
    # check can make that judgement, so it is declared in .agents/config.env; silence requires it.
    local required=("## Environments" "## Traps" "## Further reading")
    # Same tolerance as helpers/event.py:load_config, which strips spaces and quotes, because
    # config.env is hand-edited.
    if grep -qE '^[[:space:]]*AGENTS_MD_NO_ENVIRONMENTS[[:space:]]*=[[:space:]]*["'"'"']?1["'"'"']?[[:space:]]*$' \
       .agents/config.env 2>/dev/null; then
      grep -q '^## Environments' AGENTS.md &&
        bad "AGENTS.md has '## Environments' but .agents/config.env declares AGENTS_MD_NO_ENVIRONMENTS=1"
      required=("## Traps" "## Further reading")
    fi
    for req in "${required[@]}"; do
      if ! grep -q "^$req" AGENTS.md; then
        bad "AGENTS.md missing required section $req"
      elif ! section_has_body AGENTS.md "$req"; then
        bad "AGENTS.md section $req is empty (required means present and non-empty)"
      fi
    done
  fi
  # REVIEW.md is a title plus those two sections and nothing else (md-standards.md §5.3).
  # Anything more spends the reviewer's shared byte budget on every PR; it belongs in a skill.
  if [ -f REVIEW.md ]; then
    local want2=("# " "## What to flag" "## What not to flag")
    local got2=() idx2 line2 pos2 i2 w2
    while IFS= read -r line2; do got2+=("$line2"); done < <(grep -E '^(# |## )' REVIEW.md)
    idx2=0
    for h in ${got2[@]+"${got2[@]}"}; do
      pos2=-1; i2=0
      for w2 in "${want2[@]}"; do
        case "$h" in "$w2"*) pos2=$i2; break;; esac
        i2=$((i2+1))
      done
      if [ "$pos2" -lt 0 ]; then
        bad "REVIEW.md heading not allowed: '$h' — REVIEW.md is only 'What to flag' / 'What not to flag'; move narrative or evidence content to a skill (md-standards.md §5.3)"
      elif [ "$pos2" -lt "$idx2" ]; then
        bad "REVIEW.md heading out of order: '$h'"
      else
        idx2=$((pos2+1))
      fi
    done
  fi
  # nested pairs
  while IFS= read -r a; do d=$(dirname "$a"); [ "$d" = . ] && continue
    if [ -f "$d/CLAUDE.md" ] && head -n1 "$d/CLAUDE.md" | grep -qx '@AGENTS.md'; then
      :
    else
      bad "$d has AGENTS.md without a CLAUDE.md containing only @AGENTS.md"
    fi
  done < <(find . -name AGENTS.md -not -path './node_modules/*' -not -path "./$CFG/*" -not -path './.agents/*')
  while IFS= read -r c; do
    d=$(dirname "$c"); [ "$d" = . ] && continue  # root CLAUDE.md/AGENTS.md are their own checks above
    [ -f "$d/AGENTS.md" ] || bad "$d has CLAUDE.md without AGENTS.md"
  done < <(find . -name CLAUDE.md -not -path './.claude/*' -not -path './node_modules/*' -not -path "./$CFG/*" -not -path './.agents/*')

  # D10 contract: root lefthook.yml extends the vendored one
  if [ -f lefthook.yml ]; then
    grep -qF "$CFG/lefthook.yml" lefthook.yml || bad "lefthook.yml must contain 'extends: [$CFG/lefthook.yml]'"
  else
    bad "lefthook.yml missing at root"
  fi

  # The denial log holds refused commands verbatim, so an inline secret in one is one
  # `git add -A` from being committed.
  denial_log_ignored || bad "the denial log is not ignored; it records commands verbatim \
(run: $CFG/verification.sh init)"

  # D12: every MANDATORY hook registered on its event in both tools, every registered name
  # resolving. Reached through `run` so the launcher's sys.path handling isn't duplicated.
  if [ -x "$CFG/hooks/agent/run" ]; then
    bash "$CFG/hooks/agent/run" check-registration .claude/settings.json .codex/hooks.json \
      || bad "hook registration contract failed (see FAIL lines above)"
  else
    bad "$CFG/hooks/agent/run missing or not executable"
  fi

  # Every vendored skill is registered as a stub in both tools, and the stub still matches the
  # skill it points at. Existence alone is not enough: the description is the trigger, so a stub
  # left behind by a renamed or reworded skill is a skill that silently stops firing.
  if [ -d "$CFG/skills" ]; then
    local name p sd
    for sd in "$CFG"/skills/*/; do
      [ -d "$sd" ] || continue
      sd=$(basename "$sd")
      [ "$sd" = "_shared" ] && continue
      [ -f "$CFG/skills/$sd/SKILL.md" ] || bad "$CFG/skills/$sd/ has no SKILL.md"
    done
    while IFS= read -r name; do
      [ -n "$name" ] || continue
      check_frontmatter "$name" || continue
      local body; body=$(stub_body "$name")
      for p in ".claude/skills/$name/SKILL.md" ".agents/skills/$name/SKILL.md"; do
        if [ ! -f "$p" ]; then
          bad "$p is missing (run: $CFG/verification.sh stubs)"
        elif ! printf '%s\n' "$body" | diff -q - "$p" >/dev/null; then
          bad "$p does not match $CFG/skills/$name/SKILL.md (run: $CFG/verification.sh stubs)"
        fi
      done
    done < <(skill_names)
  fi

  # The vendored tree must stay owned by the team that ships it. Nothing else detects this: a
  # consumer onboarded before the ownership block existed keeps the old shape until someone
  # re-runs `init`, and every other check here would stay green.
  local owners=""
  for f in .github/CODEOWNERS CODEOWNERS docs/CODEOWNERS; do
    [ -f "$f" ] && { owners=$f; break; }
  done
  if [ -z "$owners" ]; then
    bad "no CODEOWNERS (run: $CFG/verification.sh init)"
  else
    grep -qF 'dpe-agent-config: ownership' "$owners" \
      || bad "$owners has no repo-wide owner block (run: $CFG/verification.sh init)"
    # Last match wins, so the vendored line must also be the last owner line in the file.
    local last; last=$(grep -vE '^[[:space:]]*(#|$)' "$owners" | tail -n1)
    case "$last" in
      "/$CFG/"[[:space:]]*) ;;
      *) bad "$owners must end with the '/$CFG/' owner line, or a later pattern shadows it (run: $CFG/verification.sh init)";;
    esac
  fi

  # D12: a local rule needs a test file, same convention as the catalog
  if [ -d .agents/rules ]; then
    for f in .agents/rules/*.py; do
      [ -e "$f" ] || continue
      base=$(basename "$f" .py)
      [ -f ".agents/rules/tests/test_${base}.py" ] || bad ".agents/rules/${base}.py has no test file (.agents/rules/tests/test_${base}.py)"
    done
  fi
}

drift() {
  # Only a vendored copy can drift; the source repo is the reference.
  if [ "$VENDORED" = 0 ]; then
    echo "drift: n/a — $CFG/ is the source of truth in this repo, not a vendored copy"
    return
  fi
  local want got
  want=$(cat "$CFG/CHECKSUM" 2>/dev/null) || { bad "$CFG/CHECKSUM missing"; return; }
  got=$(checksum "$CFG")
  [ "$want" = "$got" ] || bad "$CFG/ has drifted from $(cat "$CFG/VERSION" 2>/dev/null); re-sync, do not edit locally"
}

vendor_paths() { # rewrite a freshly written file's vendored-directory references
  # Templates name ".dpe-agent-config/", correct wherever they ship. Repoint them when this
  # directory is called something else. A no-op in a consumer. CODEOWNERS needs it too.
  [ "$VENDORED" = 0 ] || return 0
  [ -f "$1" ] || return 0
  sed -i.bak "s|\.dpe-agent-config/|$CFG/|g" "$1" && rm -f "$1.bak"
}

copy_if_absent() { # src dest; returns 0 if it wrote the file, 1 if it existed or the copy failed
  if [ -e "$2" ]; then
    echo "skip (exists): $2"
    return 1
  fi
  # Both the source and cp's exit status are checked: this printed "wrote:" unconditionally
  # once, so an init that copied nothing still reported success and exited 0.
  if [ ! -f "$1" ]; then
    bad "template missing: $1 (cannot write $2)"
    return 1
  fi
  mkdir -p "$(dirname "$2")"
  if ! cp "$1" "$2"; then
    bad "could not write $2 from $1"
    return 1
  fi
  vendor_paths "$2"
  echo "wrote: $2"
  return 0
}

skill_names() { # every skill shipped in the vendored catalog, one per line
  local d
  for d in "$CFG"/skills/*/; do
    [ -d "$d" ] || continue
    d=$(basename "$d")
    [ "$d" = "_shared" ] && continue
    # Silently skipped, not reported: this runs inside a process substitution, so anything on
    # stdout is read back as a skill name and a bad() here would set $fail in a subshell that is
    # then discarded. lint() checks the same condition itself, where it can be recorded.
    [ -f "$CFG/skills/$d/SKILL.md" ] || continue
    echo "$d"
  done
}

check_frontmatter() { # name; reports its own problems. Must run OUTSIDE a command
  # substitution: bad() sets $fail, and a subshell's copy of it is discarded.
  local src="$CFG/skills/$1/SKILL.md"
  if [ -z "$(sed -n 's/^description: //p' "$src" | head -n1)" ]; then
    bad "$src has no 'description:' in its frontmatter"
    return 1
  fi
  # Only the first line is ever read, so a wrapped or folded description would be truncated into
  # the stub -- and the byte comparison could not catch it, because it regenerates through this
  # same path and both sides would truncate alike.
  if sed -n '/^description: /{n;p;}' "$src" | grep -q '^[[:space:]]'; then
    bad "$src: 'description:' spans more than one line; keep it on one so the stub carries it whole"
    return 1
  fi
  return 0
}

stub_body() { # name; the stub both tools get, byte-identical, on stdout. Frontmatter already
  # validated by check_frontmatter -- this runs in a subshell and cannot report anything.
  local name=$1 desc
  desc=$(sed -n 's/^description: //p' "$CFG/skills/$name/SKILL.md" | head -n1)
  cat <<EOF
---
name: $name
description: $desc
---

Read \`$CFG/skills/$name/SKILL.md\` and follow it. That file carries the procedure and the
template the finished file starts from; this stub only routes to it.

Two tests gate every line that goes into a startup-loaded context file, whatever else you read:

- **Not derivable from source** — could an agent reach this by reading the source tree?
- **Globally relevant** — is it needed on ~every task in this repo?

A candidate failing either test does not go in the file. Route it instead — the routing table is
in the skill.

Generated by \`$CFG/verification.sh stubs\`. Edit the skill upstream, not this file.
EOF
}

stubs() { # (re)write both tools' stubs from the vendored skills; the one command that overwrites
  local name
  while IFS= read -r name; do
    [ -n "$name" ] || continue
    check_frontmatter "$name" || continue
    local body; body=$(stub_body "$name")
    local p
    for p in ".claude/skills/$name/SKILL.md" ".agents/skills/$name/SKILL.md"; do
      mkdir -p "$(dirname "$p")"
      printf '%s\n' "$body" > "$p" || { bad "could not write $p"; continue; }
      echo "wrote: $p"
    done
  done < <(skill_names)
}

init() { # writes consumer-owned files only when absent; never overwrites
  copy_if_absent "$CFG"/templates/claude-settings.json .claude/settings.json
  copy_if_absent "$CFG"/templates/codex-hooks.json .codex/hooks.json
  copy_if_absent "$CFG"/templates/lefthook.yml lefthook.yml
  copy_if_absent "$CFG"/templates/reviewflow.yml .reviewflow.yml
  # AGENTS.md and REVIEW.md are deliberately NOT written here: their content *is* the work, and a
  # placeholder file passes the shape check while saying nothing. The skills author them.
  if [ ! -f .claude/CLAUDE.md ]; then
    mkdir -p .claude
    cat > .claude/CLAUDE.md <<'EOF'
@../AGENTS.md

That import is load-bearing: Claude Code reads `CLAUDE.md`, not `AGENTS.md`, so without it
nothing above reaches a session.
EOF
    echo "wrote: .claude/CLAUDE.md"
  else
    echo "skip (exists): .claude/CLAUDE.md"
  fi
  stubs
  mkdir -p .agents/rules
  if [ ! -f .agents/config.env ]; then
    cat > .agents/config.env <<'EOF'
# Config read by the agent hooks, as NAME=value lines. Uncomment what this repo needs.
EOF
    echo "wrote: .agents/config.env"
  fi
  if [ ! -f .agents/.gitignore ]; then printf '__pycache__/\n.pytest_cache/\n' > .agents/.gitignore; echo "wrote: .agents/.gitignore"; fi
  # The denial log records each refused command verbatim, which is where an inline secret would
  # be. `lint` checks the same line.
  if ! denial_log_ignored; then
    # A .gitignore whose last line has no newline would otherwise absorb the appended pattern.
    [ -s .gitignore ] && [ -n "$(tail -c 1 .gitignore)" ] && printf '\n' >> .gitignore
    printf '/.agents/.log/\n' >> .gitignore
    echo "appended: .gitignore <- /.agents/.log/"
  fi
  # GitHub reads the FIRST of .github/, root, docs/ -- so writing a new .github/CODEOWNERS in a
  # repo whose ownership lives in docs/ would outrank theirs and silently disable every
  # per-directory owner they had. Edit the file they already use.
  local codeowners=.github/CODEOWNERS
  [ -f CODEOWNERS ] && [ ! -f .github/CODEOWNERS ] && codeowners=CODEOWNERS
  [ -f docs/CODEOWNERS ] && [ ! -f .github/CODEOWNERS ] && [ ! -f CODEOWNERS ] && codeowners=docs/CODEOWNERS
  if [ ! -f "$CFG/CODEOWNERS.snippet" ]; then
    bad "template missing: $CFG/CODEOWNERS.snippet (cannot write $codeowners)"
  else
    # The team is named once, by the snippet's `*` line, and the vendored-directory line is
    # derived from it -- the two can never drift into naming different owners.
    local owner; owner=$(awk '$1 == "*" { print $2; exit }' "$CFG/CODEOWNERS.snippet")
    if [ -z "$owner" ]; then
      bad "$CFG/CODEOWNERS.snippet has no '*' owner line"
    else
      mkdir -p "$(dirname "$codeowners")"
      [ -f "$codeowners" ] || : > "$codeowners"
      if ! grep -qF 'dpe-agent-config: ownership' "$codeowners"; then
        # Prepended, never appended: CODEOWNERS gives precedence to the LAST matching pattern, so
        # a trailing `*` would silently take every path this repo had already assigned elsewhere.
        # The subshell is what makes a failed read fail the write -- a brace group returns the
        # last command's status, so a missing snippet still produced a .tmp and a "prepended"
        # line with no owner in the file.
        if ( cat "$CFG/CODEOWNERS.snippet" || exit 1
             if [ -s "$codeowners" ]; then printf '\n' && cat "$codeowners"; fi
           ) > "$codeowners.tmp" && mv "$codeowners.tmp" "$codeowners"; then
          vendor_paths "$codeowners"
          echo "prepended: $codeowners"
        else
          rm -f "$codeowners.tmp"
          bad "could not update $codeowners"
        fi
      fi
      # Last line of the file, deliberately: a consumer whose CODEOWNERS opens with its own `*`
      # would otherwise own the vendored tree, since last match wins.
      # Moved, not just appended: a consumer who adds an owner line after it shadows the
      # vendored tree, and lint's remedy is this command -- which would have been a no-op,
      # leaving a permanent FAIL nobody could clear.
      local vendored_line="/$CFG/  $owner"
      if [ "$(grep -vE '^[[:space:]]*(#|$)' "$codeowners" | tail -n1)" != "$vendored_line" ]; then
        if { grep -vxF "$vendored_line" "$codeowners" || true; } > "$codeowners.tmp" \
           && mv "$codeowners.tmp" "$codeowners" \
           && printf '\n%s\n' "$vendored_line" >> "$codeowners"; then
          echo "owner of /$CFG/ moved to the end of $codeowners"
        else
          rm -f "$codeowners.tmp"
          bad "could not move the vendored owner line to the end of $codeowners"
        fi
      fi
    fi
  fi
  # A repo-wide formatter and a checksummed directory cannot both win. prettier's default glob
  # reaches into the vendored tree, so `lint` fails on it and `lint --write` rewrites the bytes
  # `drift` compares against CHECKSUM -- red either way, with no formatting that satisfies both.
  # Only touched when the repo already uses the tool.
  local ign
  # Consumers only. In the source repo CFG is `shared/`, and appending that would silently turn
  # its own `prettier --check` into a pass over nothing -- while `drift` there is already "n/a",
  # so the entry buys nothing either. An `if`, not an early return: everything below is still
  # part of init -- the chmod, the fail check, the lint report and the handoff banner.
  if [ "$VENDORED" = 1 ]; then
  for ign in .prettierignore .eslintignore .stylelintignore; do
    case "$ign" in
      .prettierignore)
        # Every config form prettier accepts, plus the package.json key. Matching only three
        # spellings left the rest of the fleet red with nothing appended.
        # Tested one at a time: `ls a b` exits non-zero when ANY operand is missing, so a repo
        # with only prettier.config.mjs read as having no prettier at all.
        local cfg has_cfg=0
        for cfg in .prettierrc .prettierrc.* prettier.config.*; do
          [ -e "$cfg" ] && { has_cfg=1; break; }
        done
        [ "$has_cfg" = 1 ] || grep -q '"prettier"' package.json 2>/dev/null || continue;;
      .eslintignore)
        # Flat config first, and regardless of whether a leftover .eslintignore is lying around:
        # ESLint 9 does not read that file, so a repo mid-migration would get "appended" and stay
        # red -- the "looks fixed, changes nothing" case this is meant to avoid.
        local esl
        for esl in eslint.config.*; do
          [ -e "$esl" ] || continue
          echo "note: eslint flat config detected; add '$CFG/' to \`ignores\` in $esl yourself"
          break
        done
        [ -e "$esl" ] && continue
        [ -f "$ign" ] || continue;;
      *) [ -f "$ign" ] || continue;;
    esac
    if [ -f "$ign" ] && grep -qxF "$CFG/" "$ign"; then
      continue
    fi
    # A file with no trailing newline would glue the entry onto the last pattern -- `dist`
    # becomes `dist.dpe-agent-config/`, un-ignoring what `dist` covered and leaving the vendored
    # tree formatted anyway. Same guard the CODEOWNERS append uses.
    if [ -s "$ign" ] && [ -n "$(tail -c1 "$ign")" ]; then printf '\n' >> "$ign"; fi
    if printf '%s\n' "$CFG/" >> "$ign"; then
      echo "appended: $ign ($CFG/ is checksummed; formatting it breaks drift)"
    else
      bad "could not append $CFG/ to $ign"
    fi
  done
  fi

  chmod +x "$CFG"/hooks/agent/run "$CFG"/hooks/agent/test-hooks.sh \
    "$CFG"/verification.sh "$CFG"/hooks/git/*.sh 2>/dev/null || true
  if [ "$fail" != 0 ]; then
    echo "init INCOMPLETE — see the FAIL lines above; nothing further was written"
    return
  fi
  echo "init complete — run: lefthook install"
  local bar; bar=$(printf '=%.0s' $(seq 1 80))
  echo
  echo "$bar"
  # The mechanical files are written. What is left is the content only this repo knows, so init
  # stops here and hands the job to an agent rather than dropping a placeholder that would pass
  # the shape check while saying nothing.
  local verb="create"
  { [ -f AGENTS.md ] || [ -f REVIEW.md ]; } && verb="update"
  local findings; findings=$( ( lint ) 2>&1 )
  if [ -n "$findings" ]; then
    echo "lint:"
    printf '%s\n' "$findings" | sed 's/^/  /'
  else
    echo "lint: clean"
  fi
  echo
  echo "Next — paste this into Claude Code or Codex, in this repo:"
  echo
  echo "  Use the agents-md skill to $verb AGENTS.md for this repo, then the review-md skill"
  echo "  to $verb REVIEW.md. Run $CFG/verification.sh lint after each and fix"
  echo "  every finding before you finish. Ask me anything that only lives in someone's head."
  echo "$bar"
}

probe() {
  echo "Obedience probe — run manually in an agent session:"
  echo "  1. Ask: 'What is 2+2?'  → reply must end with the token from AGENTS.md → Further reading."
  echo "  2. Ask the agent to read packages/foo/<file>, then ask again → token must switch to the nested one (Claude Code) or stay (Codex started at root)."
  echo "  3. Check .agents/.log/instructions-loaded.jsonl for the nested load (Claude Code)."
}

case "${1:-}" in
  lint) lint;;
  drift) drift;;
  checksum) checksum "${2:-$CFG}";;
  init) init;;
  stubs) stubs;;
  probe) probe;;
  *) echo "usage: $0 lint|drift|checksum|init|stubs|probe"; exit 1;;
esac
exit $fail
