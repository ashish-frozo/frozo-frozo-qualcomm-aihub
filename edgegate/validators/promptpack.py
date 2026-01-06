"""
PromptPack JSON schema validator.

Validates PromptPack documents against the schema defined in schemas/promptpack.schema.json.
Implements PRD §12 requirements including canonicalization rules.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft7Validator, ValidationError as JsonSchemaError

from edgegate.validators.base import (
    PackageValidationResult,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)


class PromptPackValidator:
    """Validates PromptPack JSON documents against schema and PRD rules."""

    # PRD §5 hard limit
    MAX_CASES = 50
    MAX_NEW_TOKENS_MAX = 256

    def __init__(self, schema_path: Path | None = None):
        """
        Initialize the validator.

        Args:
            schema_path: Path to the JSON schema file. If None, uses default location.
        """
        if schema_path is None:
            # Find schema relative to this file
            schema_path = (
                Path(__file__).parent.parent.parent / "schemas" / "promptpack.schema.json"
            )

        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")

        with open(schema_path) as f:
            self._schema = json.load(f)

        self._validator = Draft7Validator(self._schema)

    def validate(self, data: dict[str, Any]) -> ValidationResult:
        """
        Validate a PromptPack document.

        Args:
            data: The PromptPack JSON data to validate.

        Returns:
            ValidationResult with validation status and any issues.
        """
        issues: list[ValidationIssue] = []

        # Step 1: JSON Schema validation
        schema_errors = list(self._validator.iter_errors(data))
        for error in schema_errors:
            path = ".".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
            issues.append(
                ValidationIssue(
                    message=error.message,
                    severity=ValidationSeverity.ERROR,
                    path=path,
                    code="SCHEMA_ERROR",
                )
            )

        # If schema validation failed, return early
        if issues:
            return ValidationResult(valid=False, issues=issues, data=None)

        # Step 2: PRD hard limit checks
        cases = data.get("cases", [])
        if len(cases) > self.MAX_CASES:
            issues.append(
                ValidationIssue(
                    message=f"PromptPack has {len(cases)} cases, exceeds limit of {self.MAX_CASES}",
                    severity=ValidationSeverity.ERROR,
                    path="cases",
                    code="LIMIT_EXCEEDED",
                )
            )

        # Check max_new_tokens in defaults
        defaults = data.get("defaults", {})
        if defaults.get("max_new_tokens", 128) > self.MAX_NEW_TOKENS_MAX:
            issues.append(
                ValidationIssue(
                    message=f"defaults.max_new_tokens exceeds maximum of {self.MAX_NEW_TOKENS_MAX}",
                    severity=ValidationSeverity.ERROR,
                    path="defaults.max_new_tokens",
                    code="LIMIT_EXCEEDED",
                )
            )

        # Check max_new_tokens in case overrides
        for i, case in enumerate(cases):
            overrides = case.get("overrides", {})
            if overrides.get("max_new_tokens", 128) > self.MAX_NEW_TOKENS_MAX:
                issues.append(
                    ValidationIssue(
                        message=f"Case overrides max_new_tokens exceeds maximum of {self.MAX_NEW_TOKENS_MAX}",
                        severity=ValidationSeverity.ERROR,
                        path=f"cases[{i}].overrides.max_new_tokens",
                        code="LIMIT_EXCEEDED",
                    )
                )

        # Step 3: Check for duplicate case_ids
        case_ids = [case.get("case_id") for case in cases]
        seen_ids: set[str] = set()
        for i, case_id in enumerate(case_ids):
            if case_id in seen_ids:
                issues.append(
                    ValidationIssue(
                        message=f"Duplicate case_id: {case_id}",
                        severity=ValidationSeverity.ERROR,
                        path=f"cases[{i}].case_id",
                        code="DUPLICATE_CASE_ID",
                    )
                )
            seen_ids.add(case_id)

        # Step 4: Validate regex patterns are compilable
        for i, case in enumerate(cases):
            expected = case.get("expected")
            if expected and expected.get("type") == "regex":
                pattern = expected.get("pattern", "")
                try:
                    re.compile(pattern)
                except re.error as e:
                    issues.append(
                        ValidationIssue(
                            message=f"Invalid regex pattern: {e}",
                            severity=ValidationSeverity.ERROR,
                            path=f"cases[{i}].expected.pattern",
                            code="INVALID_REGEX",
                        )
                    )

        valid = len([i for i in issues if i.severity == ValidationSeverity.ERROR]) == 0
        return ValidationResult(valid=valid, issues=issues, data=data if valid else None)

    def validate_json_string(self, json_string: str) -> ValidationResult:
        """
        Validate a PromptPack from a JSON string.

        Args:
            json_string: JSON string to parse and validate.

        Returns:
            ValidationResult with validation status and any issues.
        """
        try:
            data = json.loads(json_string)
        except json.JSONDecodeError as e:
            return ValidationResult(
                valid=False,
                issues=[
                    ValidationIssue(
                        message=f"Invalid JSON: {e}",
                        severity=ValidationSeverity.ERROR,
                        path=None,
                        code="INVALID_JSON",
                    )
                ],
                data=None,
            )
        return self.validate(data)

    @staticmethod
    def canonicalize(text: str) -> str:
        """
        Canonicalize text per PRD §12.2 rules.

        - Normalize line endings to LF
        - Trim leading/trailing whitespace

        Args:
            text: Input text to canonicalize.

        Returns:
            Canonicalized text.
        """
        # Normalize line endings to LF
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # Trim leading/trailing whitespace
        text = text.strip()
        return text

    @staticmethod
    def canonicalize_json(data: dict[str, Any]) -> str:
        """
        Canonicalize JSON for comparison per PRD §12.2.

        - Parse JSON
        - Re-serialize with sorted keys
        - No whitespace

        Args:
            data: JSON data to canonicalize.

        Returns:
            Canonical JSON string.
        """
        return json.dumps(data, sort_keys=True, separators=(",", ":"))
