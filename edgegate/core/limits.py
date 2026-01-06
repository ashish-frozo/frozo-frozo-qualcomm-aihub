"""
Hard limit enforcement utilities.

Provides functions to validate inputs against PRD §5 hard limits.
These are enforced at the API boundary to reject invalid requests early.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edgegate.core import Settings


class LimitExceededError(Exception):
    """Raised when a hard limit is exceeded."""

    def __init__(self, limit_name: str, value: int | float, max_value: int | float):
        self.limit_name = limit_name
        self.value = value
        self.max_value = max_value
        super().__init__(
            f"Limit exceeded: {limit_name}. "
            f"Got {value}, maximum is {max_value}."
        )


@dataclass
class LimitCheck:
    """Result of a limit check."""

    valid: bool
    limit_name: str
    value: int | float
    max_value: int | float
    message: str | None = None


class LimitsEnforcer:
    """
    Enforces PRD §5 hard limits.
    
    All limits are configurable via settings but have maximum caps
    that cannot be exceeded.
    """

    def __init__(self, settings: "Settings"):
        self.settings = settings

    def check_model_upload_size(self, size_bytes: int) -> LimitCheck:
        """Check model upload size against limit."""
        max_bytes = self.settings.limit_model_upload_size_bytes
        return LimitCheck(
            valid=size_bytes <= max_bytes,
            limit_name="model_upload_size",
            value=size_bytes,
            max_value=max_bytes,
            message=f"Model size {size_bytes / (1024*1024):.1f}MB exceeds limit of {self.settings.limit_model_upload_size_mb}MB"
            if size_bytes > max_bytes
            else None,
        )

    def check_promptpack_cases(self, case_count: int) -> LimitCheck:
        """Check number of PromptPack cases against limit."""
        max_cases = self.settings.limit_promptpack_cases
        return LimitCheck(
            valid=case_count <= max_cases,
            limit_name="promptpack_cases",
            value=case_count,
            max_value=max_cases,
            message=f"PromptPack has {case_count} cases, exceeds limit of {max_cases}"
            if case_count > max_cases
            else None,
        )

    def check_devices_per_run(self, device_count: int) -> LimitCheck:
        """Check number of devices per run against limit."""
        max_devices = self.settings.limit_devices_per_run
        return LimitCheck(
            valid=device_count <= max_devices,
            limit_name="devices_per_run",
            value=device_count,
            max_value=max_devices,
            message=f"Run has {device_count} devices, exceeds limit of {max_devices}"
            if device_count > max_devices
            else None,
        )

    def check_repeats(self, repeats: int) -> LimitCheck:
        """Check measurement repeats against limit."""
        max_repeats = self.settings.limit_repeats_max
        return LimitCheck(
            valid=repeats <= max_repeats,
            limit_name="measurement_repeats",
            value=repeats,
            max_value=max_repeats,
            message=f"Repeats {repeats} exceeds limit of {max_repeats}"
            if repeats > max_repeats
            else None,
        )

    def check_max_new_tokens(self, tokens: int) -> LimitCheck:
        """Check max_new_tokens against limit."""
        max_tokens = self.settings.limit_max_new_tokens_max
        return LimitCheck(
            valid=tokens <= max_tokens,
            limit_name="max_new_tokens",
            value=tokens,
            max_value=max_tokens,
            message=f"max_new_tokens {tokens} exceeds limit of {max_tokens}"
            if tokens > max_tokens
            else None,
        )

    def check_run_timeout(self, timeout_minutes: int) -> LimitCheck:
        """Check run timeout against limit."""
        max_timeout = self.settings.limit_run_timeout_max_minutes
        return LimitCheck(
            valid=timeout_minutes <= max_timeout,
            limit_name="run_timeout",
            value=timeout_minutes,
            max_value=max_timeout,
            message=f"Timeout {timeout_minutes} minutes exceeds limit of {max_timeout} minutes"
            if timeout_minutes > max_timeout
            else None,
        )

    def enforce_model_upload_size(self, size_bytes: int) -> None:
        """Enforce model upload size limit, raise on violation."""
        check = self.check_model_upload_size(size_bytes)
        if not check.valid:
            raise LimitExceededError(check.limit_name, check.value, check.max_value)

    def enforce_promptpack_cases(self, case_count: int) -> None:
        """Enforce PromptPack cases limit, raise on violation."""
        check = self.check_promptpack_cases(case_count)
        if not check.valid:
            raise LimitExceededError(check.limit_name, check.value, check.max_value)

    def enforce_devices_per_run(self, device_count: int) -> None:
        """Enforce devices per run limit, raise on violation."""
        check = self.check_devices_per_run(device_count)
        if not check.valid:
            raise LimitExceededError(check.limit_name, check.value, check.max_value)

    def enforce_repeats(self, repeats: int) -> None:
        """Enforce measurement repeats limit, raise on violation."""
        check = self.check_repeats(repeats)
        if not check.valid:
            raise LimitExceededError(check.limit_name, check.value, check.max_value)

    def enforce_max_new_tokens(self, tokens: int) -> None:
        """Enforce max_new_tokens limit, raise on violation."""
        check = self.check_max_new_tokens(tokens)
        if not check.valid:
            raise LimitExceededError(check.limit_name, check.value, check.max_value)

    def enforce_run_timeout(self, timeout_minutes: int) -> None:
        """Enforce run timeout limit, raise on violation."""
        check = self.check_run_timeout(timeout_minutes)
        if not check.valid:
            raise LimitExceededError(check.limit_name, check.value, check.max_value)
