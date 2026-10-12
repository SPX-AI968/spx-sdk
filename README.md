# Simplex AI Python SDK

Python client for Simplex CD structured decisions. Supports synchronous and asynchronous calls, typed questions and answers, local image encoding, and request validation.

[中文文档](README.zh-CN.md) · [API documentation](https://simplexai.net/en/platform/docs) · [Access tokens](https://simplexai.net/en/platform/keys)

## Install

Requires Python 3.10+. Until the first PyPI release, install from this repository:

```bash
pip install git+https://github.com/SPX-AI968/spx-sdk.git
```

After publication: `pip install simplex-ai-sdk`. Import as `simplex_ai`.
Do not install `spx-sdk`: that PyPI name belongs to an unrelated project.

## First decision

Set `SIMPLEX_API_TOKEN` in your server environment, then:

```python
from simplex_ai import Choice, ChoiceAnswer, SimplexClient

with SimplexClient() as client:
    result = client.system_one(
        state={"message": "I was charged twice. Please refund the duplicate."},
        questions={
            "route": Choice(
                instructions="Choose the department.",
                criteria={"billing": "Payments and refunds", "support": "Technical help"},
            )
        },
    )
    answer = result.answers["route"]
    if isinstance(answer, ChoiceAnswer):
        print(answer.choice, answer.probabilities)
    print(result.usage)
```

Use `SimplexClient(api_key="…")` to pass a token explicitly. Never embed credentials in frontend code or commit them. The default origin is `https://api.simplexai.net`; override with `SIMPLEX_API_BASE` or `base_url` (origin only, without `/v1`). Remote origins require HTTPS; HTTP loopback is supported for local testing.

## Four question types

```python
from simplex_ai import Choice, MultiChoice, Noul, Score, SimplexClient

with SimplexClient() as client:
    result = client.system_one(
        model="spx-cd-auto",
        state="The customer reports a duplicate charge and requests a refund.",
        questions={
            "department": Choice(criteria={"billing": None, "support": None}),
            "topics": MultiChoice(
                criteria={"duplicate_charge": None, "refund": None, "technical": None},
                max_choices=2,
            ),
            "refund_requested": Noul(instructions="Does the customer request a refund?"),
            "urgency": Score(criteria=["low", "medium", "high"]),
        },
    )
    print(result.model_dump())
```

| Type | Answer field | Meaning |
| --- | --- | --- |
| `Choice` | `choice` | One candidate key |
| `MultiChoice` | `choices` | A list of candidate keys; zero selections allowed |
| `Noul` | `noul` | Yes probability, from 0 to 1 |
| `Score` | `score` | Expected zero-based index of the ordered criteria |

Questions may also be dictionaries with a `type` field. `state` accepts any JSON value for Simplex CD. Null criterion descriptions are preserved. Response extras are retained by Pydantic; use `model_dump()` to access the complete response. Answers are a discriminated union: narrow with `isinstance(answer, ChoiceAnswer)` or the other exported answer classes for static type checking.

Probabilities and confidence are preserved as returned, not recalculated. Unknown or missing usage stays `None`, not zero. Multi-choice step probabilities are conditional on earlier selections.

## Models

Use `spx-cd` (default), `spx-cd-auto`, `spx-cd-flash`, or `spx-cd-pro`. Retrieve the current catalog and server limits with `client.models()`.

`typesafe-ai/jev` uses the same token and supports text Choice, Noul and Score. It does not accept images or multi-choice; Score requires at least two criteria and state must be a string, object or array.

## Images

```python
from simplex_ai import Choice, Image, SimplexClient

with SimplexClient() as client:
    result = client.system_one(
        state="Identify the main object.",
        images=[Image.from_file("scene.png")],
        questions={"object": Choice(criteria={"chair": None, "table": None, "other": None})},
    )
```

For in-memory bytes, use `Image.from_bytes(data, media_type="image/png")`. You can also pass `Image(url="data:image/png;base64,…")`. Optional image detail: `auto`, `low`, `high`. File MIME types are inferred from extensions; the SDK checks encoding and size, not image decodability or pixel dimensions. Files are not resized. Remote image URLs are not fetched.

- PNG, JPEG, WebP, GIF; at most 4 images per request.
- At most 2,000,000 bytes per decoded image.
- At most 15,000,000 bytes for the entire JSON body, including base64.
- 1–64 questions; 1–1024 criteria per choice/score question.
- Multi-choice returns at most 10 selections; the default maximum is `min(candidate count, 10)`.

The server validates token limits; byte checks are not token counts. Inspect `/v1/models` for current context limits.

## Async

```python
import asyncio
from simplex_ai import AsyncSimplexClient, Noul


async def main():
    async with AsyncSimplexClient() as client:
        result = await client.system_one(
            state="The user said hello.",
            questions={"greeting": Noul(instructions="Is this a greeting?")},
        )
        print(result.answers["greeting"])


asyncio.run(main())
```

Reuse clients for connection pooling. Close explicitly with `close()` / `await aclose()` if not using a context manager. Default timeout is 120 seconds; pass a number or `httpx.Timeout` to customize.

## Errors and retries

```python
from simplex_ai import APIError, APITimeoutError, RateLimitError

# Wrap your call:
# except RateLimitError as exc: inspect exc.retry_after
# except APITimeoutError: execution may have completed; check usage before retrying
# except APIError as exc: inspect exc.status_code, exc.request_id, exc.body
```

Invalid request data raises `ValueError` (including Pydantic `ValidationError`) before the request is sent. HTTP errors raise `APIError`; 401/403 use `AuthenticationError`, 429 uses `RateLimitError`. Network failures use `APIConnectionError` / `APITimeoutError`. Invalid successful responses use `APIResponseError`.

The SDK does not retry requests or follow redirects. A timeout or gateway error may leave execution status unknown. `retry_after` is the raw HTTP header (seconds or HTTP date); choose your application's retry policy explicitly. Custom transports may implement their own policies. Error bodies may contain application data; inspect them deliberately rather than logging indiscriminately.

<details>
<summary>Advanced effort — not recommended for normal use</summary>

`effort` accepts integers 1–5 and defaults to 1. Keep the default for normal use. Higher values evaluate more candidate orders, increase latency, and charge the corresponding 1×–5× input usage. This is not a guarantee of better accuracy. For an advanced experiment, pass `effort=2`; the SDK emits a warning. Applies to SPX-CD only; Jev accepts effort=1. Removed `reasoning` and `reasoning_max_tokens` arguments are no longer accepted.

</details>

## Development and release

```bash
python -m venv .venv
# Activate .venv for your shell
python -m pip install -e '.[dev]'
pytest
ruff check .
mypy src/simplex_ai
python -m build
python -m twine check dist/*
```

See [RELEASING.md](RELEASING.md) for manual PyPI publication. Tests use mocked HTTP, not paid inference. Optional real API smoke test: `python examples/smoke.py` with `SIMPLEX_API_TOKEN` set.

MIT licensed. This is an independent implementation for Simplex AI's API; no Jev SDK code is vendored.
