# Admin-Panel-Erweiterung: App-Verwaltung (Feature-Flags, System-Überblick) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Das bestehende Admin-Panel (`/admin/*`, `routes/admin.py`, bereits mit Login/Nutzerverwaltung/Audit-Log) um eine Feature-Flag-Verwaltung und einen V2-System-Überblick erweitern, damit der Operator die App-weiten `AVENYTH_*`-Flags per Klick umschalten kann, statt SSH + `.env`-Edit + Container-Neustart zu brauchen.

**Architektur:** Die sieben `AVENYTH_*`-Flags wandern von Pydantic-Settings-Env-Vars in eine neue `feature_flags`-DB-Tabelle. Ein neuer `FeatureFlagService` liest mit kurzem In-Process-Cache (TTL ~5s) aus der DB; die bestehenden `require_v2_master`/`require_v2_phase`-FastAPI-Dependencies in `services/feature_flags.py` werden auf diesen Service umgestellt, ihre Signatur/ihr Guard-Verhalten bleibt für alle aufrufenden Router unverändert. Env-Vars (`AVENYTH_*_ENABLED`) werden zu reinen **Seed-Defaults** für die Migration (Audit-Stack und frische Deploys starten weiterhin mit denselben Werten wie heute) — nach der Migration ist die DB-Tabelle alleinige Quelle der Wahrheit, kein Dual-Read. Admin-UI-Seite `/admin/flags` zeigt alle sieben Flags mit Toggle; jede Änderung ist CSRF-geschützt, audit-geloggt (bestehendes `record_audit_event`-Muster) und wirkt beim nächsten Request sofort (max. Cache-TTL Verzögerung), ohne Container-Neustart. Zusätzlich: `/admin`-Dashboard um einen V2-Status-Block erweitert (Flag-Zustände auf einen Blick, `analysis_queued_gt_15min`/`analysis_failed_24h`/aktive Connections/Workspaces — dieselbe Abfrage, die wir heute manuell per SQL gefahren haben, jetzt dauerhaft im UI).

**Tech Stack:** FastAPI + SQLAlchemy (Alembic-Migration), bestehendes Admin-Router-Muster (`require_admin`, `require_csrf`), Next.js/React (`apps/web/src/app/admin/*`), bestehende `useAsync`/`api/client.ts`-Muster.

**Ausdrücklich NICHT Teil dieses Plans** (eigene, bereits dokumentierte Arbeitsaufträge, hier nur als Erweiterungspunkt vorgesehen, nicht gebaut):
- **A4 (Entitlements/Whitelist)** — eigener Arbeitsauftrag (`docs/planning/2026-09-26-p0-agent-work-orders.md` §A4). Die `/admin/flags`-Seite bekommt hier bewusst *keine* Pro-Nutzer-Spalte; sobald A4 existiert, ist das eine eigene Folge-Task auf Basis dieses Panels, kein Teil dieses Plans.
- **A7 (LLM-Nutzungs-/Kosten-Logging)** — eigener Arbeitsauftrag. Der V2-Status-Block zeigt bewusst keine Kosten-/Token-Zahlen, weil `llm_generations` noch nicht existiert.

---

## Datei-Struktur

