"""ClipCrop custom exception hierarchy.

Rooted at ClipCropError to provide strict, deterministic domain error handling.
Never raise bare Exception anywhere in the application.
"""

from __future__ import annotations


class ClipCropError(Exception):
    """Base exception for all ClipCrop pipeline and domain errors."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (details: {self.details})"
        return self.message


class ToolExecutionError(ClipCropError):
    """Raised when a perception or processing tool invocation fails."""


class StateValidationError(ClipCropError):
    """Raised on invalid state transitions, schema mismatches, or reducer violations."""


class PermanentFailureError(ClipCropError):
    """Raised on unrecoverable terminal pipeline failures (e.g. undecodable input, zero candidates)."""
