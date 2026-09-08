"""PR-V2-11 -- Evidence Results und Pattern Analyses ueber die echte HTTP-Route
(routes/evidence.py). Deckt die drei Acceptance-Checks aus
specs/v2/evidence-policy.md ab:

1. Kein Korrelations-Statement ohne Stichprobengroesse, Beobachtungszeitraum und
   Konfidenzkategorie.
2. `NO_RELIABLE_PATTERN` ist erreichbar und wird korrekt ausgeliefert (HTTP 200).
3. Life Tracking ueberschreibt nie die kanonische Personal-Day-Berechnung.
"""

from __future__ import annotations

import datetime as dt

import pytest

from numra_api.auth.passwords import hash_password
from numra_api.models import LifeTrackingEntry
from numra_api.repositories.users import create_user
from numra_numerology.engine import calculate_profile
from numra_numerology.models.person import PersonInput

pytestmark = pytest.mark.integration

_BIRTH_DATE = dt.date(1986, 7, 18)  # entspricht dem `lukas_payload`-Fixture
_WINDOW_START = dt.date(2026, 1, 1)
_WINDOW_DAYS = 60


async def _login(client, sessionmaker, email: str) -> dict:
    async with sessionmaker() as db:
        await create_user(db, email=email, password_hash=hash_password("password12345"))
        await db.commit()
    await client.post("/v1/auth/logout")
    response = await client.post(
        "/v1/auth/login", json={"email": email, "password": "password12345"}
    )
    assert response.status_code == 200
    return {"x-csrf-token": client.cookies["numra_csrf"]}


