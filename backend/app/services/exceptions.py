"""Service-layer domain errors."""

from __future__ import annotations


class LimitExceededError(Exception):
    """Оба кошелька пусты: ни пробных, ни купленных Разборов (HTTP 402)."""

    code = "LIMIT_REACHED"
    status_code = 402

    def __init__(
        self,
        message: str = "Закончились доступные Разборы — пополните баланс, чтобы продолжить",
    ) -> None:
        super().__init__(message)
        self.message = message


class ReviewValidationError(Exception):
    """Bad deck/audio/data format (HTTP 422)."""

    status_code = 422

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ReviewTooLargeError(Exception):
    """Deck exceeds the upload size limit (HTTP 413)."""

    status_code = 413

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ReviewNotFoundError(Exception):
    """Review doesn't exist, or isn't owned by the caller (HTTP 404, US-8)."""

    status_code = 404

    def __init__(self, message: str = "Разбор не найден") -> None:
        super().__init__(message)
        self.message = message


class ReviewNotReadyError(Exception):
    """Report requested before the Review reached ``done`` (HTTP 409)."""

    status_code = 409

    def __init__(self, message: str = "Разбор ещё не готов") -> None:
        super().__init__(message)
        self.message = message


class FindingNotFoundError(Exception):
    """Finding doesn't exist, or isn't owned by the caller (HTTP 404, US-8)."""

    status_code = 404

    def __init__(self, message: str = "Находка не найдена") -> None:
        super().__init__(message)
        self.message = message


class RehearsalNotFoundError(Exception):
    """Rehearsal doesn't exist, or isn't owned by the caller (HTTP 404, US-8)."""

    status_code = 404

    def __init__(self, message: str = "Репетиция не найдена") -> None:
        super().__init__(message)
        self.message = message


class RehearsalNotReadyError(Exception):
    """Rehearsal report requested before the attempt reached ``done`` (HTTP 409)."""

    status_code = 409

    def __init__(self, message: str = "Репетиция ещё обрабатывается") -> None:
        super().__init__(message)
        self.message = message


class RehearsalValidationError(Exception):
    """Bad audio/slide-timing payload (HTTP 422)."""

    status_code = 422

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
