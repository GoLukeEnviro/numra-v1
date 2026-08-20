"""Thin async HTTP client for the internal PDF rendering service (`apps/pdf`).

Never accepts or forwards a caller-supplied URL — always posts a JSON payload built
from data this API already fetched/validated/owns from its own database (a completed
`Report`'s own `content_json`/`profile_snapshot`). This preserves the PDF service's own
no-SSRF-surface design (`apps/pdf/src/server.js`'s docstring): it only ever receives
already-fetched JSON, never a URL to fetch itself.
"""

from __future__ import annotations

from typing import Any

import httpx

__all__ = ["PdfServiceClient", "PdfServiceUnavailable"]


class PdfServiceUnavailable(Exception):
    """The PDF service could not be reached, or rejected the request. Always safe to
    surface to the caller as "export failed, try again" — never leaks the internal
    bearer token or raw exception internals beyond a short message."""


class PdfServiceClient:
    def __init__(
        self, *, base_url: str, internal_token: str, timeout_seconds: float = 60.0
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._internal_token = internal_token
        self._timeout_seconds = timeout_seconds

    async def render_report_pdf(
        self, *, report: dict[str, Any], profile: dict[str, Any], person: dict[str, Any]
    ) -> bytes:
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(
                    f"{self._base_url}/render/report",
                    json={"report": report, "profile": profile, "person": person},
                    headers={"Authorization": f"Bearer {self._internal_token}"},
                )
        except httpx.HTTPError as exc:
            raise PdfServiceUnavailable(f"could not reach the PDF service: {exc}") from exc

        if response.status_code != httpx.codes.OK:
            raise PdfServiceUnavailable(
                f"PDF service returned HTTP {response.status_code}: {response.text[:300]}"
            )
        return response.content
