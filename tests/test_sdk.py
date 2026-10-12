import base64
import json

import httpx
import pytest
from pydantic import ValidationError

from simplex_ai import (
    APIConnectionError,
    APIError,
    APIResponseError,
    APITimeoutError,
    AsyncSimplexClient,
    Choice,
    Image,
    MultiChoice,
    Noul,
    RateLimitError,
    Score,
    SimplexClient,
)

RESULT = {
    "model": "simplex-fastcd",
    "answers": {
        "route": {
            "type": "choice",
            "choice": "billing",
            "probabilities": {"billing": 0.8, "other": 0.2},
            "confidence": 0.6,
        },
        "tags": {
            "type": "multi_choice",
            "choices": ["refund"],
            "steps": [{"choice": "refund", "probabilities": {"refund": 0.9}}],
        },
        "urgent": {"type": "noul", "noul": 0.75},
        "severity": {
            "type": "score",
            "score": 1.4,
            "probabilities": {"0": 0.1, "1": 0.4, "2": 0.5},
        },
    },
    "usage": {
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "status": "pending",
    },
    "latency_ms": 12.5,
}
QUESTIONS = {"route": Choice(criteria={"billing": None, "other": None})}


def test_sync_wire_and_typed_response():
    def handler(request):
        assert str(request.url) == "https://api.simplexai.net/v1/system-one"
        assert request.headers["authorization"] == "Bearer test-token"
        body = json.loads(request.content)
        assert body["model"] == "spx-cd-pro"
        assert body["state"] is None
        assert "label_style" not in body
        assert body.get("reasoning", False) is False
        assert body["questions"]["route"]["criteria"] == {"billing": None, "other": None}
        return httpx.Response(200, json=RESULT)

    with SimplexClient(api_key="test-token", transport=httpx.MockTransport(handler)) as client:
        result = client.system_one(state=None, questions=QUESTIONS, model="spx-cd-pro")
    assert result.answers["route"].choice == "billing"
    assert result.answers["route"].confidence == 0.6
    assert result.answers["tags"].choices == ["refund"]
    assert result.answers["urgent"].noul == 0.75
    assert result.answers["severity"].score == 1.4
    assert result.usage.input_tokens is None
    assert result.usage.status == "pending"


@pytest.mark.asyncio
async def test_async_parity_and_models():
    paths = []

    async def handler(request):
        paths.append(request.url.path)
        return httpx.Response(
            200, json={"data": [{"id": "spx-cd"}]} if request.method == "GET" else RESULT
        )

    async with AsyncSimplexClient(api_key="test", transport=httpx.MockTransport(handler)) as client:
        assert (await client.models())["data"][0]["id"] == "spx-cd"
        assert (await client.system_one(state="test", questions=QUESTIONS)).answers[
            "urgent"
        ].noul == 0.75
    assert paths == ["/v1/models", "/v1/system-one"]


@pytest.mark.parametrize("status", [301, 401, 413, 422, 429, 502, 503])
def test_http_errors_never_retry_or_follow_redirects(status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status,
            json={"detail": "failure"},
            headers={
                "Retry-After": "3",
                "Location": "https://elsewhere.example/",
                "X-Request-ID": "r1",
            },
        )

    with SimplexClient(api_key="secret", transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RateLimitError if status == 429 else APIError) as exc:
            client.system_one(state="test", questions=QUESTIONS)
    assert len(calls) == 1
    assert exc.value.status_code == status
    assert exc.value.request_id == "r1"
    assert "secret" not in str(exc.value)
    if status == 429:
        assert exc.value.retry_after == "3"


@pytest.mark.parametrize(
    "error,expected",
    [(httpx.ReadTimeout, APITimeoutError), (httpx.ConnectError, APIConnectionError)],
)
def test_transport_errors(error, expected):
    def handler(request):
        raise error("failure", request=request)

    with SimplexClient(api_key="test", transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(expected):
            client.system_one(state="x", questions=QUESTIONS)


@pytest.mark.parametrize(
    "payload",
    [{}, {"answers": {"q": {"type": "choice"}}}, {"answers": {"q": {"type": "new_type"}}}],
)
def test_malformed_response(payload):
    with SimplexClient(
        api_key="test", transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload))
    ) as client:
        with pytest.raises(APIResponseError):
            client.system_one(state="x", questions=QUESTIONS)


def test_question_limits():
    assert MultiChoice(criteria={"a": None, "b": None}).max_choices == 2
    assert MultiChoice(criteria={"a": None}, max_choices=0).max_choices == 0
    for kwargs in [{"min_choices": 2}, {"max_choices": 11}, {"max_choices": True}]:
        with pytest.raises(ValidationError):
            MultiChoice(criteria={"a": None}, **kwargs)
    with pytest.raises(ValidationError):
        Choice(criteria={})
    with pytest.raises(ValidationError):
        Score(criteria=[])
    assert Noul(criteria={"true": "yes", "false": "no"}).type == "noul"


def test_images(tmp_path):
    data = b"\x89PNG\r\n\x1a\n" + b"x" * 20
    path = tmp_path / "image.png"
    path.write_bytes(data)
    image = Image.from_file(path)
    assert base64.b64decode(image.url.split(",")[1]) == data
    assert Image.from_bytes(data, media_type="image/png").url == image.url
    for url in ["https://example.com/x.png", "data:image/png;base64,!", "data:image/png;base64,"]:
        with pytest.raises(ValueError):
            Image(url=url)
    with pytest.raises(ValueError):
        Image.from_bytes(b"x" * 2_000_001, media_type="image/png")
    with pytest.raises(ValueError):
        Image.from_bytes(b"x", media_type="image/svg+xml")


