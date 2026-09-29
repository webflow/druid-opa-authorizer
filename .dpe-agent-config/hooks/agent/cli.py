from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType

from catalog import CATALOG, REQUIRED_ATTRS
from helpers import event as ev
from helpers import policy
from helpers.registry import covers, launcher_problem, registered

USAGE = (
    "usage: run <name>|list|stats|mandatory|resolve <name>|check-registration <claude> <codex>\n"
    "       (names: " + ", ".join(sorted(CATALOG)) + ", or a local .agents/rules/<name>.py)"
)


def _local_path(root: str, name: str) -> str:
    return os.path.join(root, ".agents", "rules", name.replace("-", "_") + ".py")


def load_local(root: str, name: str) -> ModuleType | None:
    """Load a consumer-authored `.agents/rules/<name>.py`. Same module shape as the catalog."""
    path = _local_path(root, name)
    if not os.path.isfile(path):
        return None
    module_name = "_agent_local_hook_" + name.replace("-", "_")
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    missing = [a for a in REQUIRED_ATTRS if not hasattr(module, a)]
    if missing:
        raise AttributeError(f"local rule {path} is missing {missing}")
    return module


def _cmd_list(root: str) -> int:
    header = f"{'NAME':<20} {'EVENT':<18} {'MANDATORY':<10} {'SOURCE':<8} DESCRIPTION"
    print(header)
    for entry in sorted(CATALOG.values(), key=lambda e: e.name):
        print(
            f"{entry.name:<20} {entry.event:<18} {str(entry.mandatory):<10} "
            f"{'central':<8} {entry.description}"
        )
    rules_dir = os.path.join(root, ".agents", "rules")
    if not os.path.isdir(rules_dir):
        return 0
    for fname in sorted(os.listdir(rules_dir)):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        name = fname[:-3].replace("_", "-")
        try:
            module = load_local(root, name)
        except Exception as exc:  # noqa: BLE001 - surfacing any local-module load error to the operator
            print(f"{name:<20} <failed to load: {exc}>", file=sys.stderr)
            continue
        if module is None:
            continue
        print(
            f"{module.NAME:<20} {module.EVENT:<18} {str(module.MANDATORY):<10} "
            f"{'local':<8} {module.DESCRIPTION}"
        )
    return 0


def _cmd_stats(root: str) -> int:
    path = os.path.join(root, ".agents", ".log", "denials.jsonl")
    counts: dict[str, int] = {}
    allowed: dict[str, int] = {}
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                rule = row.get("rule", "?")
                # Rows predating the field are denials; only an explicit "allow" is one.
                bucket = allowed if row.get("decision") == "allow" else counts
                bucket[rule] = bucket.get(rule, 0) + 1
    if not counts and not allowed:
        print("no denials recorded")
        return 0
    for name, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"{count:>6}  {name}")
    if allowed:
        # Not denials: the rule could not be reached and its fail-open policy let the command
        # through. A steady count here is a broken hook, not a well-behaved agent.
        print("\nallowed after the rule could not be reached (fail-open):")
        for name, count in sorted(allowed.items(), key=lambda kv: -kv[1]):
            print(f"{count:>6}  {name}")
    return 0


def _cmd_mandatory() -> int:
    for entry in sorted(CATALOG.values(), key=lambda e: e.name):
        if entry.mandatory:
            print(f"{entry.name} {entry.event}")
    return 0


def _cmd_resolve(root: str, name: str) -> int:
    if name in CATALOG:
        return 0
    try:
        local = load_local(root, name)
    except Exception as exc:
        print(f"{name}: {exc}", file=sys.stderr)
        return 1
    return 0 if local is not None else 1


def _check_one(root: str, tool: str, path_str: str, problems: list[str]) -> None:
    path = Path(root) / path_str
    if not path.is_file():
        problems.append(f"{tool}: {path_str} is missing")
        return
    try:
        reg = registered(path)
    except Exception as exc:
        problems.append(f"{tool}: {path_str} could not be parsed: {exc}")
        return
    for entry in CATALOG.values():
        if not entry.mandatory:
            continue
        # Any registration group whose matcher covers the declared tool counts, not only one
        # whose composed key is spelled identically.
        if not any(entry.name in names and covers(key, entry.event)
                   for key, names in reg.items()):
            problems.append(
                f"{tool}: {path_str} is missing the mandatory hook '{entry.name}' "
                f"on event '{entry.event}'"
            )
    for names in reg.values():
        for name, (launcher, interpreter) in names.items():
            if _cmd_resolve(root, name) != 0:
                problems.append(f"{tool}: {path_str} registers unresolved hook '{name}'")
            problem = launcher_problem(launcher, root, interpreter)
            if problem is not None:
                problems.append(f"{tool}: {path_str} hook '{name}': {problem}")


def _cmd_check_registration(root: str, claude_path: str, codex_path: str) -> int:
    problems: list[str] = []
    _check_one(root, "claude", claude_path, problems)
    _check_one(root, "codex", codex_path, problems)
    for p in problems:
        print(f"FAIL: {p}", file=sys.stderr)
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) == 1 and argv[0] == "list":
        return _cmd_list(ev.repo_root(os.getcwd()))
    if len(argv) == 1 and argv[0] == "stats":
        return _cmd_stats(ev.repo_root(os.getcwd()))
    if len(argv) == 1 and argv[0] == "mandatory":
        return _cmd_mandatory()
    if len(argv) == 2 and argv[0] == "resolve":
        return _cmd_resolve(ev.repo_root(os.getcwd()), argv[1])
    if len(argv) == 3 and argv[0] == "check-registration":
        return _cmd_check_registration(ev.repo_root(os.getcwd()), argv[1], argv[2])
    if len(argv) != 1:
        print(USAGE, file=sys.stderr)
        return 1

    name = argv[0]
    # Everything from here to the decision is wrapped, because only exit 2 blocks and an escaped
    # exception exits 1. An unresolvable *name* stays a usage error: that is a registration bug.
    try:
        e = ev.read()
        root = ev.repo_root(e.cwd if e else os.getcwd())
        cfg = ev.load_config(root)

        entry = CATALOG.get(name)
        if entry is not None:
            return policy.run(name, entry.rule, e, cfg, root, entry.event)

        try:
            local = load_local(root, name)
        except Exception as exc:
            print(f"{name}: could not load .agents/rules/ module: {exc}", file=sys.stderr)
            why = f"its module failed to load: {exc}"
            return _decide(policy.fallback(name, why, root), name, why)
        if local is None:
            print(USAGE, file=sys.stderr)
            return 1
        return policy.run(name, local.rule, e, cfg, root, local.EVENT)
    except Exception as exc:  # noqa: BLE001 - never let the launcher see an exit code that allows
        why = f"the hook raised {type(exc).__name__}: {exc}"
        return _decide(policy.fallback(name, why, _safe_root()), name, why)


def _safe_root() -> str | None:
    """Best-effort repo root for logging. This runs on a path where something already failed."""
    try:
        return ev.repo_root(os.getcwd())
    except Exception:
        return None


def _decide(d: policy.Decision, name: str = "", why: str = "") -> int:
    if d.allow:
        return 0
    print(d.reason, file=sys.stderr)
    root = _safe_root()
    if root is not None and name:
        policy.log(root, name, None, f"fallback denial: {why}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
