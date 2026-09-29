from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import aws_readonly
import block_rm
import infra_readonly
import log_instructions
import pr_body
from helpers import event as ev
from helpers.policy import Decision

_MODULES = (aws_readonly, infra_readonly, block_rm, log_instructions, pr_body)
REQUIRED_ATTRS = ("NAME", "EVENT", "DESCRIPTION", "MANDATORY", "rule")


@dataclass(frozen=True)
class CatalogEntry:
    name: str
    event: str
    description: str
    mandatory: bool
    rule: Callable[[ev.Event, dict[str, str], str], Decision]


def _build() -> dict[str, CatalogEntry]:
    catalog: dict[str, CatalogEntry] = {}
    for module in _MODULES:
        missing = [a for a in REQUIRED_ATTRS if not hasattr(module, a)]
        if missing:
            raise AttributeError(f"catalog module {module.__name__} is missing {missing}")
        entry = CatalogEntry(
            name=module.NAME,
            event=module.EVENT,
            description=module.DESCRIPTION,
            mandatory=module.MANDATORY,
            rule=module.rule,
        )
        if entry.name in catalog:
            raise ValueError(f"duplicate catalog NAME: {entry.name!r}")
        catalog[entry.name] = entry
    return catalog


CATALOG: dict[str, CatalogEntry] = _build()
