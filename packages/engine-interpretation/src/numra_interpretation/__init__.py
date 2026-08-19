"""NUMRA interpretation engine.

Responsibility: Canonical Profile + relevant Knowledge + Report Specification ->
structured interpretation. This package performs NO calculation — it only
composes and validates interpretation text/blocks grounded in values that the
deterministic engine already produced.

Submodules:

- `knowledge_models` / `knowledge_loader` — typed, validated access to `knowledge/`.
- `composer` — rule-based composition of a `CanonicalProfile` + `KnowledgeBase` into a
  structured `Interpretation`. No LLM call.
- `llm` — the provider-agnostic LLM interface (`LLMProvider` protocol), a deterministic
  `MockLLMProvider`, a real `OllamaCloudProvider`, and the numeric-claims validator that
  keeps any LLM-generated text honest about canonical values.
"""

from __future__ import annotations

from numra_interpretation.composer import (
    CORE_METRIC_IDS,
    Interpretation,
    InterpretationSection,
    compose_interpretation,
)
from numra_interpretation.errors import InvalidReportSection, KnowledgeLoadError
from numra_interpretation.knowledge_loader import (
    KnowledgeBase,
    KnowledgeLoader,
    load_knowledge_base,
)
from numra_interpretation.knowledge_models import (
    KarmicDebtKnowledge,
    KnowledgeManifest,
    MetricKnowledge,
    NumberKnowledge,
)

__all__ = [
    "CORE_METRIC_IDS",
    "Interpretation",
    "InterpretationSection",
    "InvalidReportSection",
    "KarmicDebtKnowledge",
    "KnowledgeBase",
    "KnowledgeLoadError",
    "KnowledgeLoader",
    "KnowledgeManifest",
    "MetricKnowledge",
    "NumberKnowledge",
    "compose_interpretation",
    "load_knowledge_base",
]
