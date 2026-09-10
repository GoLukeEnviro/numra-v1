from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select, update
from test_checkins import _connect, _signup, _switch_user

from numra_api.models import (
    CheckinAnalysis,
    CheckinIdempotency,
    CheckinResponse,
    CheckinTemplate,
    RelationshipCheckin,
    RelationshipWorkspace,
    User,
    WorkspaceMember,
)
from numra_api.models.enums import WorkspaceMemberStatus

ANALYSIS_FIELDS = {
    "absolute_gap",
    "direction",
    "rolling_trend",
    "sample_size",
    "historical_delta",
    "sufficient_evidence",
}
ROUND_FIELDS = {
    "id",
    "workspace_id",
    "checkin_template_version",
    "status",
    "cycle_started_at",
    "snapshot_origin",
    "snapshot_recorded",
    "dimensions",
}
OUT_FIELDS = ROUND_FIELDS | {"my_responses", "partner_submitted", "analysis"}


async def _setup(client, sessionmaker):
    wid = await _connect(client, sessionmaker, "new-a@example.com", "new-b@example.com")
    headers = await _switch_user(client, "new-a@example.com")
    base = f"/v1/workspaces/{wid}"
    start = await client.post(f"{base}/checkins/rounds", headers=headers)
    assert start.status_code == 201
    assert set(start.json()) == ROUND_FIELDS
    return wid, base, headers, start.json()


def _payload(round_body, value=8):
    return {
        "round_id": round_body["id"],
        "responses": [
            {"dimension_id": d["dimension_id"], "value": value} for d in round_body["dimensions"]
        ],
    }


def _privacy(body, value, partner):
    assert set(body) == OUT_FIELDS
    assert body["partner_submitted"] is partner
    for answer in body["my_responses"]:
        assert set(answer) == {"dimension_id", "semantic_key", "value", "submitted_at"}
        assert answer["value"] == value
    if body["analysis"]:
        assert set(body["analysis"]) == {"computed_at", "result"}
        assert len(body["analysis"]["result"]) == len(body["dimensions"])
        for entry in body["analysis"]["result"].values():
            assert set(entry) == ANALYSIS_FIELDS


