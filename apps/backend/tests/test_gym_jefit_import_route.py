import asyncio
import io

import jwt
from fastapi import UploadFile

from app.api import gym

_SAMPLE_EXPORT = """
### EXERCISE LOGS ####################################

USERID,TIMESTAMP,belongSys,logs,_id,record,mydate,eid,ename,day_item_id,belongsession,logTime,interval_logs,auto_generated
1,"2026-01-01 00:00:00",1,"60x10,65x8",1,86.67,2026-01-01,21,"Barbell Bench Press Route Test",1,900001,1,,
"""


def _token() -> str:
    return "Bearer " + jwt.encode(
        {"sub": gym.AUTH_USERNAME, "iss": "sirisos-api"},
        gym.JWT_SECRET,
        algorithm="HS256",
    )


def _upload(content: bytes, filename: str = "export.csv") -> UploadFile:
    return UploadFile(file=io.BytesIO(content), filename=filename)


def test_import_jefit_requires_authentication() -> None:
    try:
        asyncio.run(gym.import_jefit(file=_upload(b""), authorization=None))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 401
    else:
        raise AssertionError("Expected authentication failure")


def test_import_jefit_rejects_non_utf8_content() -> None:
    try:
        asyncio.run(gym.import_jefit(file=_upload(b"\xff\xfe\x00\x01"), authorization=_token()))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    else:
        raise AssertionError("Expected a 400 for undecodable content")


def test_import_jefit_rejects_a_file_over_the_size_limit(monkeypatch) -> None:
    monkeypatch.setattr(gym, "MAX_JEFIT_EXPORT_UPLOAD_BYTES", 10)
    try:
        asyncio.run(gym.import_jefit(file=_upload(_SAMPLE_EXPORT.encode("utf-8")), authorization=_token()))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 413
    else:
        raise AssertionError("Expected a 413 for an oversized file")


def test_import_jefit_imports_a_real_shaped_export() -> None:
    result = asyncio.run(gym.import_jefit(file=_upload(_SAMPLE_EXPORT.encode("utf-8")), authorization=_token()))

    assert result.sessions_imported == 1
    assert result.sets_imported == 2
    assert result.errors == []

    # Re-uploading the same export is a no-op, not a duplicate.
    second = asyncio.run(gym.import_jefit(file=_upload(_SAMPLE_EXPORT.encode("utf-8")), authorization=_token()))
    assert second.sessions_imported == 0
    assert second.sessions_skipped == 1
