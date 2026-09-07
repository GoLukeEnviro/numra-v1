# AVENYTH V2 — Final Product Transformation Master Command

> Status: **FROZEN** (Produktentscheidungen final, Stand 2026-09-07).
> Dieses Dokument ist der verbindliche Ausgangspunkt für Phase 0
> (READ-ONLY Recon → PR #15 Assessment → Spec/ADR-Gate) und alle
> nachfolgenden PR-V2-xx-Phasen. Keine Feature-/DB-Mutation vor
> abgeschlossenem Phase-0-Spec-Gate (siehe Abschnitt 5 und 59).

## Eingefrorene Entscheidungen

| # | Entscheidung |
|---|---|
| 1 | **AVENYTH** wird Produktname |
| 2 | Branding umbenennen, technische `numra_*`-Namespaces zunächst behalten |
| 3 | Repo `numra-v1` während V2-Umbau behalten |
| 4 | Minderjährige Profile erlaubt, **keine eigenen Accounts** (Managed Profiles) |
| 5 | Alle Beziehungstypen ab V2 |
| 6 | Invite-Link + Code + E-Mail |
| 7 | Default Sharing: Core Numerology + Relationship Insights + Current Timing |
| 8 | Check-in-Dimensionen **konfigurierbar** (versioniert, Default-Set aus 5 Dimensionen) |
| 9 | Rohantworten bleiben privat; gemeinsam nur abgeleitete Ergebnisse |
| 10 | Shared + Private Relationship Copilot |
| 11 | Nach Disconnect gemeinsame historische Artefakte read-only erhalten |
| 12 | Web/PWA zuerst, Native später |
| 13 | Entitlements jetzt, echtes Billing später |
| 14 | Ollama bleibt primär, Provider-Abstraktion |
| 15 | Life Tracking / Evidence erst nach Relationship Core |

---

## Master Prompt (verbatim)

```text
===============================================================================
AVENYTH V2
FINAL PRODUCT TRANSFORMATION MASTER COMMAND
===============================================================================

Repository:
GoLukeEnviro/numra-v1

Current product:
NUMRA V1.6

Target product:
AVENYTH V2

Execution model:
PHASED / TEST-GATED / PRODUCTION-SAFE

===============================================================================
ROLE
===============================================================================

Du bist Principal Product Architect, Staff Backend Engineer, Staff Frontend
Engineer, Security Engineer, Data Architect, AI Systems Engineer und Release
Engineer.

Deine Aufgabe ist die vollständige Transformation der bestehenden NUMRA-V1-
Plattform zu AVENYTH V2.

Du baust NICHT neu.

Du erhältst:

- den bestehenden deterministischen Numerologie-Canon,
- bestehende Golden Fixtures,
- bestehende FastAPI-Architektur,
- PostgreSQL,
- bestehende serverseitige Sessions,
- bestehende Reports,
- bestehende LLM-Abstraktion,
- bestehende PWA,
- Today / Timing,
- Relationships V1,
- RBAC/Admin,
- PDF,
- CI,
- Docker,
- Production Deployment.

Darauf wird V2 additiv und kontrolliert aufgebaut.

===============================================================================
0. FINAL PRODUCT VISION
===============================================================================

AVENYTH ist:

"Personal & Relationship Development OS based on deterministic numerology."

Das Produkt ist keine:

- generische Habit-App,
- Dating-Swipe-App,
- Social-Media-Plattform,
- klassische Horoskop-App,
- KI, die Numerologie selbst errechnet.

Das Produkt besteht aus vier Wahrheits-/Verarbeitungsebenen:

1. Canonical Engine
2. Curated Knowledge
3. Structured Workspace Evidence
4. LLM Interpretation

Architektur:

Canonical Engine
      ↓
Canonical Profile
      ↓
Knowledge Base
      ↓
Structured Personal / Relationship Context
      ↓
Deterministic Analysis Services
      ↓
LLM Renderer / Copilot
      ↓
Validated User-facing Insight

GRUNDPRINZIP:

Numerology provides context.

User data provides evidence.

Deterministic/statistical services calculate.

The LLM interprets and renders.

NO EVIDENCE -> NO CLAIM.

===============================================================================
1. ABSOLUTE INVARIANTS
===============================================================================

packages/engine-numerology bleibt:

- deterministic,
- network-free,
- DB-free,
- LLM-free.

Gleicher Input -> gleicher Output.

Bestehende Canon-Versionen und Golden Fixtures dürfen nicht kosmetisch verändert
werden.

Das LLM darf NIEMALS authoritative calculations durchführen.

Insbesondere nicht:

- Life Path
- Expression
- Soul Urge
- Personality
- Timing
- Pinnacles
- Challenges
- Karmic Lessons
- Hidden Passion
- Compatibility %
- Check-in Gaps
- Trends
- Correlations
- Scores
- Sample sizes
- Effect sizes

Diese Werte werden ausschließlich deterministisch erzeugt.

===============================================================================
2. BRAND DECISION — FROZEN
===============================================================================

Public product brand:

AVENYTH

User-facing Branding wird von NUMRA auf AVENYTH umgestellt.

Technische Namespaces bleiben zunächst bestehen.

NICHT blind umbenennen:

numra_numerology
numra_interpretation
numra_api
numra-canonical
existing database identifiers
migration history
canonical IDs
hash inputs
fixture IDs
calculation_version

Grund:

Branding ist keine Canon-Migration.

Erstelle eine zentrale Brand Configuration.

Beispiel:

APP_BRAND_NAME=AVENYTH

Bestehende technische Altbezeichnungen dokumentieren.

Repository bleibt während V2:

GoLukeEnviro/numra-v1

Kein Repository-Rename während des Core-Umbaus.

===============================================================================
3. CURRENT REPOSITORY BASELINE
===============================================================================

Vor jeder Änderung:

git fetch --all --prune

Ermittle:

CURRENT_MAIN_SHA

Vergleiche niemals blind gegen einen in diesem Prompt genannten alten SHA.

Prüfe:

- main
- branch protection
- open PRs
- migrations
- schemas
- OpenAPI
- CI
- production docs
- Docker
- current deployment contracts

Alle vorhandenen 12 Pflichtchecks müssen weiterhin erhalten bleiben:

lint-python

python-typecheck

unit-and-property-tests

no-golden-leakage

dependency-security

schema-and-openapi-drift

web-lint-typecheck-build-test

pdf-service-tests

docker-build

docker-compose-e2e

playwright

system-e2e

===============================================================================
4. PR #15 MUST BE RESOLVED FIRST
===============================================================================

Historischer Draft:

PR #15
feat/report-prompt-v3

Nicht blind mergen.

Vergleiche vollständig gegen aktuellen main.

Klassifiziere relevante Änderungen:

KEEP
PORT
SUPERSEDED
DROP

Besonders prüfen:

- prompt versioning
- placeholder coverage
- grounding
- repair prompts
- linter hardening
- knowledge additions
- report v3 architecture

Wenn sinnvoll:

sauber auf aktuellen main portieren.

Wenn überholt:

PR #15 als superseded schließen.

V2-Featureentwicklung beginnt erst danach.

===============================================================================
5. V2 SPECIFICATION FREEZE
===============================================================================

BEVOR Feature-Code entsteht, folgende Spezifikationen erzeugen:

specs/v2/product-vision.md

specs/v2/architecture.md

specs/v2/personal-workspace-spec.md

specs/v2/connection-spec.md

specs/v2/relationship-workspace-spec.md

specs/v2/relationship-type-spec.md

specs/v2/consent-spec.md

specs/v2/shadow-dynamics-spec.md

specs/v2/checkin-spec.md

specs/v2/task-system-spec.md

specs/v2/roadmap-spec.md

specs/v2/copilot-grounding-spec.md

specs/v2/evidence-policy.md

specs/v2/minor-profile-policy.md

specs/v2/privacy-spec.md

specs/v2/data-model.md

specs/v2/api-contract.md

specs/v2/dissolution-policy.md

Zusätzlich:

docs/adr/008-v2-product-architecture.md

docs/adr/009-v2-relationship-workspaces.md

docs/adr/010-v2-consent-model.md

docs/adr/011-v2-llm-grounding.md

docs/adr/012-v2-managed-minor-profiles.md

docs/adr/013-v2-workspace-dissolution.md

Kein Featurecode vor Spec-Gate.

===============================================================================
6. ACCOUNT AGE / MINOR PROFILE POLICY — FROZEN
===============================================================================

AVENYTH Accounts selbst sind ausschließlich:

18+

Minderjährige erhalten:

KEINEN eigenen User Account.

Minderjährige dürfen als:

Managed Person Profile

unter einem volljährigen Account existieren.

Kennzeichnung:

person_account_mode:

SELF
MANAGED_MINOR
MANAGED_OTHER

Für MANAGED_MINOR:

- kein eigener Login,
- keine direkte private Copilot-Identität,
- keine öffentliche Discovery,
- kein eigener Connection Account,
- kein eigener Shared Workspace Member,
- keine Partner-/Dating-Beziehungstypen,
- kein öffentliches Profil,
- keine Direktnachrichten.

Zulässige Kontexte können sein:

PARENT_CHILD
FAMILY
SIBLINGS

falls fachlich sinnvoll.

Geburtsdatum bestimmt, ob ein Managed Profile minderjährig ist.

Alter wird deterministisch aus:

birth_date
+
as_of_date

bestimmt.

Keine hardcodierten dauerhaften "minor=true"-Wahrheiten ohne überprüfbare Basis.

Ein minderjähriges Profil kann später bei Volljährigkeit NICHT automatisch in ein
User-Konto umgewandelt werden.

Eine explizite Claim-/Transfer-Spezifikation wäre dafür später erforderlich.

===============================================================================
7. AUTH — KEEP CURRENT MODEL
===============================================================================

Bestehende opaque server-side sessions bleiben authoritative.

KEIN unnötiger Wechsel zu:

JWT
OAuth
OIDC
Refresh-token architecture

für V2 Web.

Ergänzen:

Email verification

Forgot password

Password reset

Token model:

- random cryptographically secure token
- only token hash persisted
- single use
- expiry
- replay protection
- rate limiting

Routen ungefähr:

POST /v1/auth/request-email-verification

POST /v1/auth/verify-email

POST /v1/auth/forgot-password

POST /v1/auth/reset-password

Anti-enumeration:

Forgot-password Antwort darf nicht verraten,
ob ein Account existiert.

Nach erfolgreichem Password Reset:

alle bestehenden Sessions revoken.

===============================================================================
8. ENTITLEMENTS — NOW, BILLING LATER
===============================================================================

Jetzt implementieren:

GET /v1/me/entitlements

Server-authoritative.

Keine verstreuten:

if premium

if subscription

if plan == ...

Checks.

Beispiel:

EntitlementSet:

personal_workspace
connections
relationship_workspaces
relationship_checkins
relationship_copilot
advanced_relationship_analysis
life_tracking
premium_reports
max_connections
max_workspaces

Anfangs:

alles für Beta freischaltbar.

Payment Provider:

später.

===============================================================================
9. PERSONAL WORKSPACE
===============================================================================

Personal Workspace wird um bestehendes Person/Calculation-Modell gebaut.

Nicht Canonical Profile duplizieren.

Calculation bleibt immutable snapshot.

Personal Workspace enthält:

PROFILE

CORE NUMBERS

STRENGTHS

SHADOWS

DEVELOPMENT

RELATIONSHIPS

COMMUNICATION

NEEDS

WORK / EXPRESSION

TIMING

PINNACLES

CHALLENGES

KARMIC LESSONS

HIDDEN PASSION

REPORTS

PRIVATE REFLECTIONS

PRIVATE NOTES

PRIVATE TASKS

PRIVATE COPILOT

Bestehende Today-/Daily-Brief-Daten wiederverwenden.

===============================================================================
10. INTERPRETATION ARCHITECTURE
===============================================================================

Personal interpretations:

CanonicalProfile
+
versioned Knowledge Base
+
allowed private workspace context
↓
structured InterpretationContext
↓
LLM
↓
validated output

LLM-Ausgaben werden:

versioned
cached
auditable
regenerable

Speichere:

calculation_version
knowledge_version
prompt_version
model_provider
model_name
generation metadata

===============================================================================
11. CONNECTION SYSTEM — FROZEN
===============================================================================

V2 verbindet echte User Accounts.

Connection methods:

INVITE_LINK
INVITE_CODE
EMAIL

Kein:

public people directory

Kein:

username search

für V2 Core.

Entities:

ConnectionInvitation

UserConnection

RelationshipWorkspace

WorkspaceMember

ConsentGrant

ConsentEvent

Invitation states:

PENDING
ACCEPTED
DECLINED
EXPIRED
REVOKED

Ein RelationshipWorkspace wird nur erstellt wenn:

User A invite
+
User B accepts
+
beide volljährige Accounts
+
Consent erfolgreich

===============================================================================
12. RELATIONSHIP TYPES — ALL ENABLED
===============================================================================

V2 unterstützt:

PARTNER

DATING

FRIENDSHIP

FAMILY

SIBLINGS

PARENT_CHILD

WORK

OTHER

Canonical numbers bleiben identisch.

Nur Interpretation Frame ändert sich.

Beispiel:

PARTNER:

intimacy
attachment-needs as non-diagnostic reflection
communication
autonomy
closeness
long-term collaboration

FRIENDSHIP:

trust
support
boundaries
growth
communication

WORK:

collaboration
communication
structure
autonomy
responsibility
power dynamics

FAMILY:

family roles
long-term patterns
boundaries
support
expectations

Keine Formulierung:

familial karma obligation

als hartes Systemaxiom.

Relationship Frames werden versioniert und in der Knowledge Base definiert.

===============================================================================
13. DEFAULT CONSENT — FROZEN
===============================================================================

Beim Connection Setup standardmäßig freigegeben:

CORE_NUMEROLOGY

RELATIONSHIP_INSIGHTS

CURRENT_TIMING

NICHT standardmäßig freigegeben:

PRIVATE_JOURNAL

PRIVATE_TASKS

PRIVATE_COPILOT

OTHER_RELATIONSHIPS

LIFE_TRACKING

Alle Consent Grants sind:

directional
versioned
auditable
revocable

Beispiel:

Luke kann Sarah CURRENT_TIMING teilen.

Sarah kann CURRENT_TIMING widerrufen,
ohne Lukes Freigabe automatisch zu verändern.

===============================================================================
14. CONSENT ENFORCEMENT
===============================================================================

Frontend-Verstecken ist niemals Security.

Jeder Datenzugriff muss serverseitig prüfen:

current_user
workspace_membership
consent_scope
resource ownership
workspace state

Consent revoke:

sofort wirksam.

Keine Cache-Lücke.

Keine bereits erstellte neue Inference nach Widerruf mit revoked data.

===============================================================================
15. LEGACY RELATIONSHIPS
===============================================================================

Bestehende V1 RelationshipComparison:

gehört nur einem User.

Diese darf nicht automatisch in V2 Shared Workspace konvertiert werden.

Grund:

historisch existierte kein mutual consent.

Legacy Comparisons dürfen:

read-only sichtbar bleiben.

Optional später:

"Invite this person to AVENYTH"

Workflow.

Erst nach realer Verbindung entsteht Shared Workspace.

===============================================================================
16. RELATIONSHIP WORKSPACE
===============================================================================

RelationshipWorkspace:

genau zwei aktive erwachsene User-Mitglieder in V2.

Sections:

OVERVIEW

DUAL PROFILE

COMMUNICATION

CLOSENESS

AUTONOMY

NEEDS

STRENGTHS

CONFLICT DYNAMICS

SHADOW DYNAMICS

DEVELOPMENT AREAS

TIMING DYNAMICS

CHECKINS

TASKS

ROADMAPS

SHARED REFLECTION

SHARED GOALS

COPILOT

===============================================================================
17. SHADOW DYNAMICS
===============================================================================

LLM erfindet KEINE Schattenseiten.

Pipeline:

CanonicalProfile A
+
CanonicalProfile B
+
RelationshipType
+
Curated Shadow Knowledge
+
Relationship rules
+
allowed evidence
↓
StructuredShadowContext
↓
LLM Renderer
↓
ShadowDynamicsResult

Structured result:

user_a_shadow_themes

user_b_shadow_themes

interaction_pattern

escalation_loop

deescalation_opportunities

pattern_intensity

recommended_micro_tasks

Jede Theme-Aussage muss provenance besitzen:

canonical refs

knowledge refs

workspace evidence refs falls benutzt.

Keine psychiatrische Diagnose.

Keine Persönlichkeitsstörung.

Kein Attachment-Style als Diagnose.

===============================================================================
18. CHECK-IN SYSTEM — CONFIGURABLE
===============================================================================

NICHT hart nur fünf Dimensionen.

Jeder Relationship Workspace erhält eine:

CheckinTemplate

CheckinTemplate ist versioniert.

Default Template enthält:

closeness

communication

understanding

autonomy

conflict_load

Scale:

1..10

Nutzer können später konfigurieren:

Dimension aktivieren/deaktivieren

eigene Dimension ergänzen

Label ändern,
sofern der historische semantic_id erhalten bleibt.

Custom dimension:

id
workspace_id
semantic_key
label
description
scale_min
scale_max
sort_order
active
created_at
retired_at

Ein bereits verwendeter semantic_key wird niemals rückwirkend neu definiert.

Historische Antworten bleiben an:

checkin_template_version

gebunden.

Beispiele zusätzlicher Dimensionen:

trust
emotional_safety
quality_time
support
sexual_connection

Letzteres nur für geeignete erwachsene Relationship Types.

Keine sexualisierte Dimension in:

PARENT_CHILD
SIBLINGS
WORK
managed minor contexts

===============================================================================
19. CHECK-IN PRIVACY — FROZEN
===============================================================================

Jeder Teilnehmer reicht separat ein.

Raw answers:

SUBMITTER_ONLY

Partner darf rohe Zahlen des anderen NICHT lesen.

Nach beiden Submissions erzeugt:

CheckinAnalysisService

deterministisch:

absolute_gap

direction

rolling_trend

sample_size

historical_delta

sufficient_evidence

Partner sehen:

derived shared analysis

nicht:

raw answer values

des Gegenübers.

===============================================================================
20. CHECK-IN ANALYSIS
===============================================================================

LLM berechnet NICHT:

gap
trend
mean
delta
sample size

Backend Service berechnet.

Danach:

CheckinAnalysis JSON
↓
LLM Renderer

LLM erklärt nur.

===============================================================================
21. SHARED TASK SYSTEM
===============================================================================

Task types:

PERSONAL_PRIVATE

FOR_PARTNER_PROPOSED

JOINT_SHARED

AVENYTH_SUGGESTED

Lifecycle:

PROPOSED

ACCEPTED

ACTIVE

COMPLETED

DECLINED

ARCHIVED

FOR_PARTNER_PROPOSED:

erst sichtbar/aktiv nach definiertem Proposal Flow.

Empfänger muss akzeptieren.

AVENYTH_SUGGESTED:

niemals automatisch aktiv.

User kann:

accept
edit
decline
archive

AI suggestions speichern provenance:

source_analysis_id
prompt_version
knowledge_version

===============================================================================
22. ROADMAPS
===============================================================================

Roadmap types:

14_DAY

30_DAY

QUARTER

Structure:

Roadmap
Milestone
Task
ReviewPoint

LLM darf Roadmap vorschlagen.

LLM darf keine Erfüllung markieren.

State transitions sind server-authoritative.

Roadmaps können:

accepted
edited
archived

werden.

===============================================================================
23. SHARED REFLECTION
===============================================================================

Shared Journal / Conversation Topics existieren.

Aber:

private reflection

wird NIEMALS automatisch shared.

Expliziter:

SHARE

Flow erforderlich.

Frontend muss klar unterscheiden:

PRIVATE

SHARED

===============================================================================
24. COPILOT MODES — FROZEN
===============================================================================

Es gibt BEIDE Modi.

A. RELATIONSHIP_SHARED

Luke
Sarah
AVENYTH

Beide sehen:

alle Messages
alle Responses

B. RELATIONSHIP_PRIVATE

Luke fragt AVENYTH mit erlaubtem Shared Relationship Context.

Sarah sieht:

NICHT Lukes Frage
NICHT AVENYTHs Antwort
NICHT daraus erzeugte Summary

Private thread darf niemals Shared Thread Memory kontaminieren.

===============================================================================
25. THREAD MODEL
===============================================================================

Entities:

ChatThread

ChatMessage

ThreadSummary

ThreadContextSnapshot

ThreadScope enum:

PERSONAL_PRIVATE

RELATIONSHIP_PRIVATE

RELATIONSHIP_SHARED

Jeder Thread hat:

workspace_id nullable

owner_user_id nullable

scope

context_version

created_at

archived_at

Shared Thread:

owner_user_id NULL

Private Relationship Thread:

owner_user_id = requester

===============================================================================
26. COPILOT CONTEXT BUILDER
===============================================================================

Implementiere einen expliziten:

ContextBuilder

Nicht ad hoc Prompts aus DB zusammensetzen.

ContextBuilder prüft:

user
workspace
thread scope
relationship type
consent grants
resource visibility
historical summaries

Context darf enthalten:

authorized canonical values

authorized Knowledge Base content

authorized shared workspace data

requester's own private data

validated previous thread summaries

Context darf NICHT enthalten:

partner private journal

partner private task

partner private Copilot

other relationships

other profiles

admin information

secrets

revoked scopes

===============================================================================
27. PROMPT INJECTION
===============================================================================

Alle Journal-/Chat-/Reflection-Inhalte gelten als:

UNTRUSTED_USER_DATA

Prompt Layer trennt:

SYSTEM_POLICY

CANONICAL_FACTS

KNOWLEDGE_CONTEXT

AUTHORIZED_WORKSPACE_CONTEXT

UNTRUSTED_USER_DATA

USER_QUERY

User content kann niemals System Instructions verändern.

===============================================================================
28. LLM TRUTH CLASSIFICATION
===============================================================================

Jede Insight-Aussage erhält:

basis_type

Enum:

NUMEROLOGY_MODEL

OBSERVED_WORKSPACE_DATA

MIXED

INSUFFICIENT_EVIDENCE

NUMEROLOGY_MODEL:

"Das numerologische Modell legt nahe ..."

OBSERVED_WORKSPACE_DATA:

"Eure bisherigen Check-ins zeigen ..."

MIXED:

beide Ebenen explizit getrennt.

INSUFFICIENT_EVIDENCE:

"Für eine belastbare Aussage liegen noch nicht genügend Daten vor."

===============================================================================
29. NO COMPATIBILITY PERCENTAGE
===============================================================================

V2 baut KEIN:

87% compatible

82/100 relationship score

match percentage

Solange kein eigener:

relationship-score-spec.md

formula

version

golden fixture

property tests

existiert.

Qualitative dimensions sind erlaubt.

===============================================================================
30. MANAGED MINOR PROFILES
===============================================================================

Wegen Produktentscheidung:

Minderjährige dürfen als verwaltete Person Profiles existieren.

Sie dürfen NICHT:

UserConnection Member sein.

Sie dürfen NICHT:

eigenen Login haben.

Sie dürfen NICHT:

Relationship Private Copilot besitzen.

Sie dürfen NICHT:

Dating / Partner Workspace Target sein.

PARENT_CHILD Analyse ist zulässig.

Beispiel:

Adult User Luke
+
Managed Minor Child Profile

kann eine private Parent-Child numerologische Analyse erzeugen.

Dies ist KEIN Shared Workspace mit einem Kinderaccount.

Wenn zwei erwachsene Sorgeberechtigte auf dasselbe Managed Minor Profile zugreifen
sollen, braucht es einen expliziten späteren:

ManagedProfileSharing

Mechanismus.

Nicht implizit freigeben.

===============================================================================
31. DISCONNECT POLICY — FROZEN
===============================================================================

Disconnect:

future data access ends immediately.

Consent = revoked.

Workspace status:

DISSOLVED

Bereits gemeinsam erzeugte Artefakte bleiben:

immutable
read-only

für beide Teilnehmer.

Beispiele:

past roadmap

past shared Copilot thread

past completed task

past relationship analysis

dürfen lesbar bleiben.

Aber:

keine Regeneration.

Keine neue Inference.

Keine neue Datenaggregation.

Keine neue private source context retrieval.

===============================================================================
32. DISSOLUTION DATA RULES
===============================================================================

Nach Disconnect:

Shared artifacts:

RETAIN_READ_ONLY

Private source data:

REVOKE_ACCESS

Future shared operations:

DISABLED

Consent:

REVOKED

Chat:

read-only

Tasks:

archived or read-only

Roadmaps:

read-only

Check-ins:

historic shared derived results retained

Raw private answers:

bleiben ausschließlich beim ursprünglichen User.

===============================================================================
33. DELETE ACCOUNT
===============================================================================

Account deletion muss Shared Workspace korrekt behandeln.

Definiere:

private content deletion

shared artifact handling

participant anonymization

remaining participant access

audit handling

PII removal

Keine orphaned PII.

Wenn gemeinsame Artefakte rechtlich/technisch erhalten bleiben:

gelöschten Nutzer pseudonymisieren/anonymisieren,
wenn möglich und zulässig.

Keine fremden Private Source Data zurücklassen.

===============================================================================
34. LIFE TRACKING — PHASE 6
===============================================================================

Erst nach erfolgreichem Relationship Core.

Life Tracking ist Evidence Layer.

Nicht Hauptprodukt.

Possible metrics:

mood

energy

sleep

stress

focus

custom metric

Daily entry speichert NICHT Personal Day/Month/Year als neue Wahrheit.

Speichern:

person_id

date

calculation_id

metric values

Timing wird vom Canon berechnet.

===============================================================================
35. EVIDENCE POLICY
===============================================================================

Statistische Aussagen brauchen deterministische Regeln.

Erstelle:

EvidencePolicy

Versioniert.

Beinhaltet:

minimum total sample count

minimum sample count per bucket

minimum observation window

missing-data handling

outlier policy

multiple-comparison protection

effect-size threshold

confidence category

Keine magische fixe Zahl ohne dokumentierte Begründung.

Output kann sein:

NO_RELIABLE_PATTERN

Das ist ein valides und erwünschtes Ergebnis.

===============================================================================
36. CORRELATION LANGUAGE
===============================================================================

Nie:

"Personal Day 5 verursacht höhere Energie."

Erlaubt:

"An den bislang beobachteten Personal-Day-5-Tagen lag deine gemessene
Energie im Mittel höher als deine persönliche Baseline."

Immer:

sample size

observation period

uncertainty category

anzeigen.

===============================================================================
37. LLM PROVIDER — FROZEN
===============================================================================

Bestehender Ollama Provider bleibt primär.

Provider abstraction erhalten und verbessern.

Kein silent fallback.

Provider interface muss ermöglichen:

future provider B

aber kein zweiter Provider ist für V2 Core Pflicht.

Bei Provider-Ausfall:

Canonical Engine bleibt verfügbar.

Relationship calculations bleiben verfügbar.

LLM Operation:

QUEUED / RETRYABLE / UNAVAILABLE

mit sauberer UX.

===============================================================================
38. WEB/PWA FIRST — FROZEN
===============================================================================

V2 Core wird zuerst vollständig in bestehender:

Next.js PWA

gebaut und getestet.

Nicht sofort parallel komplette React-Native-App bauen.

Warum:

Relationship Loop zuerst validieren.

V2 Web Scope:

Profile

Connections

Relationship Workspace

Check-ins

Tasks

Roadmaps

Copilot

===============================================================================
39. NATIVE MOBILE — AFTER CORE
===============================================================================

Nach V2-Core-Acceptance:

apps/mobile

Expo / React Native

Initial scope:

Home

Profile

Today

Connections

Relationship Workspace

Check-ins

Tasks

Copilot

Push

Reports/PDF/Admin können web-first bleiben.

===============================================================================
40. BRAND DESIGN
===============================================================================

AVENYTH Design Language:

Graphite

Deep Navy

Muted Plum

Antique Gold

Warm Ivory

Visual semantics:

individual identity

connection

shared growth

pattern recognition

clarity

Avoid:

cheap zodiac aesthetic

slot-machine numerology

neon casino

excessive gamification

===============================================================================
41. PRIMARY NAVIGATION
===============================================================================

Web/PWA primary navigation:

Home

Profile

Connections

Workspaces

Today

Copilot

Settings

Admin only if ADMIN.

Relationship Workspace tabs approximately:

Overview

Dynamics

Check-in

Tasks

Roadmap

Journal

Copilot

===============================================================================
42. DATA MODEL — TARGET ENTITIES
===============================================================================

Existing:

User

Session

Person

NameIdentity

Calculation

RelationshipComparison

Report

ReportSection

ReportJob

LLMGeneration

Export

AdminAuditEvent

New likely entities:

EmailVerificationToken

PasswordResetToken

EntitlementSet or EntitlementAssignment

ConnectionInvitation

UserConnection

RelationshipWorkspace

WorkspaceMember

ConsentGrant

ConsentEvent

RelationshipAnalysis

ShadowDynamicsAnalysis

CheckinTemplate

CheckinDimension

RelationshipCheckin

CheckinResponse

CheckinAnalysis

WorkspaceTask

TaskAcceptance

RelationshipRoadmap

RoadmapMilestone

SharedReflection

ChatThread

ChatMessage

ThreadSummary

ThreadContextSnapshot

InsightSnapshot

EvidenceMetricDefinition

EvidenceEntry

PatternAnalysis

Exact final schema must be designed in specs first.

===============================================================================
43. DATABASE RULES
===============================================================================

PostgreSQL authoritative.

Prefer normalized relational tables for:

ownership

membership

permissions

consent

state

timestamps

Use JSONB for:

versioned structured generated content

snapshot payloads

LLM validated structured outputs

Do NOT store critical authorization rules only in JSONB.

===============================================================================
44. ROW-LEVEL SECURITY
===============================================================================

Existing API-level authorization remains required.

Evaluate PostgreSQL Row-Level Security as defense-in-depth.

Do NOT introduce RLS blindly if it destabilizes existing SQLAlchemy patterns.

Document ADR:

RLS adopted
or
RLS deferred with reason.

Application authorization remains mandatory either way.

===============================================================================
45. OPTIMISTIC CONCURRENCY
===============================================================================

Do NOT add CRDT/OT in V2 Core.

Use:

version

updated_at

ETag / If-Match

or equivalent optimistic locking

for edit conflicts.

CRDT only if future live collaborative document editing genuinely requires it.

===============================================================================
46. REALTIME
===============================================================================

Do NOT force general WebSockets.

Use REST by default.

Use SSE/streaming where needed for:

LLM response streaming.

Add realtime transport only for demonstrated requirements.

===============================================================================
47. OBSERVABILITY
===============================================================================

Add metrics:

connections_invited_total

connections_accepted_total

connections_declined_total

connections_revoked_total

relationship_workspaces_active

relationship_workspaces_dissolved

consent_granted_total

consent_revoked_total

checkins_submitted_total

checkins_completed_pair_total

tasks_proposed_total

tasks_accepted_total

tasks_completed_total

roadmaps_created_total

copilot_requests_total

copilot_validation_failures_total

llm_latency_ms

llm_token_usage

llm_estimated_cost

Never analytics-log:

journal contents

chat text

private notes

raw birth profile content

===============================================================================
48. TESTING
===============================================================================

Existing engine:

near 100%.

Golden Fixture:

unchanged.

New domain logic:

target >= 90% where deterministic and security-sensitive.

Mandatory:

unit tests

integration tests

migration tests

authorization tests

consent tests

IDOR tests

lifecycle tests

LLM schema tests

LLM leakage tests

prompt-injection tests

Playwright

real two-user browser E2E

===============================================================================
49. TWO-USER AUTHORIZATION MATRIX
===============================================================================

Create two real users:

USER_A

USER_B

Verify A cannot access B:

private profile data

private notes

private tasks

private reflection

private Copilot

other workspaces

raw check-in response

managed minor private profile

unless explicit relevant consent/share mechanism exists.

Verify B same against A.

===============================================================================
50. COMPLETE V2 E2E JOURNEY
===============================================================================

User A registers.

Email verified.

Profile created.

Calculation generated.

Personal Workspace works.

User B registers.

Email verified.

Profile created.

Calculation generated.

A sends invite.

B accepts.

Relationship type selected.

Consent configured.

Workspace created.

Dual profile renders.

Relationship Analysis generated.

Shadow Dynamics generated.

Check-in Template configured.

A submits private Check-in.

B submits private Check-in.

Derived shared analysis appears.

Neither sees other's raw answers.

AVENYTH suggests task.

Task accepted.

Joint task completed.

14-day roadmap generated.

Users edit roadmap.

Shared Copilot conversation works.

A creates private relationship Copilot thread.

B cannot access it.

A revokes CURRENT_TIMING consent.

B loses access immediately.

Existing historical shared artifact remains available where policy allows.

A/B disconnect.

Workspace becomes dissolved/read-only.

No new inference possible.

Private source access gone.

===============================================================================
51. MINOR PROFILE E2E
===============================================================================

Adult account creates Managed Minor Profile.

System calculates profile.

No account credentials exist for minor.

No Connection Invitation may target minor profile.

No PARTNER/DATING relationship type allowed involving minor profile.

PARENT_CHILD private analysis works.

Minor private data cannot leak into unrelated workspace.

Delete managed minor profile removes associated private data safely.

===============================================================================
52. FEATURE FLAGS
===============================================================================

Introduce:

AVENYTH_V2_ENABLED

AVENYTH_CONNECTIONS_ENABLED

AVENYTH_RELATIONSHIP_WORKSPACES_ENABLED

AVENYTH_CHECKINS_ENABLED

AVENYTH_TASKS_ENABLED

AVENYTH_COPILOT_ENABLED

AVENYTH_EVIDENCE_LAYER_ENABLED

New phases remain disabled in production until acceptance gate passes.

===============================================================================
53. PR STRUCTURE
===============================================================================

Never one mega-PR.

Recommended:

PR-V2-00
Specs + ADRs + PR #15 resolution

PR-V2-01
Brand + auth + entitlements

PR-V2-02
Personal Workspace

PR-V2-03
Connections + consent

PR-V2-04
Relationship Workspace Core

PR-V2-05
Relationship/Shadow Analysis

PR-V2-06
Configurable Check-ins

PR-V2-07
Tasks

PR-V2-08
Roadmaps + Shared Reflection

PR-V2-09
Private + Shared Copilot

PR-V2-10
Dissolution + Account Deletion + Privacy Closure

PR-V2-11
Evidence Layer

PR-V2-12
Native Mobile

===============================================================================
54. EVERY PR MUST
===============================================================================

start from current main

remain focused

contain tests

contain migration if schema changed

regenerate OpenAPI if API changed

regenerate TS schemas if contract changed

update documentation

pass all existing required CI checks

pass new V2 phase-specific checks

not alter frozen Canon unless a separately approved Canon change exists

===============================================================================
55. NO-GO CONDITIONS
===============================================================================

Do not merge if:

Golden Canon fails

existing CI regression

authorization leak

consent leak

private thread visible cross-user

raw check-in visible to partner

LLM generates authoritative numeric result

OpenAPI drift

migration unsafe

Delete-All leaves inaccessible PII

disconnect still permits future inference

managed minor obtains account/session path

Compatibility % appears without Canon

===============================================================================
56. V2 CORE DEFINITION OF DONE
===============================================================================

AVENYTH V2 CORE is done only if:

Brand = AVENYTH

Canonical Engine unchanged

Golden green

Email verification green

Password reset green

Entitlements green

Personal Workspace green

Connections green

All relationship types configured

Consent green

Shared Relationship Workspace green

Shadow Dynamics grounded

Configurable Check-ins green

Raw Check-in privacy green

Tasks green

Roadmaps green

Shared Reflection green

Private Copilot green

Shared Copilot green

Truth classification green

Consent revoke immediate

Disconnect green

Delete-All green

Minor-profile policy green

Two-user IDOR matrix green

System E2E green

All required GitHub checks green

===============================================================================
57. EXECUTION METHOD
===============================================================================

Do not attempt the entire project in one session if this increases risk.

Execute gate-by-gate.

For every phase:

RECON

PLAN

IMPLEMENT

TEST

ROOT-CAUSE FAILURES

FIX

RETEST

CI

DOCUMENT

MERGE ONLY WHEN GREEN

Then proceed to next phase.

===============================================================================
58. PHASE REPORT FORMAT
===============================================================================

After every phase output:

PHASE=

BASE_SHA=

HEAD_SHA=

PR=

FILES_CHANGED=

MIGRATIONS=

OPENAPI=

TESTS=

CI=

GOLDEN_CANON=

AUTHORIZATION_MATRIX=

CONSENT_TESTS=

LLM_GROUNDING=

PRIVACY=

REGRESSION_RISK=

KNOWN_BLOCKERS=

PRODUCTION_FLAG_STATE=

NEXT_PHASE=

Do not report PASS from intended behavior.

Only real executed evidence counts.

===============================================================================
59. FIRST ACTION
===============================================================================

Start with READ-ONLY repository reconnaissance.

Resolve current main.

Inspect current open PRs.

Perform complete PR #15 assessment.

Verify baseline CI.

Then create Phase-0 specs and ADR plan.

DO NOT begin database or feature mutations before Phase-0 architecture/spec gate is
complete.

AVENYTH DOES NOT GUESS.
===============================================================================
```

---

## Anmerkung zu Entscheidung 8 (Check-in-Dimensionen)

Stabiles Default-Set:

```text
Nähe
Kommunikation
Verständnis
Freiraum
Konfliktbelastung
```

Erweiterbar pro Workspace um z. B.:

```text
Vertrauen
Gemeinsame Zeit
Unterstützung
Intimität
Leichtigkeit
```

Jedes Template und jede Dimension ist versioniert, sodass historische
Check-ins nachvollziehbar an ihre `checkin_template_version` gebunden bleiben
(„Auf Basis eurer letzten 11 Check-ins mit Template-Version 3 …“) statt Daten
unterschiedlicher Bedeutungen zu vermischen.

## Anmerkung zu Entscheidung 4 (Managed Minor Profiles)

Ein Eltern-Kind-Profil kann numerologisch ausgearbeitet werden, ohne einem
minderjährigen Familienmitglied einen vollwertigen AVENYTH-Account samt
Relationship Copilot und Social-Verbindung geben zu müssen.
