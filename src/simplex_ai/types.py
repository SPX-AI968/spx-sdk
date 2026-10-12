"""Validated request types and forward-compatible response models."""

from __future__ import annotations

import base64
import binascii
import mimetypes
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Content = str | dict[str, Any] | list[Any]
Model = Literal["spx-cd", "spx-cd-auto", "spx-cd-flash", "spx-cd-pro", "typesafe-ai/jev"]
MAX_IMAGE_BYTES = 2_000_000
MAX_REQUEST_BYTES = 15_000_000
MEDIA_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class Question(RequestModel):
    instructions: Content | None = None


class Choice(Question):
    type: Literal["choice"] = "choice"
    criteria: dict[str, Content | None] = Field(min_length=1, max_length=1024)


class MultiChoice(Question):
    type: Literal["multi_choice"] = "multi_choice"
    criteria: dict[str, Content | None] = Field(min_length=1, max_length=1024)
    min_choices: int = Field(default=0, ge=0, strict=True)
    max_choices: int | None = Field(default=None, ge=0, le=10, strict=True)

    @model_validator(mode="after")
    def bounds(self) -> MultiChoice:
        if self.max_choices is None:
            self.max_choices = min(len(self.criteria), 10)
        if not self.min_choices <= self.max_choices <= len(self.criteria):
            raise ValueError("Expected 0 <= min_choices <= max_choices <= min(candidate count, 10)")
        return self


class NoulCriteria(RequestModel):
    true: Content | None = None
    false: Content | None = None


class Noul(Question):
    type: Literal["noul"] = "noul"
    criteria: NoulCriteria | None = None


class Score(Question):
    type: Literal["score"] = "score"
    criteria: list[Content] = Field(min_length=1, max_length=1024)


class Image(RequestModel):
    """A supported image encoded as a data URL; remote URLs are not fetched."""

    url: str
    detail: Literal["auto", "low", "high"] = "auto"

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        header, sep, encoded = value.partition(",")
        if not sep or header not in {f"data:{mime};base64" for mime in MEDIA_TYPES}:
            raise ValueError("Use a PNG, JPEG, WebP or GIF base64 data URL")
        if len(encoded) > 4 * ((MAX_IMAGE_BYTES + 2) // 3):
            raise ValueError("Image exceeds 2,000,000 bytes")
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("Invalid image base64") from exc
        if not 0 < len(data) <= MAX_IMAGE_BYTES:
            raise ValueError("Image must contain 1–2,000,000 bytes")
        return value

    @classmethod
    def from_bytes(
        cls, data: bytes, *, media_type: str, detail: Literal["auto", "low", "high"] = "auto"
    ) -> Image:
        if media_type not in MEDIA_TYPES:
            raise ValueError("Supported formats: PNG, JPEG, WebP, GIF")
        if not 0 < len(data) <= MAX_IMAGE_BYTES:
            raise ValueError("Image must contain 1–2,000,000 bytes")
        return cls(
            url=f"data:{media_type};base64,{base64.b64encode(data).decode('ascii')}", detail=detail
        )

    @classmethod
    def from_file(
        cls, path: str | Path, *, detail: Literal["auto", "low", "high"] = "auto"
    ) -> Image:
        """Read at most 2 MB plus one byte. Infer MIME type from the filename."""
        path = Path(path)
        mime, _ = mimetypes.guess_type(str(path))
        if mime not in MEDIA_TYPES:
            raise ValueError("Use a .png, .jpg, .jpeg, .webp or .gif file")
        with path.open("rb") as source:
            data = source.read(MAX_IMAGE_BYTES + 1)
        return cls.from_bytes(data, media_type=mime, detail=detail)


QuestionType = Annotated[Choice | MultiChoice | Noul | Score, Field(discriminator="type")]


class DecisionRequest(RequestModel):
    model: Model = "spx-cd"
    state: Any
    questions: dict[str, QuestionType] = Field(min_length=1, max_length=64)
    images: list[Image] = Field(default_factory=list, max_length=4)
    effort: int = Field(default=1, ge=1, le=5, strict=True)

    @model_validator(mode="after")
    def capabilities(self) -> DecisionRequest:
        if self.model == "typesafe-ai/jev":
            if (
                self.images
                or self.effort != 1
                or any(isinstance(q, MultiChoice) for q in self.questions.values())
            ):
                raise ValueError("Jev supports text Choice, Noul and Score with effort=1 only")
            if not isinstance(self.state, (str, dict, list)):
                raise ValueError("Jev state must be a string, object or array")
            if any(isinstance(q, Score) and len(q.criteria) < 2 for q in self.questions.values()):
                raise ValueError("Jev Score requires at least two criteria")
        return self


class ResponseModel(BaseModel):
    model_config = ConfigDict(extra="allow", hide_input_in_errors=True)


class Usage(ResponseModel):
    """None means unconfirmed or absent, never zero."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    status: str | None = None


class ChoiceAnswer(ResponseModel):
    type: Literal["choice"]
    choice: str
    probabilities: dict[str, float] | None = None
    confidence: float | None = None


class MultiChoiceAnswer(ResponseModel):
    type: Literal["multi_choice"]
    choices: list[str]
    steps: list[dict[str, Any]] | None = None


class NoulAnswer(ResponseModel):
    type: Literal["noul"]
    noul: float


class ScoreAnswer(ResponseModel):
    type: Literal["score"]
    score: float
    probabilities: dict[str, float] | None = None
    confidence: float | None = None


Answer = Annotated[
    ChoiceAnswer | MultiChoiceAnswer | NoulAnswer | ScoreAnswer, Field(discriminator="type")
]


class DecisionResponse(ResponseModel):
    model: str | None = None
    answers: dict[str, Answer]
    usage: Usage | None = None
    latency_ms: float | None = None
