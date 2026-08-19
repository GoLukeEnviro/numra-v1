"""Loads and validates the NUMRA `knowledge/` tree into typed pydantic models.

Deliberately takes an explicit `knowledge_root: Path` rather than assuming a fixed
location relative to the current working directory — this package must work whether
invoked from the repo root, from inside `packages/engine-interpretation`, or bundled
into a deployed artifact with its own layout.

No calculation logic lives here: this module only parses and validates YAML content.
"""

from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]  # PyYAML ships no py.typed/stub in this repo's dependency set
from pydantic import ValidationError

from numra_interpretation.errors import KnowledgeLoadError
from numra_interpretation.knowledge_models import (
    KarmicDebtKnowledge,
    KnowledgeManifest,
    MetricKnowledge,
    NumberKnowledge,
)

__all__ = ["KnowledgeBase", "KnowledgeLoader", "load_knowledge_base"]


class KnowledgeBase:
    """In-memory, validated view of the whole `knowledge/` tree.

    Lookups are by the natural key (number value, karmic-debt compound like
    ``"13/4"``, metric id) rather than by filename, so callers never need to know the
    on-disk layout.
    """

    def __init__(
        self,
        manifest: KnowledgeManifest,
        numbers: dict[int, NumberKnowledge],
        karmic_debts: dict[str, KarmicDebtKnowledge],
        metrics: dict[str, MetricKnowledge],
    ) -> None:
        self.manifest = manifest
        self._numbers = numbers
        self._karmic_debts = karmic_debts
        self._metrics = metrics

    def number(self, value: int) -> NumberKnowledge:
        """Look up a 1-9 number or a preserved master number (11/22/33).

        Raises :class:`KeyError` if ``value`` has no knowledge file — callers should
        treat that as a hard failure (no silent fallback to another number).
        """
        try:
            return self._numbers[value]
        except KeyError:
            raise KeyError(f"No NUMRA knowledge entry for number {value!r}") from None

    def karmic_debt(self, compound: str) -> KarmicDebtKnowledge | None:
        """Look up karmic-debt knowledge by compound display value (e.g. ``"13/4"``).

        Returns ``None`` (not an error) for any compound outside the recognized
        allowlist {13/4, 14/5, 16/7, 19/1} — per canon-spec.md §21 only those four are
        ever flagged, so an absent lookup is an expected, non-exceptional case.
        """
        return self._karmic_debts.get(compound)

    def metric(self, metric_id: str) -> MetricKnowledge:
        """Look up semantic context for a metric id (e.g. ``"life_path"``).

        Raises :class:`KeyError` if unknown — callers should treat that as a hard
        failure.
        """
        try:
            return self._metrics[metric_id]
        except KeyError:
            raise KeyError(f"No NUMRA knowledge entry for metric_id {metric_id!r}") from None

    @property
    def known_metric_ids(self) -> frozenset[str]:
        return frozenset(self._metrics)


def _load_yaml_file(path: Path) -> dict[str, object]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise KnowledgeLoadError(f"Could not read knowledge file {path}: {exc}") from exc

    try:
        loaded = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise KnowledgeLoadError(f"Invalid YAML in knowledge file {path}: {exc}") from exc

    if not isinstance(loaded, dict):
        raise KnowledgeLoadError(
            f"Knowledge file {path} must contain a YAML mapping at the top level, "
            f"got {type(loaded).__name__}"
        )
    return loaded


class KnowledgeLoader:
    """Loads every knowledge YAML file under a `knowledge_root` directory.

    Any malformed file raises :class:`KnowledgeLoadError` immediately — there is no
    "skip and continue" mode, per NUMRA's determinism/no-silent-fallback principle.
    """

    def __init__(self, knowledge_root: Path) -> None:
        self.knowledge_root = knowledge_root

    def _load_manifest(self) -> KnowledgeManifest:
        path = self.knowledge_root / "manifest.yaml"
        data = _load_yaml_file(path)
        try:
            return KnowledgeManifest.model_validate(data)
        except ValidationError as exc:
            raise KnowledgeLoadError(f"Invalid manifest at {path}: {exc}") from exc

    def _load_number_dir(self, subdir: str) -> dict[int, NumberKnowledge]:
        directory = self.knowledge_root / subdir
        result: dict[int, NumberKnowledge] = {}
        for path in sorted(directory.glob("*.yaml")):
            data = _load_yaml_file(path)
            try:
                knowledge = NumberKnowledge.model_validate(data)
            except ValidationError as exc:
                raise KnowledgeLoadError(f"Invalid number knowledge at {path}: {exc}") from exc
            if knowledge.value in result:
                raise KnowledgeLoadError(
                    f"Duplicate number knowledge for value={knowledge.value} (clash at {path})"
                )
            result[knowledge.value] = knowledge
        return result

    def _load_karmic_debts(self) -> dict[str, KarmicDebtKnowledge]:
        directory = self.knowledge_root / "karmic-debts"
        result: dict[str, KarmicDebtKnowledge] = {}
        for path in sorted(directory.glob("*.yaml")):
            data = _load_yaml_file(path)
            try:
                knowledge = KarmicDebtKnowledge.model_validate(data)
            except ValidationError as exc:
                raise KnowledgeLoadError(f"Invalid karmic-debt knowledge at {path}: {exc}") from exc
            if knowledge.compound in result:
                raise KnowledgeLoadError(
                    f"Duplicate karmic-debt knowledge for compound={knowledge.compound!r} "
                    f"(clash at {path})"
                )
            result[knowledge.compound] = knowledge
        return result

    def _load_metrics(self) -> dict[str, MetricKnowledge]:
        directory = self.knowledge_root / "metrics"
        result: dict[str, MetricKnowledge] = {}
        for path in sorted(directory.glob("*.yaml")):
            data = _load_yaml_file(path)
            try:
                knowledge = MetricKnowledge.model_validate(data)
            except ValidationError as exc:
                raise KnowledgeLoadError(f"Invalid metric knowledge at {path}: {exc}") from exc
            if knowledge.metric_id in result:
                raise KnowledgeLoadError(
                    f"Duplicate metric knowledge for metric_id={knowledge.metric_id!r} "
                    f"(clash at {path})"
                )
            result[knowledge.metric_id] = knowledge
        return result

    def load(self) -> KnowledgeBase:
        if not self.knowledge_root.is_dir():
            raise KnowledgeLoadError(
                f"knowledge_root {self.knowledge_root} does not exist or is not a directory"
            )

        manifest = self._load_manifest()
        numbers = self._load_number_dir("numbers")
        numbers.update(self._load_number_dir("master-numbers"))
        karmic_debts = self._load_karmic_debts()
        metrics = self._load_metrics()

        return KnowledgeBase(
            manifest=manifest,
            numbers=numbers,
            karmic_debts=karmic_debts,
            metrics=metrics,
        )


def load_knowledge_base(knowledge_root: Path) -> KnowledgeBase:
    """Convenience wrapper around :class:`KnowledgeLoader`."""
    return KnowledgeLoader(knowledge_root).load()