async def test_replay_completion_privacy_dissolve_and_authorization(client, sessionmaker):
    wid, base, headers, round_body = await _setup(client, sessionmaker)
    body = _payload(round_body)
    current = (await client.get(f"{base}/checkins/current")).json()
    _privacy(current, 8, False)
    assert current["my_responses"] == []
    first = await client.post(f"{base}/checkins", json=body, headers=headers)
    assert first.status_code == 201
    _privacy(first.json(), 8, False)
    replay = await client.post(f"{base}/checkins", json=body, headers=headers)
    assert replay.json() == first.json()
    reordered = {**body, "responses": list(reversed(body["responses"]))}
    assert (
        await client.post(f"{base}/checkins", json=reordered, headers=headers)
    ).json() == first.json()
    conflict = await client.post(f"{base}/checkins", json=_payload(round_body, 4), headers=headers)
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "CHECKIN_IDEMPOTENCY_CONFLICT"
    b = await _switch_user(client, "new-b@example.com")
    b["Idempotency-Key"] = headers["Idempotency-Key"]  # actor namespace is separate
    before = (await client.get(f"{base}/checkins/current")).json()
    _privacy(before, 2, True)
    assert before["my_responses"] == [] and before["analysis"] is None
    second = await client.post(f"{base}/checkins", json=_payload(round_body, 2), headers=b)
    assert second.status_code == 201
    _privacy(second.json(), 2, True)
    assert second.json()["status"] == "ANALYZED"
    a = await _switch_user(client, "new-a@example.com")
    a["Idempotency-Key"] = headers["Idempotency-Key"]
    for route in ["checkins/current", f"checkins/{round_body['id']}"]:
        _privacy((await client.get(f"{base}/{route}")).json(), 8, True)
    after = await client.post(f"{base}/checkins", json=body, headers=a)
    assert after.status_code == 201
    assert after.json()["status"] == "ANALYZED"
    _privacy(after.json(), 8, True)
    start_replay = await client.post(f"{base}/checkins/rounds", headers=a)
    assert start_replay.status_code == 201 and start_replay.json()["id"] == round_body["id"]
    different = {**a, "Idempotency-Key": "different-attempt"}
    duplicate = await client.post(f"{base}/checkins", json=body, headers=different)
    assert duplicate.json()["code"] == "CHECKIN_ALREADY_SUBMITTED"
    async with sessionmaker() as db:
        assert (await db.scalar(select(func.count()).select_from(RelationshipCheckin))) == 1
        assert (await db.scalar(select(func.count()).select_from(CheckinAnalysis))) == 1
        assert (await db.scalar(select(func.count()).select_from(CheckinResponse))) == 10
        workspace = await db.get(RelationshipWorkspace, uuid.UUID(wid))
        connection = str(workspace.connection_id)
    dissolved = await client.post(f"/v1/connections/{connection}/dissolve", headers=a)
    assert dissolved.status_code == 200
    for route, request_body in [("checkins", body), ("checkins/rounds", None)]:
        response = await client.post(f"{base}/{route}", json=request_body, headers=a)
        assert response.status_code == 409
        assert response.json()["code"] == "WORKSPACE_DISSOLVED"
    _privacy((await client.get(f"{base}/checkins/current")).json(), 8, True)
    async with sessionmaker() as db:
        user = await db.scalar(select(User).where(User.email == "new-a@example.com"))
        await db.execute(
            update(WorkspaceMember)
            .where(WorkspaceMember.user_id == user.id)
            .values(status=WorkspaceMemberStatus.REMOVED)
        )
        await db.commit()
    assert (await client.post(f"{base}/checkins", json=body, headers=a)).status_code == 404


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "duplicate",
        "extra",
        "foreign",
        "low",
        "high",
        "malformed",
        "missing_round",
        "missing_key",
    ],
)
async def test_submission_validation_does_not_echo_values(client, sessionmaker, case, caplog):
    _, base, headers, round_body = await _setup(client, sessionmaker)
    body = _payload(round_body)
    code = "CHECKIN_RESPONSES_INCOMPLETE"
    if case == "missing":
        body["responses"].pop()
    elif case == "duplicate":
        body["responses"][-1] = body["responses"][0]
    elif case in ("extra", "foreign"):
        extra = {"dimension_id": str(uuid.uuid4()), "value": 8}
        if case == "foreign":
            body["responses"][0] = extra
        else:
            body["responses"].append(extra)
    elif case in ("low", "high"):
        body["responses"][0]["value"] = -98765 if case == "low" else 98765
        code = "CHECKIN_VALUE_OUT_OF_RANGE"
    elif case == "malformed":
        body["responses"][0]["value"] = "private-invalid-answer"
        code = "CHECKIN_REQUEST_INVALID"
    elif case == "missing_round":
        del body["round_id"]
        code = "CHECKIN_REQUEST_INVALID"
    else:
        del headers["Idempotency-Key"]
        code = "CHECKIN_REQUEST_INVALID"
    response = await client.post(f"{base}/checkins", json=body, headers=headers)
    assert response.status_code == 422
    assert response.json()["code"] == code
    assert set(response.json()) <= {"code", "message", "detail"}
    for error in response.json().get("detail", []):
        assert set(error) == {"loc", "type"}
    assert "private-invalid-answer" not in response.text + caplog.text
    assert "98765" not in response.text + caplog.text
    assert (await client.get(f"{base}/checkins/current")).json()["my_responses"] == []
    async with sessionmaker() as db:
        assert await db.scalar(select(func.count()).select_from(CheckinResponse)) == 0
        assert await db.scalar(select(func.count()).select_from(CheckinIdempotency)) == 1


