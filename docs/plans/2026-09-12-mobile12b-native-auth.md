# MOBILE-12B Native Authentication Implementation Plan

This increment adds a separate opaque-token boundary for native clients while keeping
the established browser cookie/CSRF contract byte-for-byte compatible. The token uses
the existing session lifecycle and database model; no parallel identity system exists.

