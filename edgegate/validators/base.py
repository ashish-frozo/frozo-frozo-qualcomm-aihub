"""
Base validation types and utilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ValidationSeverity(str, Enum):
    """Severity level for validation issues."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """A single validation issue."""

    message: str
    severity: ValidationSeverity
    path: str | None = None
    code: str | None = None

    def __str__(self) -> str:
        parts = []
        if self.code:
            parts.append(f"[{self.code}]")
        if self.path:
            parts.append(f"at {self.path}")
        parts.append(self.message)
        return " ".join(parts)


class ValidationError(Exception):
    """Raised when validation fails with one or more errors."""

    def __init__(self, message: str, issues: list[ValidationIssue] | None = None):
        super().__init__(message)
        self.message = message
        self.issues = issues or []

    def __str__(self) -> str:
        if not self.issues:
            return self.message
        issue_strs = [f"  - {issue}" for issue in self.issues]
        return f"{self.message}:\n" + "\n".join(issue_strs)


@dataclass
class ValidationResult:
    """Result of validating a JSON document against a schema."""

    valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    data: dict[str, Any] | None = None

    @property
    def errors(self) -> list[ValidationIssue]:
        """Return only error-level issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        """Return only warning-level issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]

    def raise_if_invalid(self) -> None:
        """Raise ValidationError if validation failed."""
        if not self.valid:
            raise ValidationError("Validation failed", self.errors)


@dataclass
class PackageValidationResult:
    """Result of validating a model package (directory or archive)."""

    valid: bool
    package_type: str
    issues: list[ValidationIssue] = field(default_factory=list)
    files: dict[str, Path] = field(default_factory=dict)
    manifest: dict[str, Any] = field(default_factory=dict)

    @property
    def errors(self) -> list[ValidationIssue]:
        """Return only error-level issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        """Return only warning-level issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]

    def raise_if_invalid(self) -> None:
        """Raise ValidationError if validation failed."""
        if not self.valid:
            raise ValidationError(
                f"Invalid {self.package_type} package",
                self.errors,
            )