async def test_versions_snapshots_locks_and_trend_segmentation(client, sessionmaker):
    wid, base, headers, round_body = await _setup(client, sessionmaker)
    dimension = round_body["dimensions"][0]
    for method, path, body in [
        ("post", "/checkin-dimensions", {"semantic_key": "trust", "label": "Trust"}),
        ("patch", f"/checkin-dimensions/{dimension['dimension_id']}", {"label": "new label"}),
        ("patch", "", {"relationship_type": "WORK"}),
    ]:
        result = await getattr(client, method)(base + path, json=body, headers=headers)
        assert result.status_code == 409
        assert result.json()["code"] == "CHECKIN_ROUND_OPEN"
    for email, value in [("new-a@example.com", 7), ("new-b@example.com", 3)]:
        h = await _switch_user(client, email)
        response = await client.post(
            f"{base}/checkins", json=_payload(round_body, value), headers=h
        )
        assert response.status_code == 201
    before = (await client.get(f"{base}/checkins/{round_body['id']}")).json()
    headers = await _switch_user(client, "new-a@example.com")
    changed = await client.patch(
        f"{base}/checkin-dimensions/{dimension['dimension_id']}",
        json={"label": "Current label"},
        headers=headers,
    )
    assert changed.status_code == 200
    assert changed.json()["id"] != dimension["dimension_id"]
    # Stale ID targets the same semantic identity in the newest version.
    changed_again = await client.patch(
        f"{base}/checkin-dimensions/{dimension['dimension_id']}",
        json={"description": "Current description"},
        headers=headers,
    )
    assert changed_again.json()["label"] == "Current label"
    latest = (await client.get(f"{base}/checkin-template")).json()
    assert latest["version"] == 2
    historical = (await client.get(f"{base}/checkin-template?version=1")).json()
    assert historical["active"] is False
    old_d = next(d for d in historical["dimensions"] if d["id"] == dimension["dimension_id"])
    assert old_d["label"] == dimension["label"]
    assert (await client.get(f"{base}/checkin-template?version=999")).status_code == 404
    after = (await client.get(f"{base}/checkins/{round_body['id']}")).json()
    assert after["dimensions"] == before["dimensions"]
    assert after["analysis"] == before["analysis"]
    round2 = (await client.post(f"{base}/checkins/rounds", headers=headers)).json()
    assert round2["checkin_template_version"] == 2
    for email in ["new-a@example.com", "new-b@example.com"]:
        h = await _switch_user(client, email)
        final = await client.post(f"{base}/checkins", json=_payload(round2, 5), headers=h)
        assert final.status_code == 201
    for entry in final.json()["analysis"]["result"].values():
        assert entry["sample_size"] == 1
        assert entry["direction"] == "NO_PRIOR_DATA"
        assert entry["sufficient_evidence"] is False
    async with sessionmaker() as db:
        assert (
            await db.scalar(
                select(func.count())
                .select_from(CheckinTemplate)
                .where(CheckinTemplate.workspace_id == uuid.UUID(wid), CheckinTemplate.active)
            )
            == 1
        )


async def test_config_initialization_scale_classes_and_empty_round(client, sessionmaker):
    wid = await _connect(client, sessionmaker, "cfg-a@example.com", "cfg-b@example.com")
    base = f"/v1/workspaces/{wid}"
    headers = await _switch_user(client, "cfg-a@example.com")
    duplicate = await client.post(
        f"{base}/checkin-dimensions",
        json={"semantic_key": "closeness", "label": "dup"},
        headers=headers,
    )
    assert duplicate.status_code == 409
    for minimum, maximum in [(5, 5), (9, 3), (-1, 10), (1, 101)]:
        invalid = await client.post(
            f"{base}/checkin-dimensions",
            json={
                "semantic_key": "invalid",
                "label": "Invalid",
                "scale_min": minimum,
                "scale_max": maximum,
            },
            headers=headers,
        )
        assert invalid.status_code == 422
    assert (
        await client.patch(base, json={"relationship_type": "WORK"}, headers=headers)
    ).status_code == 200
    for key, classification in [("sexual_connection", None), ("custom_intimate", "INTIMATE")]:
        response = await client.post(
            f"{base}/checkin-dimensions",
            json={"semantic_key": key, "label": "Custom", "dimension_class": classification},
            headers=headers,
        )
        assert response.status_code == 422
        assert response.json()["code"] == "DIMENSION_NOT_ALLOWED_FOR_RELATIONSHIP_TYPE"
    # Deliberately no semantic detection of arbitrary unclassified free text.
    unrestricted = await client.post(
        f"{base}/checkin-dimensions",
        json={"semantic_key": "custom_text", "label": "Arbitrary text"},
        headers=headers,
    )
    assert unrestricted.status_code == 201
    dimensions = (await client.get(f"{base}/checkin-template")).json()["dimensions"]
    for d in dimensions:
        assert (
            await client.patch(
                f"{base}/checkin-dimensions/{d['id']}", json={"active": False}, headers=headers
            )
        ).status_code == 200
    start = await client.post(f"{base}/checkins/rounds", headers=headers)
    assert start.status_code == 422 and start.json()["code"] == "CHECKIN_NO_ACTIVE_DIMENSIONS"
    assert (await client.get(f"{base}/checkins/current")).json() is None


