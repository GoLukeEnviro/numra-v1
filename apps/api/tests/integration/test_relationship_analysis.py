"""PR-V2-05: relationship-analysis / shadow-dynamics job creation + generation
(routes/relationship_analysis.py, services/relationship_analysis_service.py). Reuses
the `_connect` two-user helper pattern from test_relationship_workspaces.py and the
`llm`/`run_one_cycle` worker-driving pattern from test_reports.py.
"""

from __future__ import annotations

import datetime as dt
import re
import uuid

import pytest
from sqlalchemy import update

from numra_api.analysis_worker import run_one_cycle
from numra_api.auth.passwords import hash_password
from numra_api.models import AnalysisJob
from numra_api.repositories.reports import MAX_ATTEMPTS
from numra_api.repositories.users import create_user, mark_email_verified

pytestmark = pytest.mark.integration

_COMPATIBILITY_PATTERN = re.compile(r"\d+\s*%.*(kompatib|match|übereinstimm)", re.IGNORECASE)


async def _signup(client, sessionmaker, email: str) -> dict:
    async with sessionmaker() as db:
        user = await create_user(db, email=email, password_hash=hash_password("password12345"))
        await mark_email_verified(db, user=user, verified_at=dt.datetime.now(dt.UTC))
        await db.commit()
    return await _switch_user(client, email)


async def _switch_user(client, email: str) -> dict:
    await client.post("/v1/auth/logout")
    response = await client.post(
        "/v1/auth/login", json={"email": email, "password": "password12345"}
    )
    assert response.status_code == 200
    return {"x-csrf-token": client.cookies["numra_csrf"]}


async def _connect(client, sessionmaker, email_a: str, email_b: str) -> tuple[str, dict]:
    """Returns (workspace_id, headers_b) and leaves the active session as user B
    (the redeemer). Same helper as test_relationship_workspaces.py."""
    headers_a = await _signup(client, sessionmaker, email_a)
    invitation = (
        await client.post("/v1/connections/invitations", json={"method": "LINK"}, headers=headers_a)
    ).json()
    headers_b = await _signup(client, sessionmaker, email_b)
    redeem = await client.post(
        "/v1/connections/invitations/redeem",
        json={"token": invitation["token"]},
        headers=headers_b,
    )
    assert redeem.status_code == 201
    return redeem.json()["workspace_id"], headers_b


async def _create_self_person(client, headers: dict, payload: dict) -> None:
    response = await client.post("/v1/people", json=payload, headers=headers)
    assert response.status_code == 201
    person_id = response.json()["id"]
    calc = await client.post(
        f"/v1/people/{person_id}/calculations",
        json={"as_of_date": "2026-08-19"},
        headers=headers,
    )
    assert calc.status_code == 201


async def _set_up_partner_workspace(
    client, sessionmaker, lukas_payload, email_a: str, email_b: str
) -> tuple[str, dict, dict]:
    """Two users, connected, both with a SELF profile + calculation, workspace type
    PARTNER. Returns (workspace_id, headers_a, headers_b).

    Both members keep `lukas_payload`'s real birth date (1986-07-18 = Life Path 22, a
    master number). `knowledge/shadow-interaction/rules.yaml` now covers every Life
    Path {1-9, 11, 22, 33} pair, so a master-number pair is a fully supported
    shadow-dynamics lookup path -- no birth-date override needed to stay in scope.
    """
    workspace_id, headers_b = await _connect(client, sessionmaker, email_a, email_b)

    await _create_self_person(client, headers_b, lukas_payload)
    headers_a = await _switch_user(client, email_a)
    payload_a = {
        **lukas_payload,
        "birth_first_names": "Partner",
        "birth_last_name": "Eins",
    }
    await _create_self_person(client, headers_a, payload_a)

    patch = await client.patch(
        f"/v1/workspaces/{workspace_id}",
        json={"relationship_type": "PARTNER"},
        headers=headers_a,
    )
    assert patch.status_code == 200
    return workspace_id, headers_a, headers_b


# ---------------------------------------------------------------------------
# Consent gate + IDOR
# ---------------------------------------------------------------------------


