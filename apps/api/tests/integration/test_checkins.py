"""PR-V2-06 -- configurable check-ins (routes/checkins.py,
services/checkin_service.py). Reuses the `_connect` two-user helper pattern from
test_relationship_workspaces.py / test_consent.py. Includes the Section-49-matrix
privacy-critical block at the bottom (specs/v2/privacy-spec.md).
"""

from __future__ import annotations

import re

import pytest

from numra_api.auth.passwords import hash_password
from numra_api.repositories.users import create_user

pytestmark = pytest.mark.integration


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


async def _connect(client, sessionmaker, email_a: str, email_b: str) -> str:
    """Leaves the active session as user B (the redeemer)."""
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
    return redeem.json()["workspace_id"]


# ---------------------------------------------------------------------------
# Default template lazy creation
# ---------------------------------------------------------------------------


async def test_default_template_lazy_creation_has_five_dimensions(client, sessionmaker) -> None:
    workspace_id = await _connect(client, sessionmaker, "tpl-a@example.com", "tpl-b@example.com")
    headers = await _switch_user(client, "tpl-a@example.com")

    response = await client.get(f"/v1/workspaces/{workspace_id}/checkin-template", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert body["active"] is True
    keys = {d["semantic_key"] for d in body["dimensions"]}
    assert keys == {"closeness", "communication", "understanding", "autonomy", "conflict_load"}
    assert "sexual_connection" not in keys
    for dimension in body["dimensions"]:
        assert dimension["scale_min"] == 1
        assert dimension["scale_max"] == 10


# ---------------------------------------------------------------------------
# Custom dimensions
# ---------------------------------------------------------------------------


async def test_custom_dimension_creation_and_label_update_keeps_semantic_key(
    client, sessionmaker
) -> None:
    workspace_id = await _connect(client, sessionmaker, "cd-a@example.com", "cd-b@example.com")
    headers = await _switch_user(client, "cd-a@example.com")

    create = await client.post(
        f"/v1/workspaces/{workspace_id}/checkin-dimensions",
        json={"semantic_key": "trust", "label": "Trust", "scale_min": 1, "scale_max": 10},
        headers=headers,
    )
    assert create.status_code == 201
    dimension_id = create.json()["id"]
    assert create.json()["semantic_key"] == "trust"

    patch = await client.patch(
        f"/v1/workspaces/{workspace_id}/checkin-dimensions/{dimension_id}",
        json={"label": "Deep Trust"},
        headers=headers,
    )
    assert patch.status_code == 200
    assert patch.json()["label"] == "Deep Trust"
    assert patch.json()["semantic_key"] == "trust"


async def test_duplicate_semantic_key_is_409(client, sessionmaker) -> None:
    workspace_id = await _connect(client, sessionmaker, "dup-a@example.com", "dup-b@example.com")
    headers = await _switch_user(client, "dup-a@example.com")

    first = await client.post(
        f"/v1/workspaces/{workspace_id}/checkin-dimensions",
        json={"semantic_key": "trust", "label": "Trust"},
        headers=headers,
    )
    assert first.status_code == 201

    second = await client.post(
        f"/v1/workspaces/{workspace_id}/checkin-dimensions",
        json={"semantic_key": "trust", "label": "Trust Again"},
        headers=headers,
    )
    assert second.status_code == 409
    assert second.json()["code"] == "SEMANTIC_KEY_IMMUTABLE"


# ---------------------------------------------------------------------------
# sexual_connection gating
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("relationship_type", ["PARENT_CHILD", "SIBLINGS", "WORK"])
async def test_sexual_connection_direct_create_rejected_for_restricted_type(
    client, sessionmaker, relationship_type
) -> None:
    workspace_id = await _connect(
        client,
        sessionmaker,
        f"sg-{relationship_type}-a@example.com",
        f"sg-{relationship_type}-b@example.com",
    )
    headers = await _switch_user(client, f"sg-{relationship_type}-a@example.com")

    patch = await client.patch(
        f"/v1/workspaces/{workspace_id}",
        json={"relationship_type": relationship_type},
        headers=headers,
    )
    assert patch.status_code == 200

    create = await client.post(
        f"/v1/workspaces/{workspace_id}/checkin-dimensions",
        json={"semantic_key": "sexual_connection", "label": "Sexual Connection"},
        headers=headers,
    )
    assert create.status_code == 422
    assert create.json()["code"] == "DIMENSION_NOT_ALLOWED_FOR_RELATIONSHIP_TYPE"


async def test_sexual_connection_allowed_for_unrestricted_type(client, sessionmaker) -> None:
    workspace_id = await _connect(client, sessionmaker, "sok-a@example.com", "sok-b@example.com")
    headers = await _switch_user(client, "sok-a@example.com")

    patch = await client.patch(
        f"/v1/workspaces/{workspace_id}",
        json={"relationship_type": "PARTNER"},
        headers=headers,
    )
    assert patch.status_code == 200

    create = await client.post(
        f"/v1/workspaces/{workspace_id}/checkin-dimensions",
        json={"semantic_key": "sexual_connection", "label": "Sexual Connection"},
        headers=headers,
    )
    assert create.status_code == 201


async def test_type_change_to_restricted_auto_retires_active_sexual_connection(
    client, sessionmaker
) -> None:
    workspace_id = await _connect(client, sessionmaker, "art-a@example.com", "art-b@example.com")
    headers = await _switch_user(client, "art-a@example.com")

    await client.patch(
        f"/v1/workspaces/{workspace_id}",
        json={"relationship_type": "PARTNER"},
        headers=headers,
    )
    create = await client.post(
        f"/v1/workspaces/{workspace_id}/checkin-dimensions",
        json={"semantic_key": "sexual_connection", "label": "Sexual Connection"},
        headers=headers,
    )
    assert create.status_code == 201
    dimension_id = create.json()["id"]

    switch_to_restricted = await client.patch(
        f"/v1/workspaces/{workspace_id}",
        json={"relationship_type": "SIBLINGS"},
        headers=headers,
    )
    assert switch_to_restricted.status_code == 200

    template = await client.get(f"/v1/workspaces/{workspace_id}/checkin-template", headers=headers)
    by_id = {d["id"]: d for d in template.json()["dimensions"]}
    assert by_id[dimension_id]["active"] is False
    assert by_id[dimension_id]["retired_at"] is not None


# ---------------------------------------------------------------------------
# Retire flow
# ---------------------------------------------------------------------------


async def test_retire_dimension_keeps_historical_response_readable(client, sessionmaker) -> None:
    workspace_id = await _connect(client, sessionmaker, "rf-a@example.com", "rf-b@example.com")
    headers_a = await _switch_user(client, "rf-a@example.com")

    template = (
        await client.get(f"/v1/workspaces/{workspace_id}/checkin-template", headers=headers_a)
    ).json()
    dims = {d["semantic_key"]: d["id"] for d in template["dimensions"]}

    submit_a = await client.post(
        f"/v1/workspaces/{workspace_id}/checkins",
        json={"responses": [{"dimension_id": dims["closeness"], "value": 7}]},
        headers=headers_a,
    )
    assert submit_a.status_code == 201
    checkin_id = submit_a.json()["id"]

    # A retires the "closeness" dimension after submitting.
    retire = await client.patch(
        f"/v1/workspaces/{workspace_id}/checkin-dimensions/{dims['closeness']}",
        json={"active": False},
        headers=headers_a,
    )
    assert retire.status_code == 200
    assert retire.json()["active"] is False
    assert retire.json()["retired_at"] is not None

    # Historical response is still correctly readable by its owner.
    get_checkin = await client.get(
        f"/v1/workspaces/{workspace_id}/checkins/{checkin_id}", headers=headers_a
    )
    assert get_checkin.status_code == 200
    my_responses = get_checkin.json()["my_responses"]
    assert len(my_responses) == 1
    assert my_responses[0]["semantic_key"] == "closeness"
    assert my_responses[0]["value"] == 7


# ---------------------------------------------------------------------------
# Submission flow
# ---------------------------------------------------------------------------


async def test_submission_flow_first_awaiting_second_analyzed(client, sessionmaker) -> None:
    workspace_id = await _connect(client, sessionmaker, "sf-a@example.com", "sf-b@example.com")
    headers_a = await _switch_user(client, "sf-a@example.com")
    template = (
        await client.get(f"/v1/workspaces/{workspace_id}/checkin-template", headers=headers_a)
    ).json()
    dims = {d["semantic_key"]: d["id"] for d in template["dimensions"]}

    submit_a = await client.post(
        f"/v1/workspaces/{workspace_id}/checkins",
        json={"responses": [{"dimension_id": dims["closeness"], "value": 8}]},
        headers=headers_a,
    )
    assert submit_a.status_code == 201
    body_a = submit_a.json()
    assert body_a["status"] == "AWAITING_SUBMISSIONS"
    assert body_a["analysis"] is None
    checkin_id = body_a["id"]

    headers_b = await _switch_user(client, "sf-b@example.com")
    submit_b = await client.post(
        f"/v1/workspaces/{workspace_id}/checkins",
        json={"responses": [{"dimension_id": dims["closeness"], "value": 5}]},
        headers=headers_b,
    )
    assert submit_b.status_code == 201
    body_b = submit_b.json()
    assert body_b["id"] == checkin_id
    assert body_b["status"] == "ANALYZED"
    assert body_b["analysis"] is not None
    assert body_b["analysis"]["result"]["closeness"]["absolute_gap"] == 3
    assert body_b["analysis"]["result"]["closeness"]["direction"] == "NO_PRIOR_DATA"
    # B's own response only -- never A's raw value.
    assert body_b["my_responses"][0]["value"] == 5


async def test_concurrent_first_submissions_land_on_one_round_not_two(
    client, sessionmaker, monkeypatch
) -> None:
    """Regression for the HIGH review finding on this PR: two members submitting
    their first response for a new round at (near-)the same time must not each
    create their own AWAITING_SUBMISSIONS round (which would silently orphan both --
    `count_distinct_submitters` would never reach 2 for either). Simulates the race
    deterministically: a competing round already exists in the DB (as the *other*
    member's concurrent transaction would have committed first), but this call's
    `get_awaiting_checkin` read is patched to have missed it once -- exactly what
    happens under READ COMMITTED when both transactions read before either commits.
    `submit_checkin` must catch the resulting IntegrityError from
    `uq_relationship_checkins_one_awaiting_per_workspace`, roll back its own losing
    insert, and re-fetch onto the real (winning) round instead."""
    import uuid as uuid_module

    import numra_api.repositories.checkins as checkins_repo
    import numra_api.services.checkin_service as checkin_service_module
    from numra_api.repositories.workspaces import get_workspace_by_id
    from numra_api.services.checkin_service import get_or_create_active_template, submit_checkin

    workspace_id = await _connect(client, sessionmaker, "race-a@example.com", "race-b@example.com")
    headers_a = await _switch_user(client, "race-a@example.com")
    template_body = (
        await client.get(f"/v1/workspaces/{workspace_id}/checkin-template", headers=headers_a)
    ).json()
    # dimensions_by_id downstream keys on uuid.UUID, not the JSON-serialized str id.
    closeness_dimension_id = uuid_module.UUID(
        next(d["id"] for d in template_body["dimensions"] if d["semantic_key"] == "closeness")
    )

    async with sessionmaker() as db:
        from sqlalchemy import select

        from numra_api.models import RelationshipCheckin, User

        user_a_id = (
            await db.execute(select(User.id).where(User.email == "race-a@example.com"))
        ).scalar_one()
        workspace = await get_workspace_by_id(db, workspace_id=workspace_id)
        assert workspace is not None
        template = await get_or_create_active_template(db, workspace_id=workspace_id)

        # The "winning" concurrent transaction: already committed its round before
        # this call's (stale) read below.
        winning_checkin = await checkins_repo.create_checkin(
            db, workspace_id=workspace_id, checkin_template_version=template.version
        )
        await db.commit()

        real_get_awaiting = checkins_repo.get_awaiting_checkin
        call_count = {"n": 0}

        async def _stale_read_once(db_inner, *, workspace_id):  # noqa: ANN001
            call_count["n"] += 1
            if call_count["n"] == 1:
                return None  # simulates the race: didn't see the winner's commit yet
            return await real_get_awaiting(db_inner, workspace_id=workspace_id)

        monkeypatch.setattr(
            checkin_service_module.checkins_repo, "get_awaiting_checkin", _stale_read_once
        )

        result = await submit_checkin(
            db,
            workspace_id=workspace_id,
            user_id=user_a_id,
            responses=[(closeness_dimension_id, 8)],
        )
        await db.commit()

        assert result.checkin.id == winning_checkin.id, (
            "submit_checkin must land on the pre-existing (winning) round, not a "
            "second orphaned one"
        )

        rows = (
            (
                await db.execute(
                    select(RelationshipCheckin).where(
                        RelationshipCheckin.workspace_id == workspace_id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1, (
            f"expected exactly one RelationshipCheckin for this workspace after the "
            f"race, found {len(rows)} -- the losing insert must have been rolled back"
        )


async def test_double_submission_is_409_and_does_not_overwrite(client, sessionmaker) -> None:
    workspace_id = await _connect(client, sessionmaker, "ds-a@example.com", "ds-b@example.com")
    headers_a = await _switch_user(client, "ds-a@example.com")
    template = (
        await client.get(f"/v1/workspaces/{workspace_id}/checkin-template", headers=headers_a)
    ).json()
    dims = {d["semantic_key"]: d["id"] for d in template["dimensions"]}

    first = await client.post(
        f"/v1/workspaces/{workspace_id}/checkins",
        json={"responses": [{"dimension_id": dims["closeness"], "value": 8}]},
        headers=headers_a,
    )
    assert first.status_code == 201

    second = await client.post(
        f"/v1/workspaces/{workspace_id}/checkins",
        json={"responses": [{"dimension_id": dims["closeness"], "value": 1}]},
        headers=headers_a,
    )
    assert second.status_code == 409
    assert second.json()["code"] == "CHECKIN_ALREADY_SUBMITTED"
    assert not re.search(r"\d", second.json()["message"].replace(first.json()["id"], ""))

    checkin_id = first.json()["id"]
    get_checkin = await client.get(
        f"/v1/workspaces/{workspace_id}/checkins/{checkin_id}", headers=headers_a
    )
    assert get_checkin.json()["my_responses"][0]["value"] == 8


# ---------------------------------------------------------------------------
# PRIVACY MATRIX (specs/v2/privacy-spec.md Section 49)
# ---------------------------------------------------------------------------


async def test_privacy_user_a_reads_before_b_submits_sees_no_b_values(client, sessionmaker) -> None:
    workspace_id = await _connect(client, sessionmaker, "pm-a@example.com", "pm-b@example.com")
    headers_a = await _switch_user(client, "pm-a@example.com")
    template = (
        await client.get(f"/v1/workspaces/{workspace_id}/checkin-template", headers=headers_a)
    ).json()
    dims = {d["semantic_key"]: d["id"] for d in template["dimensions"]}

    submit_a = await client.post(
        f"/v1/workspaces/{workspace_id}/checkins",
        json={"responses": [{"dimension_id": dims["closeness"], "value": 9}]},
        headers=headers_a,
    )
    checkin_id = submit_a.json()["id"]

    read_a = await client.get(
        f"/v1/workspaces/{workspace_id}/checkins/{checkin_id}", headers=headers_a
    )
    body = read_a.json()
    assert body["status"] == "AWAITING_SUBMISSIONS"
    assert body["analysis"] is None
    assert len(body["my_responses"]) == 1
    # No field anywhere in the payload carries a second numeric value/partner key.
    assert "partner_responses" not in body
    assert "other_responses" not in body


async def test_privacy_user_a_reads_after_both_submit_only_own_and_aggregate(
    client, sessionmaker
) -> None:
    workspace_id = await _connect(client, sessionmaker, "pm2-a@example.com", "pm2-b@example.com")
    headers_a = await _switch_user(client, "pm2-a@example.com")
    template = (
        await client.get(f"/v1/workspaces/{workspace_id}/checkin-template", headers=headers_a)
    ).json()
    dims = {d["semantic_key"]: d["id"] for d in template["dimensions"]}

    submit_a = await client.post(
        f"/v1/workspaces/{workspace_id}/checkins",
        json={"responses": [{"dimension_id": dims["closeness"], "value": 9}]},
        headers=headers_a,
    )
    checkin_id = submit_a.json()["id"]

    headers_b = await _switch_user(client, "pm2-b@example.com")
    await client.post(
        f"/v1/workspaces/{workspace_id}/checkins",
        json={"responses": [{"dimension_id": dims["closeness"], "value": 2}]},
        headers=headers_b,
    )

    headers_a = await _switch_user(client, "pm2-a@example.com")
    read_a = await client.get(
        f"/v1/workspaces/{workspace_id}/checkins/{checkin_id}", headers=headers_a
    )
    body = read_a.json()
    assert body["status"] == "ANALYZED"
    assert len(body["my_responses"]) == 1
    assert body["my_responses"][0]["value"] == 9
    # Aggregate analysis only carries derived numbers, never B's raw 2.
    result = body["analysis"]["result"]["closeness"]
    assert set(result.keys()) == {
        "absolute_gap",
        "direction",
        "rolling_trend",
        "sample_size",
        "historical_delta",
        "sufficient_evidence",
    }
    assert result["absolute_gap"] == 7
    body_str = str(body)
    assert '"value": 2' not in body_str.replace('"value": 9', "")


async def test_privacy_error_messages_never_contain_numeric_values(client, sessionmaker) -> None:
    workspace_id = await _connect(client, sessionmaker, "pm3-a@example.com", "pm3-b@example.com")
    headers_a = await _switch_user(client, "pm3-a@example.com")
    template = (
        await client.get(f"/v1/workspaces/{workspace_id}/checkin-template", headers=headers_a)
    ).json()
    dims = {d["semantic_key"]: d["id"] for d in template["dimensions"]}

    await client.post(
        f"/v1/workspaces/{workspace_id}/checkins",
        json={"responses": [{"dimension_id": dims["closeness"], "value": 6}]},
        headers=headers_a,
    )
    second = await client.post(
        f"/v1/workspaces/{workspace_id}/checkins",
        json={"responses": [{"dimension_id": dims["closeness"], "value": 3}]},
        headers=headers_a,
    )
    assert second.status_code == 409
    message = second.json()["message"]
    stranger_headers = await _signup(client, sessionmaker, "pm3-stranger@example.com")
    not_found = await client.get(
        f"/v1/workspaces/{workspace_id}/checkins", headers=stranger_headers
    )
    not_found_message = not_found.json()["message"]

    checkin_id = re.search(r"[0-9a-f-]{36}", message)
    assert checkin_id is not None
    remainder = message.replace(checkin_id.group(0), "")
    assert not re.search(r"\d", remainder)

    # NotFoundError legitimately embeds the (non-secret) workspace_id UUID -- strip
    # it before asserting no OTHER numeric value (e.g. a submitted check-in value)
    # leaked into the message.
    workspace_uuid = re.search(r"[0-9a-f-]{36}", not_found_message)
    assert workspace_uuid is not None
    not_found_remainder = not_found_message.replace(workspace_uuid.group(0), "")
    assert not re.search(r"\d", not_found_remainder)


async def test_privacy_non_member_gets_404_on_all_six_endpoints(client, sessionmaker) -> None:
    workspace_id = await _connect(client, sessionmaker, "nm-a@example.com", "nm-b@example.com")
    headers_a = await _switch_user(client, "nm-a@example.com")
    template = (
        await client.get(f"/v1/workspaces/{workspace_id}/checkin-template", headers=headers_a)
    ).json()
    dim_id = template["dimensions"][0]["id"]
    submit = await client.post(
        f"/v1/workspaces/{workspace_id}/checkins",
        json={"responses": [{"dimension_id": dim_id, "value": 5}]},
        headers=headers_a,
    )
    checkin_id = submit.json()["id"]

    stranger_headers = await _signup(client, sessionmaker, "nm-stranger@example.com")

    responses = [
        await client.get(
            f"/v1/workspaces/{workspace_id}/checkin-template", headers=stranger_headers
        ),
        await client.post(
            f"/v1/workspaces/{workspace_id}/checkin-dimensions",
            json={"semantic_key": "trust", "label": "Trust"},
            headers=stranger_headers,
        ),
        await client.patch(
            f"/v1/workspaces/{workspace_id}/checkin-dimensions/{dim_id}",
            json={"label": "Hacked"},
            headers=stranger_headers,
        ),
        await client.post(
            f"/v1/workspaces/{workspace_id}/checkins",
            json={"responses": [{"dimension_id": dim_id, "value": 1}]},
            headers=stranger_headers,
        ),
        await client.get(
            f"/v1/workspaces/{workspace_id}/checkins/{checkin_id}", headers=stranger_headers
        ),
        await client.get(f"/v1/workspaces/{workspace_id}/checkins", headers=stranger_headers),
    ]
    for response in responses:
        assert response.status_code == 404, response.request.url
