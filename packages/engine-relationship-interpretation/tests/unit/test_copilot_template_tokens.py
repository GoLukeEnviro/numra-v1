"""Regression: die Copilot-Antwort laeuft durch dieselbe zentrale Token-Pruefung wie
Analysen und Reports (`rendering_guard.find_unresolved_template_token`).

Der Copilot pruefte bisher nur `contains_prompt_scaffolding(reply.text)` auf dem Rohtext --
das verkuerzte Label ``[a:life_path]`` (Audit 2026-10-09, Beziehungsanalysen), ein
``{{metric:...}}``-Rest und Unicode-Varianten gingen als ``ChatMessage.content`` durch.
"""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import BaseModel

from numra_interpretation.llm.mock_provider import MockLLMProvider
from numra_interpretation.llm.types import (
    ContextBlock,
    ProviderHealth,
    StructuredGenerationRequest,
)
from numra_numerology.engine import calculate_profile
from numra_numerology.models.person import PersonInput
from numra_relationship_interpretation.copilot_pipeline import generate_copilot_reply
from numra_relationship_interpretation.errors import AnalysisGenerationError

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def profile_self():
    return calculate_profile(
        PersonInput(
            birth_first_names="Anna",
            birth_middle_names=None,
            birth_last_name="Berger",
            birth_date=dt.date(1990, 3, 14),
        ),
        as_of_date=dt.date(2026, 8, 19),
    )


def _request() -> StructuredGenerationRequest:
    return StructuredGenerationRequest(
        system_instructions="sys",
        context_blocks=(ContextBlock(role="profile_fact", label="p", content="life_path=6"),),
        user_instructions="Was sagt mein Lebenspfad aus?",
        target_schema_name="CopilotGeneratedReply",
    )


class _FixedReplyProvider:
    def __init__(self, text: str) -> None:
        self._text = text
        self.calls = 0

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            status="healthy", provider="scripted", checked_at=dt.datetime.now(dt.UTC)
        )

    async def generate(self, request):  # pragma: no cover - not used
        raise NotImplementedError

    async def generate_structured(
        self, request: StructuredGenerationRequest, schema: type[BaseModel]
    ) -> BaseModel:
        self.calls += 1
        return schema.model_validate({"text": self._text, "basis_type": "NUMEROLOGY_MODEL"})


@pytest.mark.parametrize(
    "text",
    (
        "Dein Lebenspfad wird hier durch [a:life_path] beschrieben.",
        "Dein Lebenspfad wird hier durch [A: life_path] beschrieben.",
        "Zwischen [a:life_path] und [b:life_path] zeigt sich Nähe.",
        "Dein Lebenspfad wird durch [profile_fact:requester] beschrieben.",
        "Dein Lebenspfad ist {{metric:life_path}} und traegt dich.",
        "Dein Lebenspfad ist {{metric:life_pa",
        "Dein Lebenspfad ist life_path}} und traegt dich.",
        "Dein Lebenspfad wird durch [metric:life_path] beschrieben.",
        "Dein Lebenspfad wird durch ［a：life_path］ beschrieben.",
        "Dein Lebenspfad wird durch [а:life_path] beschrieben.",
        "Dein Lebenspfad wird durch [a​:life_path] beschrieben.",
    ),
)
async def test_a_reply_with_an_internal_token_is_rejected_not_persisted(text, profile_self) -> None:
    provider = _FixedReplyProvider(text)

    with pytest.raises(AnalysisGenerationError, match="PROMPT_SCAFFOLDING_REJECTED"):
        await generate_copilot_reply(
            request=_request(),
            llm=provider,
            knowledge_version="v1",
            grounding_profiles=(profile_self,),
        )

    assert provider.calls == 2, "der erlaubte Reparaturversuch muss stattgefunden haben"


@pytest.mark.parametrize(
    "text",
    (
        "Dein Lebenspfad steht für Verbindlichkeit und Fürsorge.",
        "Treffen um [10:30] Uhr, Buch [1], a:b im Fliesstext und „… [sic] …“.",
        "Aufzählung: a) Nähe, b) Freiraum. Klammern (wie hier) sind Prosa.",
    ),
)
async def test_ordinary_german_replies_are_accepted(text, profile_self) -> None:
    provider = _FixedReplyProvider(text)

    result = await generate_copilot_reply(
        request=_request(),
        llm=provider,
        knowledge_version="v1",
        grounding_profiles=(profile_self,),
    )

    assert result.text == text
    assert provider.calls == 1


async def test_the_mock_provider_stays_exempt_because_its_text_is_replaced(profile_self) -> None:
    result = await generate_copilot_reply(
        request=_request(),
        llm=MockLLMProvider(),
        knowledge_version="v1",
        grounding_profiles=(profile_self,),
    )

    assert "[" not in result.text and "{" not in result.text


@pytest.mark.parametrize(
    "text",
    (
        "Das Muster a{1,2} passt auf ein bis zwei Wiederholungen.",
        "Die Menge { 3 } hat ein Element, eine einzelne } bleibt Prosa.",
        "[A: Ich bin müde] sagte sie, siehe [Text](https://example.org).",
        "Er sagte [a: Nähe] und ging. Aufgabe [x] ist erledigt.",
    ),
)
async def test_isolated_braces_and_bracketed_dialogue_do_not_fail_a_copilot_turn(
    text, profile_self
) -> None:
    provider = _FixedReplyProvider(text)

    result = await generate_copilot_reply(
        request=_request(),
        llm=provider,
        knowledge_version="v1",
        grounding_profiles=(profile_self,),
    )

    assert result.text == text
    assert provider.calls == 1


@pytest.mark.parametrize(
    "text",
    (
        "Dein Weg [a:life_path und geht weiter.",
        "Dein Weg [a:life_path, danach mehr.",
        "Dein Weg [a:life_path. Danach mehr.",
        "Dein Weg [b:expression) so.",
    ),
)
async def test_an_unclosed_known_label_mid_sentence_is_rejected(text, profile_self) -> None:
    provider = _FixedReplyProvider(text)

    with pytest.raises(AnalysisGenerationError, match="PROMPT_SCAFFOLDING_REJECTED"):
        await generate_copilot_reply(
            request=_request(),
            llm=provider,
            knowledge_version="v1",
            grounding_profiles=(profile_self,),
        )