async def _create_person(client, headers, lukas_payload) -> str:
    response = await client.post("/v1/people", json=lukas_payload, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


def _canonical_personal_day(target_date: dt.date) -> int:
    """Unabhaengiger Aufruf des Kanons -- bewusst ueber `calculate_profile`, NICHT
    ueber `timing.lookup`, damit dieser Test nicht gegen denselben Helfer prueft,
    den der Service benutzt."""
    person = PersonInput(
        birth_first_names="Lukas", birth_last_name="Springer", birth_date=_BIRTH_DATE
    )
    return calculate_profile(person, as_of_date=target_date).timing.personal_day.effective_value


def _dominant_personal_day() -> int:
    """Der Personal-Day-Wert, der im Testfenster am haeufigsten vorkommt -- garantiert
    genug Bucket-Treffer fuer die Policy-Mindestzahl."""
    counts: dict[int, int] = {}
    for offset in range(_WINDOW_DAYS):
        value = _canonical_personal_day(_WINDOW_START + dt.timedelta(days=offset))
        counts[value] = counts.get(value, 0) + 1
    return max(counts, key=lambda value: (counts[value], -value))


async def _seed_window(
    sessionmaker, *, user_id, person_id, target_value: int, high: int, low: int
) -> None:
    """Setzt `energy` auf `high` an genau den Tagen, deren KANONISCHER Personal Day
    `target_value` ist, sonst auf `low`. Direkt ueber die Session statt ueber 60
    HTTP-Requests -- geprueft wird die Leseseite."""
    async with sessionmaker() as db:
        for offset in range(_WINDOW_DAYS):
            entry_date = _WINDOW_START + dt.timedelta(days=offset)
            is_target = _canonical_personal_day(entry_date) == target_value
            db.add(
                LifeTrackingEntry(
                    user_id=user_id,
                    person_id=person_id,
                    entry_date=entry_date,
                    energy=high if is_target else low,
                )
            )
        await db.commit()


async def _user_id(sessionmaker, email: str):
    from sqlalchemy import select

    from numra_api.models import User

    async with sessionmaker() as db:
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one().id


async def test_reliable_pattern_statement_carries_all_mandatory_qualifiers(
    client, sessionmaker, lukas_payload
) -> None:
    """Acceptance-Check 1."""
    email = "evidence-strong@example.com"
    headers = await _login(client, sessionmaker, email)
    person_id = await _create_person(client, headers, lukas_payload)
    user_id = await _user_id(sessionmaker, email)
    target = _dominant_personal_day()
    await _seed_window(
        sessionmaker, user_id=user_id, person_id=person_id, target_value=target, high=9, low=3
    )

    response = await client.get(
        f"/v1/people/{person_id}/evidence-results",
        params={
            "metric_key": "energy",
            "correlation_target": "PERSONAL_DAY",
            "correlation_target_value": target,
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()

    assert body["confidence_category"] in ("LOW", "MEDIUM", "HIGH")
    assert body["sample_size"] == _WINDOW_DAYS
    assert body["observation_window_days"] == _WINDOW_DAYS
    assert body["evidence_policy_version"] == 1

    statement = body["statement_text"]
    assert statement is not None
    assert f"Stichprobe: {body['sample_size']} Tage" in statement
    assert f"Beobachtungszeitraum: {body['observation_window_days']} Tage" in statement
    assert body["confidence_category"] in statement
    # Nie kausal.
    assert "verursacht" not in statement.lower()


async def test_no_reliable_pattern_is_http_200_without_statement(
    client, sessionmaker, lukas_payload
) -> None:
    """Acceptance-Check 2: unterhalb der Policy-Minima ist das leere Ergebnis ein
    gueltiger Befund, kein Fehler."""
    email = "evidence-sparse@example.com"
    headers = await _login(client, sessionmaker, email)
    person_id = await _create_person(client, headers, lukas_payload)
    user_id = await _user_id(sessionmaker, email)

    async with sessionmaker() as db:
        for offset in range(5):
            db.add(
                LifeTrackingEntry(
                    user_id=user_id,
                    person_id=person_id,
                    entry_date=_WINDOW_START + dt.timedelta(days=offset),
                    energy=7,
                )
            )
        await db.commit()

    response = await client.get(
        f"/v1/people/{person_id}/evidence-results",
        params={
            "metric_key": "energy",
            "correlation_target": "PERSONAL_DAY",
            "correlation_target_value": 5,
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["confidence_category"] == "NO_RELIABLE_PATTERN"
    assert body["statement_text"] is None
    assert body["effect_size"] is None
    assert body["sample_size"] == 5


async def test_entries_land_in_the_canonical_personal_day_bucket(
    client, sessionmaker, lukas_payload
) -> None:
    """Acceptance-Check 3: der Bucket wird aus dem Kanon abgeleitet, nicht aus
    irgendetwas am Eintrag Gespeichertem. Beweis: nur die unabhaengig ueber
    `calculate_profile` bestimmte Zielzahl liefert einen Befund; eine andere Zahl
    tut es nicht."""
    email = "evidence-canon@example.com"
    headers = await _login(client, sessionmaker, email)
    person_id = await _create_person(client, headers, lukas_payload)
    user_id = await _user_id(sessionmaker, email)
    target = _dominant_personal_day()
    other = next(
        value
        for value in range(1, 10)
        if value != target
        and sum(
            _canonical_personal_day(_WINDOW_START + dt.timedelta(days=offset)) == value
            for offset in range(_WINDOW_DAYS)
        )
        >= 5
    )
    await _seed_window(
        sessionmaker, user_id=user_id, person_id=person_id, target_value=target, high=9, low=3
    )

    hit = await client.get(
        f"/v1/people/{person_id}/evidence-results",
        params={
            "metric_key": "energy",
            "correlation_target": "PERSONAL_DAY",
            "correlation_target_value": target,
        },
        headers=headers,
    )
    miss = await client.get(
        f"/v1/people/{person_id}/evidence-results",
        params={
            "metric_key": "energy",
            "correlation_target": "PERSONAL_DAY",
            "correlation_target_value": other,
        },
        headers=headers,
    )

    assert hit.json()["bucket_mean"] == 9.0
    # Der andere Bucket enthaelt ausschliesslich Nicht-Zieltage.
    assert miss.json()["bucket_mean"] in (3.0, None)
    assert miss.json()["bucket_mean"] != 9.0


async def test_unknown_metric_key_is_not_found(client, sessionmaker, lukas_payload) -> None:
    headers = await _login(client, sessionmaker, "evidence-metric@example.com")
    person_id = await _create_person(client, headers, lukas_payload)

    response = await client.get(
        f"/v1/people/{person_id}/evidence-results",
        params={
            "metric_key": "gibtsnicht",
            "correlation_target": "PERSONAL_DAY",
            "correlation_target_value": 5,
        },
        headers=headers,
    )
    assert response.status_code == 404


async def test_invalid_correlation_target_is_rejected(client, sessionmaker, lukas_payload) -> None:
    headers = await _login(client, sessionmaker, "evidence-target@example.com")
    person_id = await _create_person(client, headers, lukas_payload)

    response = await client.get(
        f"/v1/people/{person_id}/evidence-results",
        params={
            "metric_key": "energy",
            "correlation_target": "MONDPHASE",
            "correlation_target_value": 5,
        },
        headers=headers,
    )
    assert response.status_code == 422


async def test_evidence_results_foreign_person_is_not_found(
    client, sessionmaker, lukas_payload
) -> None:
    headers_a = await _login(client, sessionmaker, "evidence-iso-a@example.com")
    person_id_a = await _create_person(client, headers_a, lukas_payload)
    headers_b = await _login(client, sessionmaker, "evidence-iso-b@example.com")

    response = await client.get(
        f"/v1/people/{person_id_a}/evidence-results",
        params={
            "metric_key": "energy",
            "correlation_target": "PERSONAL_DAY",
            "correlation_target_value": 5,
        },
        headers=headers_b,
    )
    assert response.status_code == 404


async def test_pattern_analysis_is_recomputed_server_side_and_persisted(
    client, sessionmaker, lukas_payload
) -> None:
    """Der POST-Body traegt nur die Frage. Das gespeicherte Ergebnis stammt aus
    derselben serverseitigen Berechnung wie der GET -- ein Client kann
    `sample_size`/`confidence_category` nicht setzen."""
    email = "evidence-save@example.com"
    headers = await _login(client, sessionmaker, email)
    person_id = await _create_person(client, headers, lukas_payload)
    user_id = await _user_id(sessionmaker, email)
    target = _dominant_personal_day()
    await _seed_window(
        sessionmaker, user_id=user_id, person_id=person_id, target_value=target, high=9, low=3
    )

    live = (
        await client.get(
            f"/v1/people/{person_id}/evidence-results",
            params={
                "metric_key": "energy",
                "correlation_target": "PERSONAL_DAY",
                "correlation_target_value": target,
            },
            headers=headers,
        )
    ).json()

    created = await client.post(
        f"/v1/people/{person_id}/pattern-analyses",
        json={
            "metric_key": "energy",
            "correlation_target": "PERSONAL_DAY",
            "correlation_target_value": target,
            # Wird ignoriert -- es gibt kein Feld dafuer im Request-Schema.
            "sample_size": 999999,
            "confidence_category": "HIGH",
        },
        headers=headers,
    )
    assert created.status_code == 201
    analysis = created.json()
    assert analysis["evidence_policy_version"] == 1
    assert analysis["result"] == live
    assert analysis["result"]["sample_size"] == _WINDOW_DAYS

    listed = await client.get(f"/v1/people/{person_id}/pattern-analyses", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    fetched = await client.get(f"/v1/pattern-analyses/{analysis['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["result"] == live

    deleted = await client.delete(f"/v1/pattern-analyses/{analysis['id']}", headers=headers)
    assert deleted.status_code == 204
    assert (
        await client.get(f"/v1/pattern-analyses/{analysis['id']}", headers=headers)
    ).status_code == 404


async def test_pattern_analysis_isolated_per_user(client, sessionmaker, lukas_payload) -> None:
    email = "evidence-pa-a@example.com"
    headers_a = await _login(client, sessionmaker, email)
    person_id = await _create_person(client, headers_a, lukas_payload)
    user_id = await _user_id(sessionmaker, email)
    target = _dominant_personal_day()
    await _seed_window(
        sessionmaker, user_id=user_id, person_id=person_id, target_value=target, high=9, low=3
    )
    analysis = (
        await client.post(
            f"/v1/people/{person_id}/pattern-analyses",
            json={
                "metric_key": "energy",
                "correlation_target": "PERSONAL_DAY",
                "correlation_target_value": target,
            },
            headers=headers_a,
        )
    ).json()

    headers_b = await _login(client, sessionmaker, "evidence-pa-b@example.com")
    assert (
        await client.get(f"/v1/pattern-analyses/{analysis['id']}", headers=headers_b)
    ).status_code == 404
    assert (
        await client.delete(f"/v1/pattern-analyses/{analysis['id']}", headers=headers_b)
    ).status_code == 404
