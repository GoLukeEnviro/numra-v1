# MOBILE-12A Foundation and Readiness Plan

The first native increment deliberately proves the delivery boundary before adding
credentials. It creates an Expo app, reads the existing public configuration endpoint,
and makes configuration and availability failures visible and retryable.

Native sign-in is the next design gate, not part of this PR: the server currently uses
HttpOnly session cookies plus double-submit CSRF. A mobile credential model must be
specified and threat-modelled rather than inferred from browser behavior.

