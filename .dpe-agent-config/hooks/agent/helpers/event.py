from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, TextIO


@dataclass
class Event:
    tool_name: str
    command: str
    cwd: str
    raw: dict[str, Any]

def repo_root(cwd: str) -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd,
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return cwd

def read(stream: TextIO = sys.stdin) -> Event | None:
    """Return None when the event is unparseable; callers decide fail-open/closed."""
    try:
        raw = json.load(stream)
    except Exception:
        return None
    tool = str(raw.get("tool_name", ""))
    ti = raw.get("tool_input") or {}
    cmd = ti.get("command") if isinstance(ti, dict) else None
    return Event(tool, cmd if isinstance(cmd, str) else "", raw.get("cwd") or os.getcwd(), raw)

def load_config(root: str) -> dict[str, str]:
    cfg: dict[str, str] = {}
    p = os.path.join(root, ".agents", "config.env")
    # config.env is consumer-owned and hand-edited. A stray non-UTF-8 byte used to raise here,
    # before any rule ran, and the traceback exited 1 -- which does not block. Unreadable config
    # degrades to no config; it is convenience data, never the safety decision itself.
    try:
        if os.path.exists(p):
            with open(p, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        cfg[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    cfg.update({k: v for k, v in os.environ.items() if k.startswith("AGENT_")})
    return cfg