async def test_create_relationship_analysis_without_explicit_grant_uses_defaults(
    client, sessionmaker, lukas_payload
) -> None:
    """RELATIONSHIP_INSIGHTS is auto-granted both directions at workspace creation
    (PR-V2-03 DEFAULT_CONSENT_SCOPES) -- job creation succeeds without an explicit
    grant call."""
    workspace_id, headers_a, _headers_b = await _set_up_partner_workspace(
        client, sessionmaker, lukas_payload, "ra-consent-a@example.com", "ra-consent-b@example.com"
    )
    response = await client.post(
        f"/v1/workspaces/{workspace_id}/relationship-analysis", json={}, headers=headers_a
    )
    assert response.status_code == 201
    assert response.json()["status"] == "PENDING"


async def test_create_relationship_analysis_after_consent_revoke_is_forbidden(
    client, sessionmaker, lukas_payload
) -> None:
    workspace_id, _headers_a, _headers_b = await _set_up_partner_workspace(
        client, sessionmaker, lukas_payload, "ra-revoke-a@example.com", "ra-revoke-b@example.com"
    )
    # Cookies are per-client and last-login-wins (see _switch_user) -- a header dict
    # captured before a later switch is stale, so re-fetch fresh headers for whichever
    # user acts next, matching test_relationship_workspaces.py's own pattern.
    headers_b = await _switch_user(client, "ra-revoke-b@example.com")
    revoke = await client.post(
        f"/v1/workspaces/{workspace_id}/consent/revoke",
        json={"scope": "RELATIONSHIP_INSIGHTS"},
        headers=headers_b,
    )
    assert revoke.status_code == 200

    headers_a = await _switch_user(client, "ra-revoke-a@example.com")
    response = await client.post(
        f"/v1/workspaces/{workspace_id}/relationship-analysis", json={}, headers=headers_a
    )
    assert response.status_code == 403
    assert response.json()["code"] == "CONSENT_NOT_GRANTED"


async def test_old_analysis_stays_readable_after_consent_revoke(
    client, sessionmaker, lukas_payload, llm
) -> None:
    """specs/v2/shadow-dynamics-spec.md: consent is checked at job-creation time, not
    at read time -- a COMPLETE analysis stays a readable historical snapshot after a
    later revoke, even though a *new* job would now be rejected."""
    workspace_id, headers_a, _headers_b = await _set_up_partner_workspace(
        client, sessionmaker, lukas_payload, "ra-hist-a@example.com", "ra-hist-b@example.com"
    )
    create = await client.post(
        f"/v1/workspaces/{workspace_id}/relationship-analysis", json={}, headers=headers_a
    )
    assert create.status_code == 201

    claimed = await run_one_cycle(sessionmaker, llm=llm)
    assert claimed is True

    get_before_revoke = await client.get(
        f"/v1/workspaces/{workspace_id}/relationship-analysis", headers=headers_a
    )
    assert get_before_revoke.status_code == 200
    assert get_before_revoke.json()["status"] == "COMPLETE"

    headers_b = await _switch_user(client, "ra-hist-b@example.com")
    revoke = await client.post(
        f"/v1/workspaces/{workspace_id}/consent/revoke",
        json={"scope": "RELATIONSHIP_INSIGHTS"},
        headers=headers_b,
    )
    assert revoke.status_code == 200

    headers_a = await _switch_user(client, "ra-hist-a@example.com")
    get_after_revoke = await client.get(
        f"/v1/workspaces/{workspace_id}/relationship-analysis", headers=headers_a
    )
    assert get_after_revoke.status_code == 200
    assert get_after_revoke.json()["status"] == "COMPLETE"

    new_job = await client.post(
        f"/v1/workspaces/{workspace_id}/relationship-analysis", json={}, headers=headers_a
    )
    assert new_job.status_code == 403


