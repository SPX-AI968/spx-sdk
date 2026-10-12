"""Simplex AI Python SDK."""

from .client import AsyncSimplexClient, SimplexClient
from .errors import (
    APIConnectionError,
    APIError,
    APIResponseError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
    SimplexError,
)
from .types import (
    Choice,
    ChoiceAnswer,
    DecisionResponse,
    Image,
    Model,
    MultiChoice,
    MultiChoiceAnswer,
    Noul,
    NoulAnswer,
    NoulCriteria,
    Score,
    ScoreAnswer,
    Usage,
)

__version__ = "0.2.0"
__all__ = [
    "SimplexClient",
    "AsyncSimplexClient",
    "Choice",
    "MultiChoice",
    "Noul",
    "Score",
    "NoulCriteria",
    "Image",
    "Model",
    "DecisionResponse",
    "ChoiceAnswer",
    "MultiChoiceAnswer",
    "NoulAnswer",
    "ScoreAnswer",
    "Usage",
    "SimplexError",
    "APIError",
    "AuthenticationError",
    "RateLimitError",
    "APIConnectionError",
    "APITimeoutError",
    "APIResponseError",
    "__version__",
]
