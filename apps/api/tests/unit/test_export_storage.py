from __future__ import annotations

import uuid

import pytest

from numra_api.storage.exports import LocalExportStorage

pytestmark = pytest.mark.unit


async def test_save_read_roundtrip(tmp_path) -> None:
    storage = LocalExportStorage(tmp_path)
    export_id = uuid.uuid4()
    file_ref = await storage.save(export_id=export_id, content=b"%PDF-fake-bytes", extension="pdf")
    assert file_ref == f"{export_id}.pdf"
    assert await storage.read(file_ref) == b"%PDF-fake-bytes"


async def test_delete_is_idempotent(tmp_path) -> None:
    storage = LocalExportStorage(tmp_path)
    export_id = uuid.uuid4()
    file_ref = await storage.save(export_id=export_id, content=b"x", extension="pdf")
    await storage.delete(file_ref)
    assert not (tmp_path / file_ref).exists()
    await storage.delete(file_ref)  # must not raise on an already-absent file


async def test_creates_base_dir_if_missing(tmp_path) -> None:
    base_dir = tmp_path / "does" / "not" / "exist" / "yet"
    assert not base_dir.exists()
    LocalExportStorage(base_dir)
    assert base_dir.is_dir()


@pytest.mark.parametrize(
    "malicious_ref",
    [
        "../../etc/passwd",
        "../secret.txt",
        "/etc/passwd",
        "a/../../b.pdf",
    ],
)
async def test_rejects_file_ref_that_escapes_base_dir(tmp_path, malicious_ref) -> None:
    storage = LocalExportStorage(tmp_path)
    with pytest.raises(ValueError, match="escapes storage base_dir"):
        await storage.read(malicious_ref)
    with pytest.raises(ValueError, match="escapes storage base_dir"):
        await storage.delete(malicious_ref)


async def test_read_missing_file_raises_file_not_found(tmp_path) -> None:
    storage = LocalExportStorage(tmp_path)
    with pytest.raises(FileNotFoundError):
        await storage.read(f"{uuid.uuid4()}.pdf")