async def test_non_member_scoping_and_dissolved_get_does_not_seed(client, sessionmaker):
    wid = await _connect(client, sessionmaker, "scope-a@example.com", "scope-b@example.com")
    base = f"/v1/workspaces/{wid}"
    headers = await _switch_user(client, "scope-a@example.com")
    async with sessionmaker() as db:
        workspace = await db.get(RelationshipWorkspace, uuid.UUID(wid))
        connection = str(workspace.connection_id)
    assert (
        await client.post(f"/v1/connections/{connection}/dissolve", headers=headers)
    ).status_code == 200
    assert (await client.get(f"{base}/checkin-template")).status_code == 404
    assert (await client.get(f"{base}/checkins/current")).json() is None
    assert (await client.get(f"{base}/checkins")).json() == []
    async with sessionmaker() as db:
        assert await db.scalar(select(func.count()).select_from(CheckinTemplate)) == 0
    foreign = await _signup(client, sessionmaker, "scope-stranger@example.com")
    for method, path, body in [
        ("get", "/checkins/current", None),
        ("get", "/checkin-template", None),
        ("post", "/checkins/rounds", None),
        (
            "post",
            "/checkins",
            {
                "round_id": str(uuid.uuid4()),
                "responses": [{"dimension_id": str(uuid.uuid4()), "value": 8}],
            },
        ),
        ("post", "/checkin-dimensions", {"semantic_key": "new", "label": "New"}),
        ("patch", f"/checkin-dimensions/{uuid.uuid4()}", {"active": True}),
    ]:
        kwargs = {"headers": foreign}
        if method != "get":
            kwargs["json"] = body
        assert (await getattr(client, method)(base + path, **kwargs)).status_code == 404


async def test_explicit_round_current_and_idempotency(client, sessionmaker):
    workspace = await _connect(client, sessionmaker, "round-a@example.com", "round-b@example.com")
    headers = await _switch_user(client, "round-a@example.com")
    base = f"/v1/workspaces/{workspace}"
    empty = await client.get(f"{base}/checkins/current")
    assert empty.status_code == 200
    assert empty.json() is None
    headers["Idempotency-Key"] = "start-attempt"
    first = await client.post(f"{base}/checkins/rounds", headers=headers)
    assert first.status_code == 201
    replay = await client.post(f"{base}/checkins/rounds", headers=headers)
    assert replay.json() == first.json()
    assert len(first.json()["dimensions"]) == 5
    assert first.json()["snapshot_origin"] == "ROUND_START"


