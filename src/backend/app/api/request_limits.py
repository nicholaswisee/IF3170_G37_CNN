import json

from app.limits import MAX_REQUEST_BYTES


class RunBodyLimitMiddleware:
    def __init__(self, app, max_bytes: int = MAX_REQUEST_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or scope["path"]
            not in (
                "/api/experiments/run",
                "/api/experiments/batch",
                "/api/problems/validate",
            )
        ):
            await self.app(scope, receive, send)
            return
        chunks = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.max_bytes:
                body = json.dumps(
                    {"detail": f"Request body exceeds {self.max_bytes} bytes."}
                ).encode()
                await send(
                    {
                        "type": "http.response.start",
                        "status": 422,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode()),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": body})
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        consumed = False

        async def replay_receive():
            nonlocal consumed
            if consumed:
                return await receive()
            consumed = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay_receive, send)
