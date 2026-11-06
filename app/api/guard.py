from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestGuard:
    def __init__(self, app: ASGIApp, limit: int):
        self.app = app
        self.limit = limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        host = headers.get("host", "")
        origin = headers.get("origin")

        async def reject(code: str, status: int) -> None:
            await JSONResponse({"error": {"code": code}}, status)(scope, receive, send)

        if host.split(":")[0].lower() not in {"127.0.0.1", "localhost"}:
            await reject("untrusted_host", 400)
            return
        if origin and origin != f"{scope['scheme']}://{host}":
            await reject("cross_origin_request", 403)
            return
        if scope["method"] in {"POST", "PATCH", "PUT"}:
            size = 0
            parts = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                content = message.get("body", b"")
                size += len(content)
                if size > self.limit:
                    await reject("request_too_large", 413)
                    return
                parts.extend(content)
                if not message.get("more_body"):
                    break
            delivered = False

            async def bounded_receive() -> Message:
                nonlocal delivered
                if delivered:
                    return await receive()
                delivered = True
                return {"type": "http.request", "body": bytes(parts), "more_body": False}

            await self.app(scope, bounded_receive, send)
        else:
            await self.app(scope, receive, send)