def test_invalid_requests_do_not_hit_network():
    def handler(request):
        pytest.fail("Invalid request reached the network")

    with SimplexClient(api_key="test", transport=httpx.MockTransport(handler)) as client:
        for kwargs in [
            {"questions": {}},
            {"questions": {str(i): QUESTIONS["route"] for i in range(65)}},
            {"images": [Image.from_bytes(b"x", media_type="image/png")] * 5},
            {"state": "x" * 15_000_000},
            {"state": float("nan")},
            {"model": "typesafe-ai/jev", "questions": {"q": MultiChoice(criteria={"a": None})}},
            {"model": "typesafe-ai/jev", "questions": {"q": Score(criteria=["a"])}},
        ]:
            options = {"state": "x", "questions": QUESTIONS, **kwargs}
            with pytest.raises(ValueError):
                client.system_one(**options)


def test_environment(monkeypatch):
    monkeypatch.setenv("SIMPLEX_API_TOKEN", "env-key")
    monkeypatch.setenv("SIMPLEX_API_BASE", "https://example.com/")

    def handler(request):
        assert request.url.host == "example.com"
        assert request.headers["authorization"] == "Bearer env-key"
        return httpx.Response(200, json=RESULT)

    with SimplexClient(transport=httpx.MockTransport(handler)) as client:
        client.system_one(state="x", questions=QUESTIONS)
    monkeypatch.delenv("SIMPLEX_API_TOKEN")
    with pytest.raises(ValueError):
        SimplexClient()


def test_advanced_effort_warning():
    with SimplexClient(
        api_key="test", transport=httpx.MockTransport(lambda r: httpx.Response(200, json=RESULT))
    ) as client:
        with pytest.warns(UserWarning, match="not recommended"):
            client.system_one(state="x", questions=QUESTIONS, effort=2)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 429, 503])
async def test_async_http_errors(status):
    calls = []

    async def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"detail": "failure"}, headers={"retry-after": "2"})

    async with AsyncSimplexClient(api_key="test", transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(APIError) as exc:
            await client.system_one(state="x", questions=QUESTIONS)
    assert len(calls) == 1
    assert exc.value.status_code == status


@pytest.mark.asyncio
async def test_async_timeout_and_close():
    async def handler(request):
        raise httpx.ReadTimeout("failure", request=request)

    async with AsyncSimplexClient(api_key="test", transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(APITimeoutError):
            await client.system_one(state="x", questions=QUESTIONS)
    assert client._http.is_closed


def test_raw_dicts_and_missing_usage():
    def handler(request):
        body = json.loads(request.content)
        assert body["questions"]["q"] == {
            "type": "noul",
            "instructions": "Is this a test?",
            "criteria": None,
        }
        return httpx.Response(
            200,
            json={"answers": {"q": {"type": "noul", "noul": 0.5}}, "future_metadata": "preserved"},
        )

    with SimplexClient(api_key="test", transport=httpx.MockTransport(handler)) as client:
        result = client.system_one(
            state="test", questions={"q": {"type": "noul", "instructions": "Is this a test?"}}
        )
        assert result.usage is None
        assert result.model_dump()["future_metadata"] == "preserved"
    assert client._http.is_closed


@pytest.mark.parametrize(
    "url",
    [
        "https://user:password@example.com",
        "http://example.com",
        "https://example.com/v1",
        "https://example.com/?key=x",
    ],
)
def test_invalid_base_url(url):
    with pytest.raises(ValueError):
        SimplexClient(api_key="test", base_url=url)


def test_exact_image_limit_and_supported_types(tmp_path):
    for mime in ["image/png", "image/jpeg", "image/webp", "image/gif"]:
        assert Image.from_bytes(b"x" * 2_000_000, media_type=mime).url.startswith("data:" + mime)
    path = tmp_path / "large.png"
    path.write_bytes(b"x" * 2_000_001)
    with pytest.raises(ValueError):
        Image.from_file(path)


def test_utf8_body_size_not_character_count():
    with SimplexClient(
        api_key="test", transport=httpx.MockTransport(lambda r: pytest.fail("Must not send"))
    ) as client:
        with pytest.raises(ValueError, match="15,000,000"):
            client.system_one(state="中" * 5_000_000, questions=QUESTIONS)


def test_invalid_json_response():
    with SimplexClient(
        api_key="test",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="<html>error</html>")),
    ) as client:
        with pytest.raises(APIResponseError):
            client.system_one(state="x", questions=QUESTIONS)

@pytest.mark.parametrize("effort", [0, 6, True, 1.5, "2", None])
def test_invalid_effort_never_sends(effort):
    with SimplexClient(api_key="test", transport=httpx.MockTransport(lambda r: pytest.fail("sent invalid request"))) as client:
        with pytest.raises(ValueError):
            client.system_one(state="x", questions=QUESTIONS, effort=effort)

@pytest.mark.parametrize("field", ["reasoning", "reasoning_max_tokens"])
def test_removed_reasoning_rejected(field):
    with SimplexClient(api_key="test") as client:
        with pytest.raises(TypeError):
            client.system_one(state="x", questions=QUESTIONS, **{field: True})

@pytest.mark.parametrize("effort", range(2, 6))
@pytest.mark.asyncio
async def test_async_effort_wire(effort):
    def handler(request):
        body = json.loads(request.content)
        assert body["effort"] == effort
        assert "reasoning" not in body and "reasoning_max_tokens" not in body
        return httpx.Response(200, json=RESULT)
    async with AsyncSimplexClient(api_key="test", transport=httpx.MockTransport(handler)) as client:
        with pytest.warns(UserWarning, match="not recommended"):
            await client.system_one(state="x", questions=QUESTIONS, effort=effort)