| Datei | Zweck |
|---|---|
| `apps/api/alembic/versions/<neu>_feature_flags_table.py` | Neue Migration: `feature_flags`-Tabelle + Seed-Insert mit heutigen Produktionswerten |
| `apps/api/src/numra_api/models/tables.py` | Neues `FeatureFlag`-Model (Zeile ergänzen, bestehende Datei) |
| `apps/api/src/numra_api/repositories/feature_flags.py` | Neu: `get_all_flags`, `get_flag`, `set_flag` (mit Audit-Event-Schreiben) |
| `apps/api/src/numra_api/services/feature_flags.py` | Bestehende Datei umbauen: `require_v2_master`/`require_v2_phase` lesen jetzt über einen gecachten Service statt `Settings` |
| `apps/api/src/numra_api/services/feature_flag_cache.py` | Neu: einfacher In-Process-TTL-Cache (kein Redis-Zwang, Flags ändern sich selten) |
| `apps/api/src/numra_api/routes/admin.py` | Erweitern: `GET /v1/admin/flags`, `PATCH /v1/admin/flags/{name}` |
| `apps/api/src/numra_api/schemas/admin.py` | Erweitern: `FeatureFlagOut`, `FeatureFlagListOut`, `FeatureFlagUpdateIn` |
| `apps/web/src/app/admin/flags/page.tsx` | Neu: Flag-Toggle-Seite |
| `apps/web/src/app/admin/flags/__tests__/page.test.tsx` | Neu: Tests für Toggle-Seite |
| `apps/web/src/app/admin/page.tsx` | Erweitern: V2-Status-Block (bestehende Datei, Dashboard) |
| `apps/web/src/api/client.ts` | Erweitern: `api.admin.flags.list()`, `api.admin.flags.update()` |
| `apps/api/tests/integration/test_admin_flags.py` | Neu: Integrationstests (Toggle wirkt, Audit-Eintrag entsteht, CSRF greift, nicht-Admin bekommt 403) |

---

### Task 1: DB-Modell + Migration

**Dateien:**
- Modify: `apps/api/src/numra_api/models/tables.py`
- Create: `apps/api/alembic/versions/<neu>_feature_flags_table.py`
- Test: `apps/api/tests/unit/test_feature_flags_model.py`

- [ ] **Schritt 1: Model ergänzen**

```python
class FeatureFlag(Base):
    __tablename__ = "feature_flags"
    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
```

- [ ] **Schritt 2: Alembic-Migration erzeugen**

Run: `cd /opt/numra/repo && alembic -c apps/api/alembic.ini revision --autogenerate -m "feature_flags table"`
Migration von Hand prüfen (autogenerate verpasst oft Defaults) und den Seed-Insert ergänzen — **mit den heutigen echten Produktionswerten**, nicht mit `false` für alle:

```python
def upgrade() -> None:
    op.create_table(...)
    flags_table = sa.table(
        "feature_flags", sa.column("name", sa.String), sa.column("enabled", sa.Boolean)
    )
    op.bulk_insert(
        flags_table,
        [
            {"name": "v2_master", "enabled": True},
            {"name": "connections", "enabled": True},
            {"name": "relationship_workspaces", "enabled": True},
            {"name": "checkins", "enabled": False},
            {"name": "tasks", "enabled": False},
            {"name": "copilot", "enabled": True},
            {"name": "evidence_layer", "enabled": False},
        ],
    )
```

- [ ] **Schritt 3: Lokal gegen Audit-DB testen, dann committen**

Run: `alembic -c apps/api/alembic.ini upgrade head` gegen eine lokale/Audit-DB, `SELECT * FROM feature_flags` prüfen.

```bash
git add apps/api/src/numra_api/models/tables.py apps/api/alembic/versions/
git commit -m "feat: feature_flags-Tabelle mit heutigen Produktionswerten geseedet"
```

---

### Task 2: Repository + gecachter Service

**Dateien:**
- Create: `apps/api/src/numra_api/repositories/feature_flags.py`
- Create: `apps/api/src/numra_api/services/feature_flag_cache.py`
- Test: `apps/api/tests/unit/test_feature_flag_cache.py`

- [ ] **Schritt 1: Fehlschlagenden Test für den TTL-Cache schreiben**

```python
async def test_cache_returns_stale_value_within_ttl_then_refetches(monkeypatch):
    calls = 0

    async def fake_loader():
        nonlocal calls
        calls += 1
        return {"v2_master": calls == 1}

    cache = FeatureFlagCache(loader=fake_loader, ttl_seconds=0.05)
    first = await cache.get_all()
    second = await cache.get_all()
    assert first == second  # noch im TTL-Fenster, kein zweiter Loader-Call
    assert calls == 1
    await asyncio.sleep(0.06)
    third = await cache.get_all()
    assert calls == 2
```

