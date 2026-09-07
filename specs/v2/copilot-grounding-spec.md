# AVENYTH V2 — Copilot Grounding Spec

## Status

Frozen product decision (#10 in the decision log) — both Copilot modes ship.

## Modes

```
RELATIONSHIP_SHARED
  Both members + AVENYTH in one thread. Both see all messages and all responses.

RELATIONSHIP_PRIVATE
  One member asks AVENYTH with authorized shared relationship context. The other
  member sees neither the question, the answer, nor any summary derived from it.

PERSONAL_PRIVATE
  A user's own workspace Copilot, no relationship context beyond what belongs to
  their own profile(s).
```

A private thread must never contaminate shared thread memory — no summary,
embedding, or follow-up in a `RELATIONSHIP_SHARED` thread may be influenced by
content that originated in a `RELATIONSHIP_PRIVATE` thread of the same workspace.

## Thread model

```
ChatThread
  id, workspace_id (nullable), owner_user_id (nullable), scope, context_version,
  created_at, archived_at

ChatMessage
ThreadSummary
ThreadContextSnapshot
```

```
ThreadScope:
  PERSONAL_PRIVATE
  RELATIONSHIP_PRIVATE
  RELATIONSHIP_SHARED
```

`RELATIONSHIP_SHARED` threads: `owner_user_id = NULL`. `RELATIONSHIP_PRIVATE`
threads: `owner_user_id = requester`. `PERSONAL_PRIVATE`: `workspace_id = NULL`,
`owner_user_id = requester`.

## Context Builder

An explicit `ContextBuilder` component assembles every Copilot prompt — never ad
hoc string concatenation from the DB. It checks: `user`, `workspace`,
`thread scope`, `relationship type`, `consent grants`, `resource visibility`,
`historical summaries`.

Context **may** include: authorized canonical values, authorized Knowledge Base
content, authorized shared workspace data, the requester's own private data,
validated previous thread summaries (matching the thread's own scope).

Context **must never** include: the partner's private journal, the partner's
private tasks, the partner's private Copilot content, other relationships, other
profiles, admin information, secrets, or any scope that is currently revoked.

## Prompt injection defense

All journal/chat/reflection content is `UNTRUSTED_USER_DATA`. The prompt layer
separates:

```
SYSTEM_POLICY
CANONICAL_FACTS
KNOWLEDGE_CONTEXT
AUTHORIZED_WORKSPACE_CONTEXT
UNTRUSTED_USER_DATA
USER_QUERY
```

User content can never alter system instructions — this is enforced structurally
(distinct prompt sections, not string interpolation of user text into the system
turn), the same discipline the existing report pipeline already uses for
knowledge/user content separation.

## Truth classification

Every Copilot/insight statement carries a `basis_type`:

```
NUMEROLOGY_MODEL           "Das numerologische Modell legt nahe ..."
OBSERVED_WORKSPACE_DATA    "Eure bisherigen Check-ins zeigen ..."
MIXED                      both levels explicitly separated in the text
INSUFFICIENT_EVIDENCE      "Für eine belastbare Aussage liegen noch nicht
                             genügend Daten vor."
```

`INSUFFICIENT_EVIDENCE` is a valid, expected, and frequently correct output — never
treated as a failure state.

## Acceptance checks

- A `RELATIONSHIP_PRIVATE` thread's question/answer/summary is unreachable by the
  other member through any endpoint (two-user IDOR matrix, Section 49).
- A prompt-injection attempt embedded in journal/chat content cannot alter the
  system policy section or leak another user's private data (dedicated
  prompt-injection test suite, Section 48).
- Every rendered insight statement carries a `basis_type`; `INSUFFICIENT_EVIDENCE`
  renders correctly rather than being suppressed or guessed around.

See `docs/adr/011-v2-llm-grounding.md`.
