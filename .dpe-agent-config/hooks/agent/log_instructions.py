from __future__ import annotations

import json
import os
import time

from helpers import event as ev
from helpers.policy import ALLOW, Decision

NAME = "log-instructions"
EVENT = "InstructionsLoaded"
DESCRIPTION = "Claude Code only. Appends every InstructionsLoaded event to prove on-demand loads."
MANDATORY = False


def rule(event: ev.Event, cfg: dict[str, str], root: str) -> Decision:
    del cfg
    d = os.path.join(root, ".agents", ".log")
    os.makedirs(d, exist_ok=True)
    line = time.strftime("%Y-%m-%dT%H:%M:%SZ ", time.gmtime()) + json.dumps(event.raw)
    with open(os.path.join(d, "instructions-loaded.jsonl"), "a", encoding="utf-8") as f:
        f.write(line + "\n")
    return ALLOW