- [ ] **Schritt 2: Test ausführen, Fehlschlag bestätigen**

Run: `pytest apps/api/tests/unit/test_feature_flag_cache.py -v`
Erwartung: FAIL (Modul existiert nicht)

- [ ] **Schritt 3: Minimalen Cache implementieren**

```python
import asyncio
import time
from collections.abc import Awaitable, Callable


class FeatureFlagCache:
    def __init__(
        self, loader: Callable[[], Awaitable[dict[str, bool]]], ttl_seconds: float = 5.0
    ) -> None:
        self._loader = loader
        self._ttl = ttl_seconds
        self._value: dict[str, bool] | None = None
        self._loaded_at = 0.0
        self._lock = asyncio.Lock()

    async def get_all(self) -> dict[str, bool]:
        now = time.monotonic()
        if self._value is not None and (now - self._loaded_at) < self._ttl:
            return self._value
        async with self._lock:
            now = time.monotonic()
            if self._value is not None and (now - self._loaded_at) < self._ttl:
                return self._value
            self._value = await self._loader()
            self._loaded_at = now
            return self._value

    def invalidate(self) -> None:
        self._value = None
```

- [ ] **Schritt 4: Test ausführen, Erfolg bestätigen**

Run: `pytest apps/api/tests/unit/test_feature_flag_cache.py -v` → PASS

- [ ] **Schritt 5: Repository-Funktionen (DB-Zugriff + Audit)**

```python
# repositories/feature_flags.py
async def get_all_flags(db: AsyncSession) -> dict[str, bool]:
    result = await db.execute(select(FeatureFlag))
    return {row.name: row.enabled for row in result.scalars()}


async def set_flag(db: AsyncSession, *, name: str, enabled: bool, actor_user_id: uuid.UUID) -> None:
    flag = await db.get(FeatureFlag, name)
    if flag is None:
        raise NotFoundError(f"unknown flag: {name}")
    previous = flag.enabled
    flag.enabled = enabled
    flag.updated_by_user_id = actor_user_id
    await record_audit_event(
        db,
        action=AuditAction.FEATURE_FLAG_CHANGED,
        actor_user_id=actor_user_id,
        safe_metadata={"flag": name, "from": previous, "to": enabled},
    )
    await db.commit()
```

(`AuditAction.FEATURE_FLAG_CHANGED` als neuer Enum-Wert in `models/enums.py` ergänzen — ein-Zeiler.)

- [ ] **Schritt 6: Singleton-Instanz + Invalidierung verdrahten, committen**

Ein modul-level `_cache = FeatureFlagCache(loader=...)` in `services/feature_flags.py`; `set_flag`-Aufrufer (Admin-Route) ruft nach dem Commit `_cache.invalidate()`, damit der nächste Request sofort den neuen Wert sieht statt bis zu 5s zu warten.

```bash
git add apps/api/src/numra_api/repositories/feature_flags.py apps/api/src/numra_api/services/feature_flag_cache.py apps/api/tests/unit/test_feature_flag_cache.py apps/api/src/numra_api/models/enums.py
git commit -m "feat: gecachtes Feature-Flag-Repository mit Audit-Log bei Aenderung"
```

---

### Task 3: Bestehende Guards auf den neuen Service umstellen

**Dateien:**
- Modify: `apps/api/src/numra_api/services/feature_flags.py:1-55` (siehe gelesener Ausschnitt oben)
- Test: bestehende `apps/api/tests/unit/test_feature_flags*.py` (falls vorhanden, sonst neu) + alle bestehenden Router-Tests, die `require_v2_master`/`require_v2_phase` indirekt testen, dürfen NICHT brechen

- [ ] **Schritt 1: Fehlschlagenden Test schreiben, der DB-Werte statt Env-Vars erwartet**

