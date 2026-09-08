"""PR-V2-05: relationship-analysis / shadow-dynamics job creation + generation
(routes/relationship_analysis.py, services/relationship_analysis_service.py). Reuses
the `_connect` two-user helper pattern from test_relationship_workspaces.py and the
`llm`/`run_one_cycle` worker-driving pattern from test_reports.py.
"""

from __future__ import annotations

import re

import pytest

from numra_api.analysis_worker import run_one_cycle
from numra_api.auth.passwords import hash_password
from numra_api.repositories.users import create_user

pytestmark = pytest.mark.integration

_COMPATIBILITY_PATTERN = re.compile(r"\d+\s*%.*(kompatib|match|übereinstimm)", re.IGNORECASE)


async def _signup(client, sessionmaker, email: str) -> dict:
    async with sessionmaker() as db:
        await create_user(db, email=email, password_hash=hash_password("password12345"))
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

    Deliberately overrides `birth_date` for both profiles to non-master-number Life
    Paths (1-9): `lukas_payload`'s own birth date reduces to Life Path 22, which
    `knowledge/shadow-interaction/rules.yaml` does not cover (that table is scoped to
    Life Path 1-9 pairs only per the blueprint) -- reusing it verbatim for both
    members would make the shadow-dynamics E2E test hit an out-of-scope master-number
    pair instead of exercising the real, covered lookup path.
    """
    workspace_id, headers_b = await _connect(client, sessionmaker, email_a, email_b)

    payload_b = {**lukas_payload, "birth_date": "1990-03-14"}  # Life Path 9
    await _create_self_person(client, headers_b, payload_b)
    headers_a = await _switch_user(client, email_a)
    payload_a = {
        **lukas_payload,
        "birth_first_names": "Partner",
        "birth_last_name": "Eins",
        "birth_date": "1988-07-22",  # Life Path 1
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


async def test_relationship_type_work_returns_knowledge_frame_not_available(
    client, sessionmaker, lukas_payload
) -> None:
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
    assert response.status_code == 409
    assert response.json()["code"] == "KNOWLEDGE_FRAME_NOT_AVAILABLE"


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
