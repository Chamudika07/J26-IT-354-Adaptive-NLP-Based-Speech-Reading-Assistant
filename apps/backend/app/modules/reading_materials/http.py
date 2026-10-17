"""Bound the actual streamed JSON body before FastAPI parses any material request."""

import re

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# 50,000 astral characters can require 600,000 bytes when JSON-escaped.
MAX_BODY_BYTES = 768 * 1024
PATH = re.compile(r"^/api/v1/learners/[^/]+/reading-materials(?:/|$)")


class MaterialBodyLimit:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or not PATH.match(scope.get("path", ""))
        ):
            await self.app(scope, receive, send)
            return
        headers = {k.lower(): v for k, v in scope.get("headers", [])}

        async def reject(status: int, code: str, message: str) -> None:
            await JSONResponse(
                status_code=status,
                content={"error": {"code": code, "message": message}},
                headers={"Cache-Control": "no-store"},
            )(scope, receive, send)

        if headers.get(b"content-encoding", b"identity").lower() != b"identity":
            await reject(415, "unsupported_media_type", "Unsupported media type")
            return
        content_type = headers.get(b"content-type", b"").split(b";", 1)[0].strip().lower()
        if content_type and content_type != b"application/json":
            await reject(415, "unsupported_media_type", "Unsupported media type")
            return
        length = headers.get(b"content-length")
        if length is not None:
            try:
                count = int(length)
                if count < 0:
                    raise ValueError("Invalid length")
            except ValueError:
                await reject(422, "validation_error", "Invalid request")
                return
            if count > MAX_BODY_BYTES:
                await reject(413, "payload_too_large", "Request too large")
                return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > MAX_BODY_BYTES:
                await reject(413, "payload_too_large", "Request too large")
                return
            if not message.get("more_body", False):
                break
        if body and content_type != b"application/json":
            await reject(415, "unsupported_media_type", "Unsupported media type")
            return
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay, send)
