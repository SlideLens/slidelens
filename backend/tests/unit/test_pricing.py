"""Ставки моделей и расчёт стоимости Разбора в рублях."""

from __future__ import annotations

import pytest

from core.llm.config import (
    FALLBACK_MODEL_PRICE_RUB,
    LLMConfig,
    ModelPrice,
)
from core.llm.utils import estimate_asr_cost_rub, estimate_cost_rub


def _config(**overrides: object) -> LLMConfig:
    return LLMConfig(api_key="k", **overrides)  # type: ignore[arg-type]


def test_price_is_taken_per_model_not_per_tier_name() -> None:
    config = _config(model_full="gemini-2.5-flash", model_screening="gemini-2.5-flash-lite")

    full = config.price_for(config.model_for_tier("full"))
    screening = config.price_for(config.model_for_tier("screening"))

    assert (full.input_rub_per_mtok, full.output_rub_per_mtok) == (60, 500)
    assert (screening.input_rub_per_mtok, screening.output_rub_per_mtok) == (20, 80)


def test_versioned_model_id_falls_back_to_its_family_price() -> None:
    """``gpt-4o-2024-08-06`` не должен уезжать в fallback — это тот же gpt-4o."""
    price = _config().price_for("gpt-4o-2024-08-06")

    assert (price.input_rub_per_mtok, price.output_rub_per_mtok) == (250, 2000)


def test_longest_prefix_wins_over_shorter_one() -> None:
    """``gpt-4o-mini`` дешевле ``gpt-4o``, и префикс не должен их путать."""
    price = _config().price_for("gpt-4o-mini")

    assert (price.input_rub_per_mtok, price.output_rub_per_mtok) == (15, 120)


def test_unknown_model_uses_the_expensive_fallback() -> None:
    """Занизить стоимость опаснее, чем завысить: на ней строятся тарифы."""
    assert _config().price_for("совершенно-новая-модель") == FALLBACK_MODEL_PRICE_RUB


def test_cost_matches_the_provider_rate_card() -> None:
    price = ModelPrice(input_rub_per_mtok=60, output_rub_per_mtok=500)

    # Замеренный профиль 7-слайдового Разбора: ~87k входных, ~6k выходных.
    cost = estimate_cost_rub(price, 87_000, 6_000)

    assert cost == pytest.approx(87_000 * 60 / 1e6 + 6_000 * 500 / 1e6)
    assert cost == pytest.approx(8.22, abs=0.01)


def test_negative_token_counts_do_not_produce_negative_cost() -> None:
    price = ModelPrice(input_rub_per_mtok=60, output_rub_per_mtok=500)

    assert estimate_cost_rub(price, -5, -5) == 0.0


def test_asr_price_is_per_minute() -> None:
    config = _config(model_transcription="whisper-1")

    rate = config.asr_price_for(config.model_transcription)
    # Замер пользователя: 6 ₽ за 4:30 ≈ 1.33 ₽/мин при прайсе 1.2 ₽/мин.
    assert rate == 1.2
    assert estimate_asr_cost_rub(rate, 270) == pytest.approx(5.4)


def test_prices_can_be_overridden_without_touching_code() -> None:
    """Прайс провайдера меняется — конфиг должен переживать это без правок."""
    config = _config(
        model_full="gemini-2.5-flash",
        model_prices_rub={
            "gemini-2.5-flash": ModelPrice(input_rub_per_mtok=70, output_rub_per_mtok=550)
        },
    )

    assert config.price_for("gemini-2.5-flash").input_rub_per_mtok == 70