async def test_intimate_auto_retirement_versions_and_type_noop(client, sessionmaker):
    wid = await _connect(client, sessionmaker, "int-a@example.com", "int-b@example.com")
    base = f"/v1/workspaces/{wid}"
    h = await _switch_user(client, "int-a@example.com")
    assert (
        await client.patch(base, json={"relationship_type": "PARTNER"}, headers=h)
    ).status_code == 200
    custom = await client.post(
        f"{base}/checkin-dimensions",
        json={
            "semantic_key": "sexual_connection",
            "label": "Connection",
            "dimension_class": None,
            "scale_min": 3,
            "scale_max": 5,
        },
        headers=h,
    )
    assert custom.status_code == 201 and custom.json()["dimension_class"] == "INTIMATE"
    round_body = (await client.post(f"{base}/checkins/rounds", headers=h)).json()
    assert (
        await client.patch(base, json={"relationship_type": "PARTNER"}, headers=h)
    ).status_code == 200
    for email, value in [("int-a@example.com", 3), ("int-b@example.com", 5)]:
        headers = await _switch_user(client, email)
        submitted = await client.post(
            f"{base}/checkins", json=_payload(round_body, value), headers=headers
        )
        assert submitted.status_code == 201
    before = (await client.get(f"{base}/checkins/{round_body['id']}")).json()
    changed = await client.patch(base, json={"relationship_type": "WORK"}, headers=headers)
    assert changed.status_code == 200
    current = (await client.get(f"{base}/checkin-template")).json()
    assert current["version"] == 2
    intimate = next(d for d in current["dimensions"] if d["semantic_key"] == "sexual_connection")
    assert intimate["active"] is False and intimate["retired_at"] is not None
    old = (await client.get(f"{base}/checkin-template?version=1")).json()
    assert (
        next(d for d in old["dimensions"] if d["semantic_key"] == "sexual_connection")["active"]
        is True
    )
    blocked = await client.patch(
        f"{base}/checkin-dimensions/{custom.json()['id']}", json={"active": True}, headers=headers
    )
    assert blocked.status_code == 422
    assert (await client.get(f"{base}/checkins/{round_body['id']}")).json() == before


async def test_round_mismatch_foreign_dimensions_and_key_workspace_namespace(client, sessionmaker):
    wid, base, headers, original = await _setup(client, sessionmaker)
    unknown = await client.post(
        f"{base}/checkins",
        json={**_payload(original), "round_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert unknown.status_code == 409 and unknown.json()["code"] == "CHECKIN_ROUND_MISMATCH"
    # A connects to a different real member, creating a second workspace.
    invite = (
        await client.post("/v1/connections/invitations", json={"method": "LINK"}, headers=headers)
    ).json()
    c = await _signup(client, sessionmaker, "new-c@example.com")
    redeemed = await client.post(
        "/v1/connections/invitations/redeem", json={"token": invite["token"]}, headers=c
    )
    assert redeemed.status_code == 201
    other_base = f"/v1/workspaces/{redeemed.json()['workspace_id']}"
    a = await _switch_user(client, "new-a@example.com")
    a["Idempotency-Key"] = headers["Idempotency-Key"]
    other = await client.post(f"{other_base}/checkins/rounds", headers=a)
    assert other.status_code == 201 and other.json()["id"] != original["id"]
    assert (await client.post(f"{other_base}/checkins/rounds", headers=a)).json() == other.json()
    foreign = _payload(original)
    foreign["responses"][0]["dimension_id"] = other.json()["dimensions"][0]["dimension_id"]
    rejected = await client.post(f"{base}/checkins", json=foreign, headers=a)
    assert rejected.status_code == 422 and rejected.json()["code"] == "CHECKIN_RESPONSES_INCOMPLETE"
    cross_round = await client.post(f"{other_base}/checkins", json=_payload(original), headers=a)
    assert cross_round.status_code == 409
    # A submit does not create a round in another workspace or accept foreign IDs.
    assert (await client.get(f"{base}/checkins/current")).json()["my_responses"] == []
    assert (await client.get(f"{other_base}/checkins/current")).json()["my_responses"] == []


@pytest.mark.parametrize("location", ["submit", "answer", "start", "start_invalid_json"])
async def test_unknown_payload_is_not_ignored(client, sessionmaker, location):
    _, base, headers, round_body = await _setup(client, sessionmaker)
    if location == "start_invalid_json":
        response = await client.post(
            f"{base}/checkins/rounds",
            content="{broken",
            headers={**headers, "content-type": "application/json"},
        )
    else:
        body = _payload(round_body)
        path = "checkins"
        if location == "submit":
            body["unexpected"] = "private-extra"
        elif location == "answer":
            body["responses"][0]["unexpected"] = "private-extra"
        else:
            body = {"unexpected": "private-extra"}
            path = "checkins/rounds"
        response = await client.post(f"{base}/{path}", json=body, headers=headers)
    assert response.status_code == 422
    assert response.json()["code"] == "CHECKIN_REQUEST_INVALID"
    assert "private-extra" not in response.text
