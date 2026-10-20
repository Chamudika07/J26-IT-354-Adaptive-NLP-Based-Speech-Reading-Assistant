from uuid import uuid4

import pytest

from app.modules.reading_materials.http import MAX_BODY_BYTES


def base():
    return f"/api/v1/learners/{uuid4()}/reading-materials"


@pytest.mark.parametrize(
    "headers",
    [
        {"content-type": "text/plain"},
        {"content-type": "multipart/form-data"},
        {"content-type": "application/pdf"},
        {"content-type": "application/json", "content-encoding": "gzip"},
    ],
)
def test_only_json(client, headers):
    res = client.post(base(), content=b"private source", headers=headers)
    assert res.status_code == 415 and "private source" not in res.text
    assert res.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("length", [None, "1", str(MAX_BODY_BYTES + 1)])
def test_real_body_limit_not_just_content_length(client, length):
    headers = {"content-type": "application/json"}
    if length:
        headers["content-length"] = length
    res = client.post(base(), content=b"x" * (MAX_BODY_BYTES + 1), headers=headers)
    assert res.status_code == 413
    assert res.json() == {"error": {"code": "payload_too_large", "message": "Request too large"}}


@pytest.mark.parametrize("length", ["-1", "invalid"])
def test_malformed_length(client, length):
    assert (
        client.post(
            base(),
            content=b"{}",
            headers={"content-type": "application/json", "content-length": length},
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "method,suffix,body",
    [
        ("post", "", {"title": "Synthetic", "language_tag": "en", "text": "A cat."}),
        ("get", "", None),
        ("get", "/00000000-0000-0000-0000-000000000001", None),
        ("post", "/00000000-0000-0000-0000-000000000001/archive", {"row_version": 1}),
    ],
)
def test_authentication_required(client, method, suffix, body):
    kwargs = {} if body is None else {"json": body}
    assert getattr(client, method)(base() + suffix, **kwargs).status_code == 401
