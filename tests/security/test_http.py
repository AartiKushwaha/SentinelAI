import asyncio
import json
import socket

import httpx
import pytest

from app.core.config import HttpProfile, Settings
from app.core.security import pin_destination
from app.targets.base import Interaction, Message, TargetError
from app.targets.http import HttpTarget


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.169.254",
        "100.64.0.1",
        "224.0.0.1",
        "::1",
        "fe80::1",
        "::ffff:127.0.0.1",
        "64:ff9b::a9fe:a9fe",
    ],
)
async def test_block_non_public_addresses(address):
    host = f"[{address}]" if ":" in address else address
    with pytest.raises(TargetError):
        await pin_destination(f"https://{host}/fixture")


@pytest.mark.parametrize(
    "url",
    [
        "http://8.8.8.8",
        "https://user@8.8.8.8/",
        "https://8.8.8.8/?token=x",
        "https://8.8.8.8/#fragment",
    ],
)
async def test_block_unsafe_url(url):
    with pytest.raises(TargetError):
        await pin_destination(url)


async def test_mixed_dns_answers(monkeypatch):
    async def resolve(*args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))
            for ip in ["8.8.8.8", "127.0.0.1"]
        ]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
    with pytest.raises(TargetError, match="non_public"):
        await pin_destination("https://fixture.example/generate")


class Chunks(httpx.AsyncByteStream):
    def __init__(self, body):
        self.body = body

    async def __aiter__(self):
        yield self.body


@pytest.mark.parametrize(
    "mode", ["valid", "oversize", "redirect", "compressed", "malformed", "missing-field"]
)
async def test_pinned_http_transport(mode, monkeypatch):
    async def resolve(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
    monkeypatch.setenv("SENTINEL_CRED_TEST", "test-fixture-credential")
    calls = []

    def handler(req):
        calls.append(req)
        assert req.url.host == "8.8.8.8" and req.headers["Host"] == "fixture.example"
        assert req.extensions["sni_hostname"] == "fixture.example"
        assert req.headers["Authorization"] == "Bearer test-fixture-credential"
        assert json.loads(req.content) == {"input": {"text": "hello"}}
        body = {"answer": {"text": "ok"}, "trace": {"documents": [], "tools": []}}
        raw = {"oversize": b"x" * 1025, "malformed": b"oops", "missing-field": b"{}"}.get(
            mode, json.dumps(body).encode()
        )
        return httpx.Response(
            302 if mode == "redirect" else 200,
            headers={
                "Location": "http://127.0.0.1",
                "content-encoding": "gzip" if mode == "compressed" else "identity",
            },
            stream=Chunks(raw),
        )

    profile = HttpProfile(
        url="https://fixture.example/generate",
        auth_env="SENTINEL_CRED_TEST",
        payload={"input": {"text": "$prompt"}},
        text_path="answer.text",
        trace_path="trace",
    )
    target = HttpTarget(profile, Settings(max_bytes=1024), transport=httpx.MockTransport(handler))
    request = Interaction(messages=[Message(role="user", content="hello")], request_id="one")
    if mode == "valid":
        assert (await target.send(request)).text == "ok"
    else:
        with pytest.raises(TargetError):
            await target.send(request)
    assert len(calls) == 1
