"""
Model metadata JSON schema validator.

Validates model metadata documents against the schema defined in edgegate/schemas/model_metadata.schema.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

from edgegate.validators.base import (
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)


class ModelMetadataValidator:
    """Validates model metadata JSON documents against schema."""

    # PRD §5 hard limit
    MAX_MODEL_SIZE_MB = 500

    def __init__(self, schema_path: Path | None = None):
        """
        Initialize the validator.

        Args:
            schema_path: Path to the JSON schema file. If None, uses default location.
        """
        if schema_path is None:
            schema_path = (
                Path(__file__).parent.parent / "schemas" / "model_metadata.schema.json"
            )

        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")

        with open(schema_path) as f:
            self._schema = json.load(f)

        self._validator = Draft7Validator(self._schema)

    def validate(self, data: dict[str, Any]) -> ValidationResult:
        """
        Validate a model metadata document.

        Args:
            data: The model metadata JSON data to validate.

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

        # Step 2: Validate packaging_type consistency with quantization
        packaging_type = data.get("packaging_type")
        quantization = data.get("quantization", {})

        if packaging_type == "aimet" and quantization.get("method") not in ("aimet", None):
            issues.append(
                ValidationIssue(
                    message="AIMET packaging should have quantization.method='aimet' or unset",
                    severity=ValidationSeverity.WARNING,
                    path="quantization.method",
                    code="INCONSISTENT_QUANTIZATION",
                )
            )

        # Step 3: Validate input shapes are reasonable
        input_specs = data.get("input_specs", {})
        for input_name, spec in input_specs.items():
            shape = spec.get("shape", [])
            # Check for obviously invalid shapes
            if any(dim == 0 for dim in shape):
                issues.append(
                    ValidationIssue(
                        message=f"Input '{input_name}' has zero dimension in shape",
                        severity=ValidationSeverity.ERROR,
                        path=f"input_specs.{input_name}.shape",
                        code="INVALID_SHAPE",
                    )
                )

        valid = len([i for i in issues if i.severity == ValidationSeverity.ERROR]) == 0
        return ValidationResult(valid=valid, issues=issues, data=data if valid else None)

    def validate_json_string(self, json_string: str) -> ValidationResult:
        """
        Validate model metadata from a JSON string.

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

    def validate_model_size(self, size_bytes: int) -> ValidationResult:
        """
        Validate that model size is within PRD limits.

        Args:
            size_bytes: Size of the model in bytes.

        Returns:
            ValidationResult indicating if size is acceptable.
        """
        max_bytes = self.MAX_MODEL_SIZE_MB * 1024 * 1024
        if size_bytes > max_bytes:
            return ValidationResult(
                valid=False,
                issues=[
                    ValidationIssue(
                        message=f"Model size {size_bytes / (1024*1024):.1f}MB exceeds limit of {self.MAX_MODEL_SIZE_MB}MB",
                        severity=ValidationSeverity.ERROR,
                        path=None,
                        code="LIMIT_EXCEEDED",
                    )
                ],
                data=None,
            )
        return ValidationResult(valid=True, issues=[], data={"size_bytes": size_bytes})
