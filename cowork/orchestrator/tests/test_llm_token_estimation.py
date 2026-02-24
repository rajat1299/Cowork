from __future__ import annotations

import math

import pytest

import app.runtime.llm_client as llm_client
from app.runtime.llm_client import estimate_text_tokens


def test_estimate_text_tokens_uses_model_tokenizer_for_openai_compatible_models() -> None:
    tiktoken = pytest.importorskip("tiktoken", reason="tiktoken not available")

    text = "def normalize_user_profile(data):\n    return {k: str(v).strip() for k, v in data.items()}\n"
    expected = len(tiktoken.encoding_for_model("gpt-4o-mini").encode(text))

    # OpenRouter models are often provider-prefixed (e.g. openai/gpt-4o-mini).
    actual = estimate_text_tokens(
        text,
        model_name="openai/gpt-4o-mini",
        provider_name="openrouter",
    )
    assert actual == expected


def test_estimate_text_tokens_returns_zero_for_empty_and_positive_for_non_empty() -> None:
    assert estimate_text_tokens("") == 0
    assert estimate_text_tokens("x", model_name="gpt-4o-mini", provider_name="openai") >= 1


def test_estimate_text_tokens_adds_anthropic_headroom(monkeypatch: pytest.MonkeyPatch) -> None:
    tiktoken = pytest.importorskip("tiktoken", reason="tiktoken not available")
    monkeypatch.setenv("ANTHROPIC_TOKEN_HEADROOM", "1.12")

    text = "Summarize commit history and explain regressions.\n" * 8
    base = len(tiktoken.encoding_for_model("gpt-4o-mini").encode(text))

    actual = estimate_text_tokens(
        text,
        model_name="claude-sonnet-4-5",
        provider_name="anthropic",
    )

    assert actual == int(math.ceil(base * 1.12))


def test_estimate_text_tokens_applies_fallback_headroom_without_tiktoken(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(llm_client, "tiktoken", None)
    monkeypatch.setenv("TOKEN_ESTIMATE_HEADROOM", "1.5")

    text = "alpha beta gamma delta"
    base = llm_client._fallback_estimate_tokens(text)
    actual = estimate_text_tokens(text, provider_name="openrouter")

    assert actual == int(math.ceil(base * 1.5))
