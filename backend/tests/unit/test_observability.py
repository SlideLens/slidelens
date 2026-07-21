"""Observability setup tests."""

from __future__ import annotations

import json

import pytest
import structlog
from fastapi.testclient import TestClient

from observability.context import review_context
from observability.setup import (
    observe_review_cost,
    setup_logging,
    setup_metrics,
    setup_sentry,
)


def test_log_contains_review_id(capsys: pytest.CaptureFixture[str]) -> None:
    setup_logging(json_logs=True)
    log = structlog.get_logger()
    with review_context(review_id="abc-111"):
        log.info("hello", step="test")
    captured = capsys.readouterr().out.strip().splitlines()[-1]
    payload = json.loads(captured)
    assert payload["review_id"] == "abc-111"
    assert payload["event"] == "hello"


def test_sentry_captures_with_test_transport() -> None:
    events: list[object] = []

    class Transport:
        def capture_envelope(self, envelope: object) -> None:  # noqa: ANN001
            events.append(envelope)

        def capture_event(self, event: object) -> None:  # noqa: ANN001
            events.append(event)

    import sentry_sdk
    from sentry_sdk.transport import Transport as BaseTransport

    class CapturingTransport(BaseTransport):
        def capture_envelope(self, envelope):  # noqa: ANN001
            events.append(envelope)

    sentry_sdk.init(
        dsn="http://public@example.com/1",
        transport=CapturingTransport(),
    )
    try:
        raise RuntimeError("sentry-test-exception")
    except RuntimeError as exc:
        sentry_sdk.capture_exception(exc)
    sentry_sdk.flush(timeout=2)
    assert events, "expected Sentry transport to receive an event"
    # also exercise setup helper path
    assert setup_sentry("") is False


def test_metrics_endpoint_and_cost() -> None:
    setup_metrics()
    observe_review_cost(0.25)

    from app.main import create_app

    client = TestClient(create_app())
    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    assert "review_cost_rub" in body
    assert "pipeline_step_duration_seconds" in body
    assert "queue_depth" in body
    assert "reviews_total" in body
    # exact shape covered by tests/unit/test_app_main.py::test_health_and_metrics
    assert client.get("/health").status_code == 200
