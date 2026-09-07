# AVENYTH V2 — Connection Spec

## Status

Draft — Phase 0 spec freeze. Frozen decisions: #6 (invite methods).

## Scope

V2 connects real, adult **User accounts** to each other. It does not build a public
people directory or username search for V2 Core.

## Invitation methods

```
INVITE_LINK
INVITE_CODE
EMAIL
```

All three resolve to the same `ConnectionInvitation` entity; the method only
determines how the recipient discovers/redeems it.

## Entities

```
ConnectionInvitation
  id, inviter_user_id, method, code/link_token (hashed at rest, like password-reset
  tokens), invitee_email (nullable, EMAIL method only), state, expires_at,
  created_at, redeemed_by_user_id (nullable), redeemed_at

UserConnection
  id, user_a_id, user_b_id, created_at, status (ACTIVE | DISSOLVED)

RelationshipWorkspace
  see specs/v2/relationship-workspace-spec.md

WorkspaceMember
ConsentGrant
ConsentEvent
  see specs/v2/consent-spec.md
```

## Invitation states

```
PENDING
ACCEPTED
DECLINED
EXPIRED
REVOKED
```

Only `PENDING` invitations may transition; every other state is terminal. Tokens
follow the existing password-reset token model (ADR-consistent with
`specs/v2/api-contract.md` §Auth): random cryptographically secure token, only the
hash persisted, single use, expiry, replay protection, rate limiting.

## Workspace creation gate

A `RelationshipWorkspace` is created **only when all of the following hold**:

1. User A sent an invite.
2. User B accepted it.
3. Both are adult (18+) `User` accounts — never a `MANAGED_MINOR`/`MANAGED_OTHER`
   profile (`specs/v2/minor-profile-policy.md`).
4. Consent was configured successfully for the connection
   (`specs/v2/consent-spec.md`).

Any invitation targeting a Managed Profile, or accepted by/for a non-adult account,
is rejected server-side — never merely hidden in the UI.

## Legacy V1 relationships

Existing `RelationshipComparison` rows belong to a single user; V1 had no mutual
consent step. They are **not** auto-converted into V2 shared workspaces. They
remain read-only-visible to their original owner. A later, explicit "Invite this
person to AVENYTH" flow may let a user turn a legacy comparison into a real
invitation — but a `RelationshipWorkspace` is only ever created through the gate
above, after a genuine new connection.

## Acceptance checks

- Two-user IDOR matrix (Section 49): neither party can read the other's private
  invitation tokens, or force-create a workspace without the other's acceptance.
- Expired/revoked/declined invitations cannot be redeemed.
- An invitation targeting an email that later turns out to belong to a
  `MANAGED_MINOR`-only account context is rejected.