```python
async def test_require_v2_phase_reads_db_not_settings(db_session, monkeypatch):
    monkeypatch.setenv("AVENYTH_COPILOT_ENABLED", "false")  # Env sagt aus
    await set_flag(
        db_session, name="copilot", enabled=True, actor_user_id=some_admin_id
    )  # DB sagt an
    dependency = require_v2_phase("copilot")
    await dependency(settings=get_settings(), db=db_session)  # darf NICHT raisen
```

- [ ] **Schritt 2: Test ausführen, Fehlschlag bestätigen**

Run: `pytest apps/api/tests/unit/test_feature_flags.py -v -k db_not_settings`
Erwartung: FAIL (liest noch `settings.avenyth_copilot_enabled`)

- [ ] **Schritt 3: `require_v2_master`/`require_v2_phase` umbauen**

```python
def require_v2_master() -> Callable[..., None]:
    async def _dependency(db: AsyncSession = Depends(get_db, scope="function")) -> None:
        flags = await get_cached_flags(db)
        if not flags.get("v2_master", False):
            raise V2Disabled()

    return _dependency


def require_v2_phase(flag_name: Literal[...]) -> Callable[..., None]:
    async def _dependency(db: AsyncSession = Depends(get_db, scope="function")) -> None:
        flags = await get_cached_flags(db)
        if not flags.get("v2_master", False):
            raise V2Disabled()
        if not flags.get(flag_name, False):
            raise V2PhaseDisabled(flag_name)

    return _dependency
```

Wichtig (aus dem Docstring der bestehenden Datei): Reihenfolge Flag-Check **vor** Auth-Check in jedem Router bleibt exakt wie heute — hier ändert sich nur die Datenquelle, nicht die Guard-Reihenfolge oder -Semantik.

- [ ] **Schritt 4: Test ausführen, Erfolg bestätigen**

Run: `pytest apps/api/tests/unit/test_feature_flags.py -v` → PASS

- [ ] **Schritt 5: Vollen bestehenden Testlauf gegen Regressionen prüfen**

Run: `pytest apps/api/tests/ -x -q` (voller Lauf, nicht nur die neue Datei — jeder Router mit `require_v2_phase` hängt jetzt an der DB statt an Settings)
Erwartung: alle bisherigen Tests weiterhin grün; Test-Fixtures, die bisher `monkeypatch.setenv("AVENYTH_*_ENABLED", ...)` nutzen, müssen auf `set_flag(db, ...)` umgestellt werden — **das ist der aufwändigste Teil dieses Tasks**, vorher grep: `grep -rln "AVENYTH_.*_ENABLED" apps/api/tests/`

- [ ] **Schritt 6: Settings-Felder als deprecated markieren, nicht löschen**

`avenyth_*_enabled` in `config.py` bleiben als Felder bestehen (Migration-Seed liest sie einmalig), bekommen aber einen Kommentar `# DEPRECATED: nur noch Seed-Default fuer die Migration, Laufzeit-Wahrheit ist feature_flags-Tabelle`. Nicht entfernen — Minimal-Touch, keine Folgeschäden an `compose.production.yml`/`docs/ops/*`.

- [ ] **Schritt 7: Committen**

```bash
git add apps/api/src/numra_api/services/feature_flags.py apps/api/tests/
git commit -m "feat: V2-Flag-Guards lesen jetzt aus der DB statt aus Settings/Env"
```

---

### Task 4: Admin-API-Endpunkte

**Dateien:**
- Modify: `apps/api/src/numra_api/routes/admin.py` (Muster: siehe bestehende `/users/{user_id}/disable`-Route als Vorlage für CSRF+Audit+403-Handling)
- Modify: `apps/api/src/numra_api/schemas/admin.py`
- Create: `apps/api/tests/integration/test_admin_flags.py`

- [ ] **Schritt 1: Fehlschlagenden Integrationstest schreiben**

