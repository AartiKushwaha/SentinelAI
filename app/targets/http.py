import asyncio
import json
import os
from time import monotonic
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.config import HttpProfile, Settings
from app.core.security import pin_destination
from app.targets.base import Interaction, Observation, TargetError, TransientError


def extract(obj: Any, path: str) -> Any:
    for key in path.split("."):
        obj = obj[int(key)] if isinstance(obj, list) else obj[key]
    return obj


def render(node: Any, variables: dict) -> Any:
    if isinstance(node, dict):
        return {k: render(v, variables) for k, v in node.items()}
    if isinstance(node, list):
        return [render(v, variables) for v in node]
    return variables.get(node, node) if isinstance(node, str) else node


class HttpTarget:
    def __init__(
        self,
        profile: HttpProfile,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.profile = profile
        self.settings = settings
        self.transport = transport
        self.lock = asyncio.Lock()
        self.next_request = 0.0

    async def send(self, request: Interaction, *, model: str | None = None) -> Observation:
        async with self.lock:
            await asyncio.sleep(max(0, self.next_request - monotonic()))
            self.next_request = monotonic() + 1 / self.profile.requests_per_second
        url, host, tls_host = await pin_destination(self.profile.url)
        variables = {
            "$messages": [m.model_dump() for m in request.messages],
            "$prompt": request.messages[-1].content,
            "$model": model,
        }
        data = json.dumps(render(self.profile.payload, variables)).encode()
        if len(data) > self.settings.max_bytes:
            raise TargetError("request_too_large")
        headers = {
            **self.profile.headers,
            "Host": host,
            "Content-Type": "application/json",
            "Accept-Encoding": "identity",
            "Idempotency-Key": request.request_id,
        }
        if self.profile.auth_env:
            credential = os.environ.get(self.profile.auth_env)
            if not credential:
                raise TargetError("credential_unavailable")
            headers[self.profile.auth_header] = self.profile.auth_prefix + credential
        try:
            async with httpx.AsyncClient(
                trust_env=False,
                timeout=self.settings.timeout,
                transport=self.transport,
                follow_redirects=False,
            ) as client:
                async with client.stream(
                    self.profile.method,
                    url,
                    headers=headers,
                    content=data,
                    extensions={"sni_hostname": tls_host},
                ) as response:
                    if response.status_code in {429, 502, 503, 504}:
                        raise TransientError("upstream_busy")
                    if (
                        not 200 <= response.status_code < 300
                        or response.headers.get("content-encoding", "identity") != "identity"
                    ):
                        raise TargetError("upstream_rejected")
                    body = bytearray()
                    async for chunk in response.aiter_raw():
                        if len(body) + len(chunk) > self.settings.max_bytes:
                            raise TargetError("response_too_large")
                        body.extend(chunk)
            raw = json.loads(body)
            p = self.profile
            trace = extract(raw, p.trace_path) if p.trace_path else {}
            return Observation(
                text=extract(raw, p.text_path),
                decision=extract(raw, p.decision_path) if p.decision_path else None,
                tokens=extract(raw, p.usage_path) if p.usage_path else None,
                **{key: trace[key] for key in ("tools", "documents") if key in trace},
            )
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise TransientError("connection_failed") from exc
        except (
            httpx.HTTPError,
            ValueError,
            IndexError,
            KeyError,
            TypeError,
            AttributeError,
            RecursionError,
            ValidationError,
        ) as exc:
            raise TargetError("invalid_response_or_transport") from exc
