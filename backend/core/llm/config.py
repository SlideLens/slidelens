"""LLM settings consumed by ``LLMClient`` (no import of ``app``)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelPrice(BaseModel):
    """Ставки одной модели, ₽ за 1M токенов."""

    model_config = ConfigDict(frozen=True)

    input_rub_per_mtok: float = Field(ge=0.0)
    output_rub_per_mtok: float = Field(ge=0.0)


# Прайс провайдера (aitunnel), снят 21.07.2026. Держим только те модели, которые
# реально включаем, — список на 200+ позиций устареет быстрее, чем принесёт пользу.
DEFAULT_MODEL_PRICES_RUB: dict[str, ModelPrice] = {
    "gemini-2.5-flash-lite": ModelPrice(input_rub_per_mtok=20, output_rub_per_mtok=80),
    "gemini-2.5-flash": ModelPrice(input_rub_per_mtok=60, output_rub_per_mtok=500),
    "gemini-3-flash-preview": ModelPrice(input_rub_per_mtok=100, output_rub_per_mtok=600),
    "gemini-3.5-flash": ModelPrice(input_rub_per_mtok=300, output_rub_per_mtok=1800),
    "gemini-2.5-pro": ModelPrice(input_rub_per_mtok=250, output_rub_per_mtok=2000),
    "gpt-4o-mini": ModelPrice(input_rub_per_mtok=15, output_rub_per_mtok=120),
    "gpt-4o": ModelPrice(input_rub_per_mtok=250, output_rub_per_mtok=2000),
}

# ₽ за минуту аудио.
DEFAULT_ASR_PRICES_RUB_PER_MINUTE: dict[str, float] = {
    "whisper-1": 1.2,
    "whisper-large-v3": 0.37,
    "whisper-large-v3-turbo": 0.13,
    "voxtral-mini-transcribe": 0.6,
}

# Неизвестную модель считаем по самой дорогой из используемых: занизить стоимость
# опаснее, чем завысить — на заниженной цифре строятся тарифы.
FALLBACK_MODEL_PRICE_RUB = ModelPrice(input_rub_per_mtok=250, output_rub_per_mtok=2000)
FALLBACK_ASR_PRICE_RUB_PER_MINUTE = 1.2


def _lookup[T](table: dict[str, T], model: str, fallback: T) -> T:
    """Точное совпадение, иначе самый длинный префикс (``gpt-4o-2024-08-06`` → ``gpt-4o``)."""
    if model in table:
        return table[model]
    matches = [key for key in table if model.startswith(key)]
    if not matches:
        return fallback
    return table[max(matches, key=len)]


class LLMConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model_full: str = "gpt-4o"
    model_screening: str = ""
    model_transcription: str = "whisper-1"
    timeout_seconds: float = 120.0
    max_retries_rate_limit: int = 3
    model_prices_rub: dict[str, ModelPrice] = Field(
        default_factory=lambda: dict(DEFAULT_MODEL_PRICES_RUB)
    )
    asr_prices_rub_per_minute: dict[str, float] = Field(
        default_factory=lambda: dict(DEFAULT_ASR_PRICES_RUB_PER_MINUTE)
    )

    def model_for_tier(self, tier: str) -> str:
        if tier == "screening" and self.model_screening:
            return self.model_screening
        return self.model_full

    def price_for(self, model: str) -> ModelPrice:
        return _lookup(self.model_prices_rub, model, FALLBACK_MODEL_PRICE_RUB)

    def asr_price_for(self, model: str) -> float:
        return _lookup(
            self.asr_prices_rub_per_minute, model, FALLBACK_ASR_PRICE_RUB_PER_MINUTE
        )
