"""Prompt token-estimation helpers."""

from __future__ import annotations

from typing import Any


def estimate_text_tokens(
    text: str,
    *,
    model: str | None = None,
) -> dict[str, int | str | None]:
    """Estimate token usage for one text payload.

    Args:
        text: Text to estimate.
        model: Optional model name used to choose an encoding when supported.

    Returns:
        dict[str, int | str | None]: Cached token-estimate payload.
    """

    normalized_text = text or ""
    try:
        import tiktoken

        encoding = _encoding_for_model(tiktoken=tiktoken, model=model)
        return {
            "strategy": "tiktoken",
            "model": model,
            "encoding": getattr(encoding, "name", None),
            "token_count": len(encoding.encode(normalized_text)),
            "character_count": len(normalized_text),
        }
    except Exception:  # noqa: BLE001
        approximate_count = max(0, (len(normalized_text) + 3) // 4)
        return {
            "strategy": "approximate_chars_div_4",
            "model": model,
            "encoding": None,
            "token_count": approximate_count,
            "character_count": len(normalized_text),
        }


def estimate_prompt_bundle_tokens(
    *,
    base_system_prompt: str,
    system_prompt: str,
    enhancement_text: str | None,
    model: str | None = None,
) -> dict[str, int | str | None]:
    """Estimate token usage for a saved prompt bundle.

    Args:
        base_system_prompt: Base prompt before enhancement layers.
        system_prompt: Final rendered prompt.
        enhancement_text: Optional rendered prompt-enhancement block.
        model: Optional target model name for tokenizer selection.

    Returns:
        dict[str, int | str | None]: Cached prompt-bundle token estimates.
    """

    base_estimate = estimate_text_tokens(base_system_prompt, model=model)
    system_estimate = estimate_text_tokens(system_prompt, model=model)
    enhancement_estimate = (
        estimate_text_tokens(enhancement_text or "", model=model)
        if enhancement_text is not None
        else None
    )
    base_tokens = int(base_estimate.get("token_count") or 0)
    system_tokens = int(system_estimate.get("token_count") or 0)
    enhancement_tokens = (
        None
        if enhancement_estimate is None
        else int(enhancement_estimate.get("token_count") or 0)
    )
    return {
        "strategy": str(system_estimate.get("strategy")),
        "model": model,
        "encoding": system_estimate.get("encoding"),
        "base_system_prompt_tokens": base_tokens,
        "system_prompt_tokens": system_tokens,
        "enhancement_tokens": enhancement_tokens,
        "enhancement_text_tokens": enhancement_tokens,
        "prompt_delta_tokens": max(system_tokens - base_tokens, 0),
        "total_prompt_tokens": system_tokens,
        "base_system_prompt_characters": int(base_estimate.get("character_count") or 0),
        "system_prompt_characters": int(system_estimate.get("character_count") or 0),
        "enhancement_characters": (
            None
            if enhancement_estimate is None
            else int(enhancement_estimate.get("character_count") or 0)
        ),
    }


def estimate_prompt_enhancement_tokens(
    *,
    generated_context: str,
    exploration_context: str | None = None,
    user_context: str | None = None,
    business_rules: str | None = None,
    additional_effective_context: str | None = None,
    answer_style: str | None = None,
    model: str | None = None,
) -> dict[str, int | str | None]:
    """Estimate token usage for one prompt-enhancement artifact.

    Args:
        generated_context: Generated snapshot-derived prompt context.
        exploration_context: Optional live explored prompt context.
        user_context: Optional user-authored domain notes.
        business_rules: Optional user-authored business rules and caveats.
        additional_effective_context: Optional direct prompt instructions.
        answer_style: Optional answer-style guidance.
        model: Optional target model name for tokenizer selection.

    Returns:
        dict[str, int | str | None]: Per-layer and aggregate token estimates.
    """

    generated_estimate = estimate_text_tokens(generated_context, model=model)
    exploration_estimate = estimate_text_tokens(
        exploration_context or "",
        model=model,
    )
    user_estimate = estimate_text_tokens(user_context or "", model=model)
    rules_estimate = estimate_text_tokens(business_rules or "", model=model)
    effective_estimate = estimate_text_tokens(
        additional_effective_context or "",
        model=model,
    )
    style_estimate = estimate_text_tokens(answer_style or "", model=model)
    total = sum(
        int(payload.get("token_count") or 0)
        for payload in (
            generated_estimate,
            exploration_estimate,
            user_estimate,
            rules_estimate,
            effective_estimate,
            style_estimate,
        )
    )
    return {
        "strategy": str(generated_estimate.get("strategy")),
        "model": model,
        "encoding": generated_estimate.get("encoding"),
        "generated_context_tokens": int(generated_estimate.get("token_count") or 0),
        "generated_context_characters": int(
            generated_estimate.get("character_count") or 0
        ),
        "exploration_context_tokens": int(exploration_estimate.get("token_count") or 0),
        "exploration_context_characters": int(
            exploration_estimate.get("character_count") or 0
        ),
        "user_context_tokens": int(user_estimate.get("token_count") or 0),
        "user_context_characters": int(user_estimate.get("character_count") or 0),
        "business_rules_tokens": int(rules_estimate.get("token_count") or 0),
        "business_rules_characters": int(rules_estimate.get("character_count") or 0),
        "additional_effective_context_tokens": int(
            effective_estimate.get("token_count") or 0
        ),
        "additional_effective_context_characters": int(
            effective_estimate.get("character_count") or 0
        ),
        "answer_style_tokens": int(style_estimate.get("token_count") or 0),
        "answer_style_characters": int(style_estimate.get("character_count") or 0),
        "effective_enhancement_tokens": total,
    }


def _encoding_for_model(*, tiktoken: Any, model: str | None) -> Any:
    """Resolve the most appropriate tiktoken encoding for one model name."""

    if model:
        try:
            return tiktoken.encoding_for_model(model)
        except KeyError:
            pass
    return tiktoken.get_encoding("cl100k_base")