async def test_relationship_type_work_has_knowledge_frame(
    client, sessionmaker, lukas_payload
) -> None:
    """WORK now has a `knowledge/relationship-frames/work.yaml` frame (all 8
    RelationshipType values do, see specs/v2/relationship-type-spec.md), so job
    creation succeeds instead of returning 409 KNOWLEDGE_FRAME_NOT_AVAILABLE."""
    workspace_id, headers_b = await _connect(
        client, sessionmaker, "ra-work-a@example.com", "ra-work-b@example.com"
    )
    await _create_self_person(client, headers_b, lukas_payload)
    headers_a = await _switch_user(client, "ra-work-a@example.com")
    payload_a = {**lukas_payload, "birth_first_names": "Partner", "birth_last_name": "Eins"}
    await _create_self_person(client, headers_a, payload_a)

    patch = await client.patch(
        f"/v1/workspaces/{workspace_id}", json={"relationship_type": "WORK"}, headers=headers_a
    )
    assert patch.status_code == 200

    response = await client.post(
        f"/v1/workspaces/{workspace_id}/relationship-analysis", json={}, headers=headers_a
    )
    assert response.status_code == 201


async def test_relationship_type_not_set_returns_409(client, sessionmaker, lukas_payload) -> None:
    workspace_id, headers_b = await _connect(
        client, sessionmaker, "ra-notype-a@example.com", "ra-notype-b@example.com"
    )
    await _create_self_person(client, headers_b, lukas_payload)
    headers_a = await _switch_user(client, "ra-notype-a@example.com")
    payload_a = {**lukas_payload, "birth_first_names": "Partner", "birth_last_name": "Eins"}
    await _create_self_person(client, headers_a, payload_a)

    response = await client.post(
        f"/v1/workspaces/{workspace_id}/relationship-analysis", json={}, headers=headers_a
    )
    assert response.status_code == 409
    assert response.json()["code"] == "RELATIONSHIP_TYPE_NOT_SET"


async def test_analysis_job_idor_non_member_gets_404(client, sessionmaker, lukas_payload) -> None:
    workspace_id, headers_a, _headers_b = await _set_up_partner_workspace(
        client, sessionmaker, lukas_payload, "ra-idor-a@example.com", "ra-idor-b@example.com"
    )
    create = await client.post(
        f"/v1/workspaces/{workspace_id}/relationship-analysis", json={}, headers=headers_a
    )
    job_id = create.json()["job_id"]

    outsider_headers = await _signup(client, sessionmaker, "ra-idor-outsider@example.com")
    response = await client.get(f"/v1/analysis-jobs/{job_id}", headers=outsider_headers)
    assert response.status_code == 404


async def test_analysis_job_idor_both_members_can_read(client, sessionmaker, lukas_payload) -> None:
    """Both workspace members may poll the job -- it is a shared, two-person result,
    not requester-only."""
    workspace_id, headers_a, _headers_b = await _set_up_partner_workspace(
        client, sessionmaker, lukas_payload, "ra-idor2-a@example.com", "ra-idor2-b@example.com"
    )
    create = await client.post(
        f"/v1/workspaces/{workspace_id}/relationship-analysis", json={}, headers=headers_a
    )
    job_id = create.json()["job_id"]

    response_a = await client.get(f"/v1/analysis-jobs/{job_id}", headers=headers_a)
    assert response_a.status_code == 200

    headers_b_switched = await _switch_user(client, "ra-idor2-b@example.com")
    response_b = await client.get(f"/v1/analysis-jobs/{job_id}", headers=headers_b_switched)
    assert response_b.status_code == 200


# ---------------------------------------------------------------------------
# Enum validation
# ---------------------------------------------------------------------------


async def test_relationship_type_rejects_free_text_injection(
    client, sessionmaker, lukas_payload
) -> None:
    workspace_id, headers_b = await _connect(
        client, sessionmaker, "ra-enum-a@example.com", "ra-enum-b@example.com"
    )
    await _create_self_person(client, headers_b, lukas_payload)
    headers_a = await _switch_user(client, "ra-enum-a@example.com")
    payload_a = {**lukas_payload, "birth_first_names": "Partner", "birth_last_name": "Eins"}
    await _create_self_person(client, headers_a, payload_a)

    patch = await client.patch(
        f"/v1/workspaces/{workspace_id}",
        json={"relationship_type": "NOT_A_REAL_TYPE"},
        headers=headers_a,
    )
    assert patch.status_code == 422


