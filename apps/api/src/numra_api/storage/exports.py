"""Where generated export files (PDF bytes) physically live.

`ExportStorage` is a `Protocol` — callers (`services/export_service.py`) depend only on
its shape, never on `LocalExportStorage` directly, so a future S3/GCS-backed
implementation can be swapped in (e.g. behind a `Settings.export_storage_backend`
switch) without touching any calling code.

`LocalExportStorage` is the only implementation in V1: local disk, single-instance
deployment. Every file is named strictly by the export's own server-generated UUID —
never by anything a client supplies — so there is no path-traversal surface; `_path_for`
additionally asserts the resolved path never escapes `base_dir` as a defense-in-depth
check against a future caller accidentally passing back something it shouldn't.
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Protocol

__all__ = ["ExportStorage", "LocalExportStorage"]


class ExportStorage(Protocol):
    async def save(self, *, export_id: uuid.UUID, content: bytes, extension: str) -> str:
        """Persist ``content``, returning an opaque storage reference that `read`/
        `delete` accept. The reference is never a client-controllable path."""
        ...

    async def read(self, file_ref: str) -> bytes: ...

    async def delete(self, file_ref: str) -> None:
        """Must not raise if the file is already absent — deletion is idempotent, so
        Delete-All can call it freely without first checking existence."""
        ...


class LocalExportStorage:
    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, file_ref: str) -> Path:
        base = self._base_dir.resolve()
        resolved = (base / file_ref).resolve()
        if resolved != base and base not in resolved.parents:
            raise ValueError(f"file_ref escapes storage base_dir: {file_ref!r}")
        return resolved

    async def save(self, *, export_id: uuid.UUID, content: bytes, extension: str) -> str:
        file_ref = f"{export_id}.{extension}"
        path = self._path_for(file_ref)
        await asyncio.to_thread(path.write_bytes, content)
        return file_ref

    async def read(self, file_ref: str) -> bytes:
        path = self._path_for(file_ref)
        return await asyncio.to_thread(path.read_bytes)

    async def delete(self, file_ref: str) -> None:
        path = self._path_for(file_ref)

        def _unlink() -> None:
            path.unlink(missing_ok=True)

        await asyncio.to_thread(_unlink)
