"""Load and cross-validate the broker registry."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path

import yaml
from pydantic import ValidationError

from mrclean.errors import MRcleanError
from mrclean.registry.schema import Broker

log = logging.getLogger(__name__)

BROKERS_DIR = Path(__file__).parent / "brokers"


class RegistryError(MRcleanError):
    """One or more registry entries are invalid. ``problems`` lists each one."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__(f"{len(problems)} registry problem(s):\n" + "\n".join(problems))


def _load_file(path: Path) -> Broker:
    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, Mapping):
        raise ValueError("top level must be a mapping")
    broker = Broker.model_validate(raw)
    if broker.id != path.stem:
        raise ValueError(f"id {broker.id!r} must match the filename {path.stem!r}")
    return broker


def load_registry(directory: Path = BROKERS_DIR) -> dict[str, Broker]:
    """Load every ``*.yaml`` in ``directory``.

    All problems are collected and raised together, so one run of
    ``mrclean registry validate`` shows everything that needs fixing.
    """
    brokers: dict[str, Broker] = {}
    problems: list[str] = []
    for path in sorted(directory.glob("*.yaml")):
        try:
            broker = _load_file(path)
        except (OSError, yaml.YAMLError, ValidationError, ValueError) as exc:
            problems.append(f"{path.name}: {exc}")
            continue
        brokers[broker.id] = broker

    for broker in brokers.values():
        if broker.parent and broker.parent not in brokers:
            problems.append(f"{broker.id}.yaml: parent {broker.parent!r} is not in the registry")
    if problems:
        raise RegistryError(problems)
    log.debug("Loaded %d brokers", len(brokers))
    return brokers


def execution_order(brokers: Mapping[str, Broker]) -> list[Broker]:
    """Parents before children, then by priority, then by id (deterministic)."""
    depth: dict[str, int] = {}

    def _depth(b: Broker, seen: frozenset[str] = frozenset()) -> int:
        if b.id in seen:
            raise RegistryError([f"{b.id}.yaml: parent cycle via {sorted(seen)}"])
        if b.id not in depth:
            depth[b.id] = 0 if not b.parent else 1 + _depth(brokers[b.parent], seen | {b.id})
        return depth[b.id]

    return sorted(brokers.values(), key=lambda b: (_depth(b), b.priority, b.id))