# ---------------------------------------------------------------------------
# E2E generation with MockLLMProvider
# ---------------------------------------------------------------------------


async def test_relationship_analysis_e2e_covers_all_partner_dimensions_with_provenance(
    client, sessionmaker, lukas_payload, llm
) -> None:
    workspace_id, headers_a, _headers_b = await _set_up_partner_workspace(
        client, sessionmaker, lukas_payload, "ra-e2e-a@example.com", "ra-e2e-b@example.com"
    )
    create = await client.post(
        f"/v1/workspaces/{workspace_id}/relationship-analysis", json={}, headers=headers_a
    )
    assert create.status_code == 201

    claimed = await run_one_cycle(sessionmaker, llm=llm)
    assert claimed is True

    get_response = await client.get(
        f"/v1/workspaces/{workspace_id}/relationship-analysis", headers=headers_a
    )
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["status"] == "COMPLETE"
    result = body["result"]
    dimension_ids = {d["dimension_id"] for d in result["dimensions"]}
    assert dimension_ids == {
        "communication",
        "closeness",
        "autonomy",
        "needs",
        "strengths",
        "conflict_dynamics",
    }
    for dimension in result["dimensions"]:
        for statement in dimension["statements"]:
            assert statement["canonical_refs"] or statement["knowledge_refs"]
            assert not _COMPATIBILITY_PATTERN.search(statement["text"])


async def test_shadow_dynamics_e2e_provenance(client, sessionmaker, lukas_payload, llm) -> None:
    workspace_id, headers_a, _headers_b = await _set_up_partner_workspace(
        client, sessionmaker, lukas_payload, "sd-e2e-a@example.com", "sd-e2e-b@example.com"
    )
    create = await client.post(
        f"/v1/workspaces/{workspace_id}/shadow-dynamics", json={}, headers=headers_a
    )
    assert create.status_code == 201

    claimed = await run_one_cycle(sessionmaker, llm=llm)
    assert claimed is True

    get_response = await client.get(
        f"/v1/workspaces/{workspace_id}/shadow-dynamics", headers=headers_a
    )
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["status"] == "COMPLETE"
    result = body["result"]
    all_statements = (
        result["user_a_shadow_themes"]
        + result["user_b_shadow_themes"]
        + [result["interaction_pattern"], result["escalation_loop"]]
        + result["deescalation_opportunities"]
    )
    for statement in all_statements:
        assert statement["canonical_refs"] or statement["knowledge_refs"]
        assert not _COMPATIBILITY_PATTERN.search(statement["text"])
    assert result["pattern_intensity"] in ("moderate", "high")
    assert len(result["recommended_micro_tasks"]) >= 1


@pytest.mark.parametrize(
    "birth_date",
    ["1960-01-03", "1986-07-18", "1960-04-22"],  # Life Path 11 / 22 / 33
)
async def test_shadow_dynamics_e2e_completes_for_master_life_paths(
    client, sessionmaker, lukas_payload, llm, birth_date
) -> None:
    """Shadow dynamics must reach COMPLETE (not terminal FAILED) for master-number
    Life Paths 11/22/33 -- the pair the pre-fix rules.yaml could not resolve."""
    master_payload = {**lukas_payload, "birth_date": birth_date}
    workspace_id, headers_a, _headers_b = await _set_up_partner_workspace(
        client,
        sessionmaker,
        master_payload,
        f"sd-master-{birth_date}-a@example.com",
        f"sd-master-{birth_date}-b@example.com",
    )
    create = await client.post(
        f"/v1/workspaces/{workspace_id}/shadow-dynamics", json={}, headers=headers_a
    )
    assert create.status_code == 201

    claimed = await run_one_cycle(sessionmaker, llm=llm)
    assert claimed is True

    get_response = await client.get(
        f"/v1/workspaces/{workspace_id}/shadow-dynamics", headers=headers_a
    )
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "COMPLETE"


