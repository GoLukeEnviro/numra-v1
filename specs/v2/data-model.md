# AVENYTH V2 — Data Model

## Status

Draft — Phase 0 spec freeze. Exact column-level schema is designed per-PR
(Section 53); this file fixes the target entity list and storage rules so
individual PRs don't drift.

## Existing (unchanged shape, may gain columns)

```
User            (+ person_account_mode is on Person, not User; see below)
Session
Person          (+ person_account_mode: SELF | MANAGED_MINOR | MANAGED_OTHER)
NameIdentity
Calculation
RelationshipComparison   (legacy V1, read-only per specs/v2/connection-spec.md)
Report
ReportSection
ReportJob
LLMGeneration
Export
AdminAuditEvent
```

## New V2 entities

```
EmailVerificationToken
PasswordResetToken

EntitlementSet / EntitlementAssignment

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
```

Each entity's full column list, indexes, and constraints are specified in the PR
that introduces it (`specs/v2/api-contract.md` §PR structure), reviewed against
this list so nothing is added or renamed silently.

## Storage rules

- Ownership, membership, permissions, consent, and state live in normalized
  relational columns/tables — never JSONB-only. A critical authorization decision
  must be queryable and indexable by SQL, not buried in a JSON blob.
- JSONB is for versioned structured generated content, snapshot payloads, and
  validated LLM structured output (e.g. `RelationshipAnalysis.result_json`,
  `ShadowDynamicsAnalysis.result_json`, `CheckinAnalysis.result_json`) — content
  that is read as a whole and whose shape is already validated against a schema
  before it's written.
- `calculation_version`, `knowledge_version`, `prompt_version`, `model_provider`,
  `model_name` are stored on every LLM-generated artifact (matches the existing
  `LLMGeneration` discipline).

## Row-Level Security

Evaluated as defense-in-depth, not assumed. Decision recorded in
`docs/adr/010-v2-consent-model.md` (adopted, or deferred with reason).
Application-level authorization is mandatory regardless of the RLS decision.