```python
async def test_non_admin_gets_403_on_flags_list(client, user_session):
    resp = await client.get("/v1/admin/flags", cookies=user_session)
    assert resp.status_code == 403


async def test_admin_can_toggle_flag_and_audit_entry_is_created(client, admin_session, db_session):
    resp = await client.patch(
        "/v1/admin/flags/checkins",
        json={"enabled": True},
        cookies=admin_session,
        headers={"X-CSRF-Token": admin_session_csrf_token},
    )
    assert resp.status_code == 204
    flags = await get_all_flags(db_session)
    assert flags["checkins"] is True
    events = await list_audit_events_paginated(db_session, limit=1)
    assert events[0].action == AuditAction.FEATURE_FLAG_CHANGED
```

- [ ] **Schritt 2: Tests ausführen, Fehlschlag bestätigen**

Run: `pytest apps/api/tests/integration/test_admin_flags.py -v`
Erwartung: FAIL (404, Route existiert nicht)

- [ ] **Schritt 3: Schemas ergänzen**

```python
# schemas/admin.py
class FeatureFlagOut(BaseModel):
    name: str
    enabled: bool
    updated_at: datetime
    updated_by_user_id: UUID | None


class FeatureFlagListOut(BaseModel):
    flags: list[FeatureFlagOut]


class FeatureFlagUpdateIn(BaseModel):
    enabled: bool
```

- [ ] **Schritt 4: Routen ergänzen**

```python
@router.get("/flags", response_model=FeatureFlagListOut)
async def list_flags(db: AsyncSession = Depends(get_db, scope="function")) -> FeatureFlagListOut:
    rows = await get_all_flags_with_metadata(db)
    return FeatureFlagListOut(flags=rows)


@router.patch(
    "/flags/{name}",
    status_code=204,
    dependencies=[Depends(require_csrf), Depends(rate_limit_by_user)],
)
async def update_flag(
    name: str,
    body: FeatureFlagUpdateIn,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> None:
    await set_flag(db, name=name, enabled=body.enabled, actor_user_id=admin.id)
    get_feature_flag_cache().invalidate()
```

- [ ] **Schritt 5: Tests ausführen, Erfolg bestätigen**

Run: `pytest apps/api/tests/integration/test_admin_flags.py -v` → PASS

- [ ] **Schritt 6: OpenAPI/TS-Typen regenerieren (Projekt-Pflicht laut api-contract.md)**

Run: `pnpm --filter @numra/schema generate` (bzw. das in `specs/v2/api-contract.md` genannte Kommando)

- [ ] **Schritt 7: Committen**

```bash
git add apps/api/src/numra_api/routes/admin.py apps/api/src/numra_api/schemas/admin.py apps/api/tests/integration/test_admin_flags.py openapi/
git commit -m "feat: Admin-Endpunkte fuer Feature-Flag-Liste und -Toggle"
```

---

### Task 5: Admin-Web-UI für Flags

**Dateien:**
- Create: `apps/web/src/app/admin/flags/page.tsx`
- Create: `apps/web/src/app/admin/flags/__tests__/page.test.tsx`
- Modify: `apps/web/src/api/client.ts`
- Modify: `apps/web/src/app/admin/page.tsx` (Link zur neuen Seite ergänzen, Muster: bestehende Links zu `/admin/users`, `/admin/audit`)

- [ ] **Schritt 1: Fehlschlagenden Komponententest schreiben**

```tsx
it("toggles a flag and shows the updated state after confirmation", async () => {
  vi.mocked(api.admin.flags.list).mockResolvedValue({ flags: [
    { name: "checkins", enabled: false, updated_at: "...", updated_by_user_id: null },
  ]});
  vi.mocked(api.admin.flags.update).mockResolvedValue(undefined);
  renderPage();
  fireEvent.click(await screen.findByRole("switch", { name: /checkins/i }));
  expect(await screen.findByRole("switch", { name: /checkins/i })).toHaveAttribute("aria-checked", "true");
  expect(api.admin.flags.update).toHaveBeenCalledWith("checkins", { enabled: true });
});
```

