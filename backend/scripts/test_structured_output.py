"""Smoke-test Structured Output against the configured OpenAI-compatible API.

Compares three styles:
  1) Responses API: ``client.responses.parse(..., text_format=Person)``  (your example)
  2) Chat Completions: ``beta.chat.completions.parse(..., response_format=Person)``
  3) Chat Completions: manual ``response_format=json_schema`` from ``model_json_schema()``
     — what ``LLMClient`` does today

Usage (from ``slidelens/backend``)::

    uv run python scripts/test_structured_output.py

Reads ``LLM_API_KEY`` / ``LLM_BASE_URL`` / ``LLM_MODEL_FULL`` from
``backend/.env``.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

from openai import OpenAI
from pydantic import BaseModel


class Person(BaseModel):
    name: str
    age: int
    job: str
    company: str


PROMPT = "Ивану 28 лет, он работает Python-разработчиком в компании OpenAI."


def _load_dotenv() -> None:
    path = Path(__file__).resolve().parents[1] / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)

def _client() -> tuple[OpenAI, str]:
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").strip()
    model = os.environ.get("LLM_MODEL_FULL", "gpt-4o").strip()
    if not api_key:
        print("ERROR: LLM_API_KEY is empty", file=sys.stderr)
        sys.exit(1)
    print(f"base_url={base_url}")
    print(f"model={model}")
    print(f"api_key=***{api_key[-4:]}")
    return OpenAI(api_key=api_key, base_url=base_url), model


def _section(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def test_responses_parse(client: OpenAI, model: str) -> None:
    _section("1) responses.parse + text_format=Person")
    try:
        response = client.responses.parse(
            model=model,
            input=PROMPT,
            text_format=Person,
        )
        person = response.output_parsed
        print("OK:", person)
        print("name=", person.name, "age=", person.age)
    except Exception as exc:  # noqa: BLE001 — smoke script
        print("FAIL:", type(exc).__name__, exc)
        traceback.print_exc()


def test_chat_parse(client: OpenAI, model: str) -> None:
    _section("2) beta.chat.completions.parse + response_format=Person")
    try:
        response = client.beta.chat.completions.parse(
            model=model,
            messages=[{"role": "user", "content": PROMPT}],
            response_format=Person,
            temperature=0,
        )
        person = response.choices[0].message.parsed
        print("OK:", person)
        print("refusal=", response.choices[0].message.refusal)
    except Exception as exc:  # noqa: BLE001 — smoke script
        print("FAIL:", type(exc).__name__, exc)
        traceback.print_exc()


def test_manual_json_schema(client: OpenAI, model: str) -> None:
    _section("3) chat.completions.create + manual json_schema (current LLMClient)")
    schema = Person.model_json_schema()
    print("schema keys:", sorted(schema.keys()))
    print("additionalProperties on root:", schema.get("additionalProperties", "<missing>"))
    print(json.dumps(schema, ensure_ascii=False, indent=2))
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": PROMPT}],
            temperature=0,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": Person.__name__,
                    "schema": schema,
                    "strict": True,
                },
            },
        )
        text = response.choices[0].message.content or ""
        print("raw:", text)
        person = Person.model_validate_json(text)
        print("OK:", person)
    except Exception as exc:  # noqa: BLE001 — smoke script
        print("FAIL:", type(exc).__name__, exc)
        traceback.print_exc()


def main() -> None:
    _load_dotenv()
    client, model = _client()
    test_responses_parse(client, model)
    test_chat_parse(client, model)
    test_manual_json_schema(client, model)
    print("\nDone.")


if __name__ == "__main__":
    main()