async def test_shadow_dynamics_e2e_missing_rule_fails_terminally(
    client, sessionmaker, lukas_payload, llm, monkeypatch
) -> None:
    """A genuine shadow-interaction-rule gap (simulated here by an empty rules table)
    must fail the job terminally as ANALYSIS_GENERATION_ERROR with retryable=False --
    not retry-loop, not a bare UNEXPECTED_ERROR. Keeps the FAILED path covered without
    relying on a real knowledge hole."""
    from numra_api.services import relationship_analysis_service as svc

    monkeypatch.setattr(svc, "load_shadow_interaction_rules", lambda _root: ())

    workspace_id, headers_a, _headers_b = await _set_up_partner_workspace(
        client, sessionmaker, lukas_payload, "sd-fail-a@example.com", "sd-fail-b@example.com"
    )
    create = await client.post(
        f"/v1/workspaces/{workspace_id}/shadow-dynamics", json={}, headers=headers_a
    )
    assert create.status_code == 201
    job_id = create.json()["job_id"]

    claimed = await run_one_cycle(sessionmaker, llm=llm)
    assert claimed is True

    job = await client.get(f"/v1/analysis-jobs/{job_id}", headers=headers_a)
    assert job.status_code == 200
    job_body = job.json()
    assert job_body["status"] == "FAILED"  # terminal, retryable=False -> no retry loop
    assert job_body["error_code"].startswith("ANALYSIS_GENERATION_ERROR")


# ---------------------------------------------------------------------------
# Kontextblock-Labels im Modelltext: aufloesen (eindeutig) oder ablehnen
# ---------------------------------------------------------------------------


class _StubProvider:
    """A real (non-mock) provider that never calls a model: renders whatever
    ``text_for(request)`` returns."""

    def __init__(self, text_for) -> None:
        self._text_for = text_for

    async def health(self):
        from numra_interpretation.llm.types import ProviderHealth

        return ProviderHealth(
            status="healthy", provider="ollama_cloud", checked_at=dt.datetime.now(dt.UTC)
        )

    async def generate(self, request):
        raise AssertionError("not used")

    async def generate_structured(self, request, schema):
        return schema(text=self._text_for(request))


def _cites_first_fact_label(request) -> str:
    label = next(b.label for b in request.context_blocks if b.role == "profile_fact")
    return f"Das ist gepraegt durch [profile_fact:{label}] im Alltag."


def _cites_first_fact_short_label(request) -> str:
    label = next(b.label for b in request.context_blocks if b.role == "profile_fact")
    return f"Das ist gepraegt durch [{label}] im Alltag."