- [ ] **Schritt 2: Test ausführen, Fehlschlag bestätigen**

Run: `pnpm --filter @numra/web test -- --run src/app/admin/flags/__tests__/page.test.tsx`
Erwartung: FAIL (Modul existiert nicht)

- [ ] **Schritt 3: `api.admin.flags` im Client ergänzen**

```typescript
admin: {
  ...existingAdminMethods,
  flags: {
    list: () => request<FeatureFlagListOut>("GET", "/v1/admin/flags"),
    update: (name: string, body: { enabled: boolean }) =>
      request<void>("PATCH", `/v1/admin/flags/${name}`, { body }),
  },
},
```

- [ ] **Schritt 4: Seite implementieren**

Muster: bestehende `/admin/users/page.tsx` für Layout/AppShell/Fehlerzustände übernehmen. Pro Flag: Name, Beschreibungstext (statisch im Code, z.B. "Check-ins — konfigurierbare Beziehungs-Check-ins"), Toggle-Switch, `zuletzt geändert von/am`. Optimistisches UI-Update mit Rollback bei Fehler (gleiches Muster wie `private-notes-panel.tsx`s `startEdit`/`submitEdit`-Fehlerbehandlung).

- [ ] **Schritt 5: Test ausführen, Erfolg bestätigen**

Run: `pnpm --filter @numra/web test -- --run src/app/admin/flags/__tests__/page.test.tsx` → PASS

- [ ] **Schritt 6: Link im Admin-Dashboard ergänzen, committen**

```bash
git add apps/web/src/app/admin/flags/ apps/web/src/api/client.ts apps/web/src/app/admin/page.tsx
git commit -m "feat: Admin-UI zum Umschalten der AVENYTH-Feature-Flags"
```

---

### Task 6: V2-Status-Block im Admin-Dashboard

**Dateien:**
- Modify: `apps/api/src/numra_api/repositories/admin.py` (bestehende `compute_admin_stats`-Funktion erweitern)
- Modify: `apps/api/src/numra_api/schemas/admin.py` (`AdminStatsOut` erweitern)
- Modify: `apps/web/src/app/admin/page.tsx`
- Test: bestehende `test_admin_stats`-Tests erweitern (Datei lokalisieren: `grep -rl compute_admin_stats apps/api/tests/`)

- [ ] **Schritt 1: Fehlschlagenden Test für die erweiterten Stats schreiben**

```python
async def test_admin_stats_includes_v2_health(db_session, seeded_workspace_and_stale_job):
    stats = await compute_admin_stats(db_session, now=dt.datetime.now(dt.UTC))
    assert stats.v2.connections_active == 1
    assert stats.v2.workspaces_active == 1
    assert stats.v2.analysis_queued_gt_15min == 1
```

- [ ] **Schritt 2: Test ausführen, Fehlschlag bestätigen**

Run: `pytest apps/api/tests/ -v -k admin_stats_includes_v2_health`

- [ ] **Schritt 3: `AdminStatsOut` + `compute_admin_stats` erweitern**

Exakt dieselben fünf Kennzahlen, die wir heute manuell per SQL gefahren haben (siehe `docs/ops/2026-09-26-v2-activation-connections-workspaces.md` §6): `invitations_pending`, `connections_active`, `workspaces_active`, `analysis_queued_gt_15min`, `analysis_failed_24h` — als verschachteltes `v2: V2HealthOut`-Feld in `AdminStatsOut`, per SQLAlchemy-Query statt Rohsql.

- [ ] **Schritt 4: Test ausführen, Erfolg bestätigen**

Run: `pytest apps/api/tests/ -v -k admin_stats_includes_v2_health` → PASS

- [ ] **Schritt 5: Dashboard-UI ergänzen, committen**

