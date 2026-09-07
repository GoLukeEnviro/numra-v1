# AVENYTH V2 — Managed Minor Profile Policy

## Status

Frozen product decision (#4 in the decision log) — deviates from the recommended
default of allowing scoped minor accounts.

## Decision

AVENYTH accounts are **18+ only**. Minors never get their own `User` row, login, or
session. A minor may exist only as a **Managed Person Profile** owned by an adult
account.

## `person_account_mode`

Add an enum column to `Person` (or an equivalent owning table):

```
person_account_mode:
  SELF            -- profile belongs to and represents the account holder
  MANAGED_MINOR   -- profile represents a minor, managed by the owning adult account
  MANAGED_OTHER   -- profile represents another adult, managed for convenience
                      (e.g. a parent tracking a grown relative) -- not itself a login
```

Only `SELF` profiles may ever become a `UserConnection` participant or a
`RelationshipWorkspace` member (`specs/v2/connection-spec.md`).

## Age determination

Minor status is **derived, not stored as a fact**:

```
is_minor(profile, as_of_date) = age_from(profile.birth_date, as_of_date) < 18
```

Computed on read wherever it gates behavior (invite eligibility, workspace-type
eligibility, check-in dimension eligibility). No persisted boolean
`is_minor = true/false` is treated as durable truth — `birth_date` is canonical, the
derivation is a pure function of it and the current date.

## Restrictions on `MANAGED_MINOR` profiles

A `MANAGED_MINOR` profile must never:

- have its own login or session,
- have a private Copilot identity of its own,
- appear in public discovery,
- be the target or source of a `ConnectionInvitation`,
- be a `WorkspaceMember` of any `RelationshipWorkspace`,
- be assigned `PARTNER` or `DATING` as a relationship type in any analysis,
- have a public profile,
- send or receive direct messages,
- have a `sexual_connection`-class check-in dimension available
  (`specs/v2/checkin-spec.md`).

## Allowed contexts

`PARENT_CHILD`, `FAMILY`, `SIBLINGS` relationship-type analyses are permitted
**between an adult account's own `SELF` profile and a `MANAGED_MINOR`/
`MANAGED_OTHER` profile they own** — this is always a private, single-owner
analysis, never a shared workspace with two independent accounts.

Example: adult user Luke + his Managed Minor Child profile → a private
Parent-Child numerological analysis. This is not a `RelationshipWorkspace`; there is
only one account involved.

## Multi-guardian access

If two adult accounts should both see the same Managed Minor Profile (e.g. two
co-parents), this requires an explicit, later `ManagedProfileSharing` mechanism.
**Never implicitly shared** — until that mechanism exists, a Managed Minor Profile
is visible only to the single account that created it.

## Age-of-majority transition

A Managed Minor Profile reaching 18 is **not** automatically converted into a real
`User` account. An explicit claim/transfer flow (out of scope for V2 Core) would be
required for that later; until it exists, the profile simply continues to exist as
a `MANAGED_OTHER`-eligible managed profile with no login path.

## Deletion

Deleting a Managed Minor Profile removes its private data (calculations, private
analyses) belonging solely to that profile. Since it can never be a shared-workspace
participant, there is no cross-account artifact to reconcile — see
`specs/v2/dissolution-policy.md` §Delete Account for the account-level case.

## Acceptance checks (Section 51)

- Adult creates Managed Minor Profile → profile calculates normally.
- No credentials/session exist for the minor profile.
- `ConnectionInvitation` targeting a `MANAGED_MINOR` profile is rejected at the API
  layer (not just hidden in the UI).
- `PARTNER`/`DATING` relationship type involving a managed minor profile is rejected
  at the API layer.
- `PARENT_CHILD` private analysis between an adult's `SELF` profile and their
  `MANAGED_MINOR` profile works end-to-end.
- Minor profile's private data never appears in an unrelated workspace's context
  (verified via the Copilot Context Builder tests, `specs/v2/copilot-grounding-spec.md`).
- Deleting a Managed Minor Profile removes its private data safely, with no orphaned
  rows.

See `docs/adr/012-v2-managed-minor-profiles.md`.