def _strings(value):
    """Every string value anywhere in a JSON-shaped result."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


@pytest.mark.parametrize("kind", ["relationship-analysis", "shadow-dynamics"])
@pytest.mark.parametrize("cite_name", ["long", "short"])
async def test_copied_fact_label_is_resolved_and_the_analysis_completes(
    client, sessionmaker, lukas_payload, kind, cite_name
) -> None:
    cite = {"long": _cites_first_fact_label, "short": _cites_first_fact_short_label}[cite_name]
    workspace_id, headers_a, _headers_b = await _set_up_partner_workspace(
        client,
        sessionmaker,
        lukas_payload,
        f"lr-ok-{kind}-{cite_name}-a@example.com",
        f"lr-ok-{kind}-{cite_name}-b@example.com",
    )
    create = await client.post(f"/v1/workspaces/{workspace_id}/{kind}", json={}, headers=headers_a)
    assert create.status_code == 201

    claimed = await run_one_cycle(sessionmaker, llm=_StubProvider(cite))
    assert claimed is True

    body = (await client.get(f"/v1/workspaces/{workspace_id}/{kind}", headers=headers_a)).json()
    assert body["status"] == "COMPLETE"
    strings = list(_strings(body["result"]))
    assert any("gepraegt durch" in text for text in strings)
    for text in strings:
        for token in ("[", "]", "{", "}", "profile_fact"):
            assert token not in text, f"{token!r} leaked into the stored result: {text!r}"
    job = (
        await client.get(f"/v1/analysis-jobs/{create.json()['job_id']}", headers=headers_a)
    ).json()
    assert job["status"] == "COMPLETE"
    assert job["error_code"] is None


@pytest.mark.parametrize("kind", ["relationship-analysis", "shadow-dynamics"])
@pytest.mark.parametrize(
    ("case", "unrepairable"),
    [
        ("knowledge", "Wissen [knowledge:communication:semantic_context] im Satz."),
        ("ambiguous", "Mehrdeutig [profile_fact:life_path] im Satz."),
        ("unknown", "Unbekannt [profile_fact:a:does_not_exist] im Satz."),
        ("template", "Template {partner_a} im Satz."),
        ("fullwidth", "Voll \uff3bprofile_fact\uff1aa:expression\uff3d im Satz."),
        ("short-unknown", "Unbekannt [a:does_not_exist] im Satz."),
        ("short-truncated", "Abgeschnitten [a:life_pa"),
        ("short-nested", "Verschachtelt [[a:life_path]] im Satz."),
        ("short-fullwidth", "Voll \uff3ba\uff1alife_path\uff3d im Satz."),
        ("metric-truncated", "Abgeschnitten {{metric:a:life_pa"),
        ("short-unknown-plain", "Unbekannt [a:foo] im Satz."),
        ("lookalike-id", "Unbekannt [a:does_not_exist_\u0261] im Satz."),
        ("filler-in-marker", "Voll [prof\u3164ile_fact:a:expression] im Satz."),
        ("control-in-marker", "Voll [prof\x07ile_fact:a:expression] im Satz."),
        ("format-positional", "Platzhalter {0} im Satz."),
        ("format-conversion", "Platzhalter {name!r} im Satz."),
    ],
)
async def test_unrepairable_token_never_completes_and_fails_with_one_error_code(
    client, sessionmaker, lukas_payload, kind, case, unrepairable
) -> None:
    slug = f"{kind}-{case}"
    workspace_id, headers_a, _headers_b = await _set_up_partner_workspace(
        client,
        sessionmaker,
        lukas_payload,
        f"lr-bad-{slug}-a@example.com",
        f"lr-bad-{slug}-b@example.com",
    )
    create = await client.post(f"/v1/workspaces/{workspace_id}/{kind}", json={}, headers=headers_a)
    assert create.status_code == 201
    job_id = create.json()["job_id"]
    llm = _StubProvider(lambda _request: unrepairable)

    # Retryable: first attempt is re-queued, never COMPLETE.
    assert await run_one_cycle(sessionmaker, llm=llm) is True
    job = (await client.get(f"/v1/analysis-jobs/{job_id}", headers=headers_a)).json()
    assert job["status"] == "QUEUED"
    assert job["error_code"] == "ANALYSIS_GENERATION_ERROR"

    # Last attempt: terminal FAILED with the very same code, nothing stored as result.
    async with sessionmaker() as db:
        await db.execute(
            update(AnalysisJob)
            .where(AnalysisJob.id == job_id)
            .values(next_attempt_at=None, attempt_count=MAX_ATTEMPTS - 1)
        )
        await db.commit()
    assert await run_one_cycle(sessionmaker, llm=llm) is True
    job = (await client.get(f"/v1/analysis-jobs/{job_id}", headers=headers_a)).json()
    assert job["status"] == "FAILED"
    assert job["error_code"] == "ANALYSIS_GENERATION_ERROR"

    stored = (
        await client.get(
            f"/v1/workspaces/{workspace_id}/{kind}/{create.json()['id']}", headers=headers_a
        )
    ).json()
    assert stored["status"] == "FAILED"
    assert stored["result"] is None
    latest = await client.get(f"/v1/workspaces/{workspace_id}/{kind}", headers=headers_a)
    assert latest.status_code == 404 or latest.json()["status"] != "COMPLETE"


async def test_job_that_succeeds_after_a_rejected_attempt_keeps_no_error_code(
    client, sessionmaker, lukas_payload
) -> None:
    """Ein Job, der im zweiten Versuch COMPLETE wird, zeigt den Fehlercode des ersten
    Versuchs nicht mehr (die Fortschrittsanzeige gibt ``error_code`` woertlich aus);
    ``last_error_at`` bleibt als Spur des Retries."""
    workspace_id, headers_a, _headers_b = await _set_up_partner_workspace(
        client, sessionmaker, lukas_payload, "lr-retry-a@example.com", "lr-retry-b@example.com"
    )
    create = await client.post(
        f"/v1/workspaces/{workspace_id}/relationship-analysis", json={}, headers=headers_a
    )
    assert create.status_code == 201
    job_id = create.json()["job_id"]
    calls = {"n": 0}

    def _text(_request) -> str:
        calls["n"] += 1
        # Erste Dimension: Erstversuch + Reparaturversuch abgelehnt -> Job wird neu eingeplant.
        return "Ein Rest [a:does_not_exist] im Satz." if calls["n"] <= 2 else "Saubere Prosa."

    llm = _StubProvider(_text)

    assert await run_one_cycle(sessionmaker, llm=llm) is True
    job = (await client.get(f"/v1/analysis-jobs/{job_id}", headers=headers_a)).json()
    assert job["status"] == "QUEUED"
    assert job["error_code"] == "ANALYSIS_GENERATION_ERROR"

    async with sessionmaker() as db:
        await db.execute(
            update(AnalysisJob).where(AnalysisJob.id == job_id).values(next_attempt_at=None)
        )
        await db.commit()
    assert await run_one_cycle(sessionmaker, llm=llm) is True

    job = (await client.get(f"/v1/analysis-jobs/{job_id}", headers=headers_a)).json()
    assert job["status"] == "COMPLETE"
    assert job["error_code"] is None
    async with sessionmaker() as db:
        stored = await db.get(AnalysisJob, uuid.UUID(job_id))
        assert stored is not None and stored.last_error_at is not None


@pytest.mark.parametrize("kind", ["relationship-analysis", "shadow-dynamics"])
async def test_a_field_no_pipeline_gate_checks_never_completes_the_analysis(
    client, sessionmaker, lukas_payload, llm, monkeypatch, kind
) -> None:
    """Das Gate am Speicherpunkt (`persistence_gate`) prueft das komplette Ergebnis. Der
    Rest steckt hier in einem Herkunftsfeld, das keine Pipeline-Pruefung kennt; er wird
    erst nach der Pipeline eingefuegt, also muss das Service-Gate ihn fangen."""
    from numra_api.services import relationship_analysis_service as service

    name = {
        "relationship-analysis": "generate_relationship_analysis",
        "shadow-dynamics": "generate_shadow_dynamics",
    }[kind]
    real = getattr(service, name)

    async def _poisoned(**kwargs):
        result = await real(**kwargs)
        if kind == "relationship-analysis":
            dimension = result.dimensions[0]
            statement = dimension.statements[0].model_copy(update={"canonical_refs": ("[a:foo]",)})
            dimension = dimension.model_copy(update={"statements": (statement,)})
            return result.model_copy(update={"dimensions": (dimension, *result.dimensions[1:])})
        statement = result.interaction_pattern.model_copy(update={"knowledge_refs": ("{0}",)})
        return result.model_copy(update={"interaction_pattern": statement})

    monkeypatch.setattr(service, name, _poisoned)
    workspace_id, headers_a, _headers_b = await _set_up_partner_workspace(
        client,
        sessionmaker,
        lukas_payload,
        f"lr-gate-{kind}-a@example.com",
        f"lr-gate-{kind}-b@example.com",
    )
    create = await client.post(f"/v1/workspaces/{workspace_id}/{kind}", json={}, headers=headers_a)
    assert create.status_code == 201
    job_id = create.json()["job_id"]

    assert await run_one_cycle(sessionmaker, llm=llm) is True

    job = (await client.get(f"/v1/analysis-jobs/{job_id}", headers=headers_a)).json()
    assert job["status"] == "QUEUED"
    assert job["error_code"] == "ANALYSIS_GENERATION_ERROR"
    stored = (
        await client.get(
            f"/v1/workspaces/{workspace_id}/{kind}/{create.json()['id']}", headers=headers_a
        )
    ).json()
    assert stored["status"] != "COMPLETE"
    assert stored["result"] is None