Kachel-Block im bestehenden `/admin/page.tsx` (Muster: bestehende Stats-Karten), `analysis_queued_gt_15min > 0` visuell als Warnung (rot/gelb) hervorheben — genau das Signal, das laut Runbook ein Abbruchkriterium ist.

```bash
git add apps/api/src/numra_api/repositories/admin.py apps/api/src/numra_api/schemas/admin.py apps/web/src/app/admin/page.tsx apps/api/tests/
git commit -m "feat: V2-Gesundheitsstatus im Admin-Dashboard"
```

---

### Task 7: Dokumentation + Deploy

**Dateien:**
- Modify: `docs/ops/numra-topology.md` (neue Tabellenzeile: `feature_flags`-Tabelle als neue Konfigurationsquelle)
- Modify: `docs/planning/avenyth-pwa-execution-state.md`
- Modify: `docs/ops/2026-09-26-v2-activation-connections-workspaces.md` (§4 "Gemeinsame Befehle": Hinweis ergänzen, dass Flag-Änderungen ab jetzt über `/admin/flags` laufen, nicht mehr über `.env`-Edit + Neustart — alter Weg bleibt als Fallback dokumentiert, falls die API selbst nicht erreichbar ist)

- [ ] **Schritt 1: Deploy-Ablauf für diese PR festhalten**

Dieser Task erfordert — anders als reine Flag-Flips — einen echten Code-Deploy (Migration + neues `api`-Image), **keinen** reinen `.env`-Edit. Ablauf identisch zum heutigen Muster: PR mergen, `docs/ops/release-verification.md`-Gate, `$DC build && $DC up -d`, danach **zusätzlich**: `alembic upgrade head` gegen die Produktions-DB (Migrations-Einmaljob läuft das automatisch beim `up -d`, wie heute schon beobachtet).

- [ ] **Schritt 2: Nach dem Deploy: Manuelle Abnahme**

- `/admin/flags` aufrufen, alle 7 Flags zeigen die heutigen Produktionswerte (v2_master/connections/relationship_workspaces/copilot=an, checkins/tasks/evidence_layer=aus) — **Beweis, dass der Seed korrekt lief und kein Flag versehentlich zurückgesetzt wurde**
- Einen unkritischen Flag (`checkins`) testweise umschalten, `scripts/ops/v2-flag-probe.sh` zeigt die Änderung ohne Container-Neustart, dann zurückschalten
- Audit-Log (`/admin/audit`) zeigt den Toggle-Eintrag

- [ ] **Schritt 3: Dokumentation aktualisieren, committen**

```bash
git add docs/
git commit -m "docs: Feature-Flag-Verwaltung ueber Admin-UI dokumentieren"
```

---

## Risiken / offene Punkte für die Review-Runde

- **Migrations-Reihenfolge-Risiko:** Zwischen "Migration läuft" und "neuer `api`-Code mit DB-Read ist live" gibt es einen kurzen Fenster-Moment im Rolling-Restart, in dem alte Code-Version noch Settings/Env liest, während die Tabelle schon existiert — unkritisch, weil Env-Werte zu diesem Zeitpunkt identisch zum Seed sind, aber in der PR explizit als bewusst in Kauf genommen vermerken (gleiche Kategorie wie die Deploy-Reihenfolge-Überlegungen, die wir heute schon dokumentiert haben).
- **Cache-TTL-Wert (5s) ist eine Annahme**, keine Vorgabe aus den Specs — ggf. mit dem Produktinhaber kurz abstimmen, ob "sofort" wörtlicher gemeint ist (TTL 0, dafür DB-Last pro Request) oder 5s UX-seitig akzeptabel sind.
- **Audit-Action-Enum-Wert `FEATURE_FLAG_CHANGED`** ist neu — prüfen, ob es dafür bereits eine DB-Migration-Konvention für Enum-Erweiterungen gibt (Postgres-native Enums brauchen ggf. eine eigene `ALTER TYPE`-Migration, nicht nur Python-Enum-Änderung).
