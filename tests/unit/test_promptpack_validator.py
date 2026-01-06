"""
Unit tests for PromptPack validator.

Tests cover:
- Valid PromptPack documents
- Schema validation errors
- PRD hard limit enforcement
- Duplicate case_id detection
- Regex pattern validation
- Canonicalization rules
"""

import pytest

from edgegate.validators import PromptPackValidator, ValidationError


@pytest.fixture
def validator():
    """Create a PromptPackValidator instance."""
    return PromptPackValidator()


@pytest.fixture
def valid_promptpack():
    """A minimal valid PromptPack document."""
    return {
        "promptpack_id": "test-pack-1",
        "version": "1.0.0",
        "name": "Test PromptPack",
        "cases": [
            {
                "case_id": "case-1",
                "name": "Test Case 1",
                "prompt": "Hello, world!",
            }
        ],
    }


@pytest.fixture
def full_promptpack():
    """A full PromptPack with all optional fields."""
    return {
        "promptpack_id": "full-test-pack",
        "version": "2.1.0-beta.1",
        "name": "Full Test PromptPack",
        "description": "A comprehensive test pack",
        "tags": ["test", "example"],
        "defaults": {
            "max_new_tokens": 128,
            "temperature": 0.2,
            "top_p": 0.95,
            "seed": 42,
        },
        "cases": [
            {
                "case_id": "json-case",
                "name": "JSON Output Test",
                "prompt": "Return a JSON object with name and age",
                "expected": {
                    "type": "json_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "age": {"type": "integer"},
                        },
                    },
                },
            },
            {
                "case_id": "regex-case",
                "name": "Regex Match Test",
                "prompt": "Say hello",
                "expected": {
                    "type": "regex",
                    "pattern": "^[Hh]ello.*",
                },
            },
            {
                "case_id": "exact-case",
                "name": "Exact Match Test",
                "prompt": "What is 2+2?",
                "expected": {
                    "type": "exact",
                    "text": "4",
                },
                "overrides": {
                    "max_new_tokens": 10,
                    "temperature": 0.0,
                },
            },
            {
                "case_id": "none-case",
                "name": "No Validation Test",
                "prompt": "Tell me a story",
                "expected": {
                    "type": "none",
                },
            },
        ],
    }


class TestPromptPackValidation:
    """Tests for basic PromptPack validation."""

    def test_valid_minimal_promptpack(self, validator, valid_promptpack):
        """Test that a minimal valid PromptPack passes validation."""
        result = validator.validate(valid_promptpack)
        assert result.valid
        assert len(result.errors) == 0
        assert result.data == valid_promptpack

    def test_valid_full_promptpack(self, validator, full_promptpack):
        """Test that a full PromptPack with all fields passes validation."""
        result = validator.validate(full_promptpack)
        assert result.valid
        assert len(result.errors) == 0

    def test_missing_required_fields(self, validator):
        """Test that missing required fields cause validation to fail."""
        result = validator.validate({})
        assert not result.valid
        assert len(result.errors) > 0
        # Should have errors for promptpack_id, version, name, cases
        error_paths = {e.path for e in result.errors}
        assert "root" in error_paths or any("required" in e.message.lower() for e in result.errors)

    def test_invalid_version_format(self, validator, valid_promptpack):
        """Test that invalid semver versions fail validation."""
        valid_promptpack["version"] = "not-a-version"
        result = validator.validate(valid_promptpack)
        assert not result.valid
        assert any("version" in str(e).lower() for e in result.errors)

    def test_valid_prerelease_version(self, validator, valid_promptpack):
        """Test that prerelease semver versions are accepted."""
        valid_promptpack["version"] = "1.0.0-alpha.1"
        result = validator.validate(valid_promptpack)
        assert result.valid

    def test_valid_build_metadata_version(self, validator, valid_promptpack):
        """Test that build metadata in versions is accepted."""
        valid_promptpack["version"] = "1.0.0+build.123"
        result = validator.validate(valid_promptpack)
        assert result.valid


class TestPromptPackLimits:
    """Tests for PRD hard limit enforcement."""

    def test_max_cases_limit(self, validator, valid_promptpack):
        """Test that exceeding 50 cases fails validation (PRD §5).
        
        Note: Limit is enforced by JSON schema maxItems constraint.
        """
        # Create 51 cases
        valid_promptpack["cases"] = [
            {"case_id": f"case-{i}", "name": f"Case {i}", "prompt": f"Prompt {i}"}
            for i in range(51)
        ]
        result = validator.validate(valid_promptpack)
        assert not result.valid
        # Schema enforces the limit with SCHEMA_ERROR
        assert any(e.code == "SCHEMA_ERROR" for e in result.errors)

    def test_exactly_50_cases_allowed(self, validator, valid_promptpack):
        """Test that exactly 50 cases is allowed."""
        valid_promptpack["cases"] = [
            {"case_id": f"case-{i}", "name": f"Case {i}", "prompt": f"Prompt {i}"}
            for i in range(50)
        ]
        result = validator.validate(valid_promptpack)
        assert result.valid

    def test_max_new_tokens_limit_defaults(self, validator, valid_promptpack):
        """Test that max_new_tokens > 256 in defaults fails (PRD §5).
        
        Note: Limit is enforced by JSON schema maximum constraint.
        """
        valid_promptpack["defaults"] = {"max_new_tokens": 257}
        result = validator.validate(valid_promptpack)
        assert not result.valid
        # Schema enforces the limit with SCHEMA_ERROR
        assert any(e.code == "SCHEMA_ERROR" for e in result.errors)

    def test_max_new_tokens_limit_overrides(self, validator, valid_promptpack):
        """Test that max_new_tokens > 256 in case overrides fails (PRD §5).
        
        Note: Limit is enforced by JSON schema maximum constraint.
        """
        valid_promptpack["cases"][0]["overrides"] = {"max_new_tokens": 300}
        result = validator.validate(valid_promptpack)
        assert not result.valid
        # Schema enforces the limit with SCHEMA_ERROR
        assert any(e.code == "SCHEMA_ERROR" for e in result.errors)

    def test_max_new_tokens_at_limit(self, validator, valid_promptpack):
        """Test that max_new_tokens = 256 is allowed."""
        valid_promptpack["defaults"] = {"max_new_tokens": 256}
        result = validator.validate(valid_promptpack)
        assert result.valid


class TestDuplicateCaseIds:
    """Tests for duplicate case_id detection."""

    def test_duplicate_case_id_fails(self, validator, valid_promptpack):
        """Test that duplicate case_ids fail validation."""
        valid_promptpack["cases"] = [
            {"case_id": "same-id", "name": "Case 1", "prompt": "Prompt 1"},
            {"case_id": "same-id", "name": "Case 2", "prompt": "Prompt 2"},
        ]
        result = validator.validate(valid_promptpack)
        assert not result.valid
        assert any(e.code == "DUPLICATE_CASE_ID" for e in result.errors)

    def test_unique_case_ids_pass(self, validator, valid_promptpack):
        """Test that unique case_ids pass validation."""
        valid_promptpack["cases"] = [
            {"case_id": "id-1", "name": "Case 1", "prompt": "Prompt 1"},
            {"case_id": "id-2", "name": "Case 2", "prompt": "Prompt 2"},
        ]
        result = validator.validate(valid_promptpack)
        assert result.valid


class TestExpectedOutputValidation:
    """Tests for expected output field validation."""

    def test_regex_invalid_pattern(self, validator, valid_promptpack):
        """Test that invalid regex patterns fail validation."""
        valid_promptpack["cases"][0]["expected"] = {
            "type": "regex",
            "pattern": "[invalid(regex",
        }
        result = validator.validate(valid_promptpack)
        assert not result.valid
        assert any(e.code == "INVALID_REGEX" for e in result.errors)

    def test_regex_valid_pattern(self, validator, valid_promptpack):
        """Test that valid regex patterns pass validation."""
        valid_promptpack["cases"][0]["expected"] = {
            "type": "regex",
            "pattern": "^test.*pattern$",
        }
        result = validator.validate(valid_promptpack)
        assert result.valid

    def test_json_schema_type_requires_schema(self, validator, valid_promptpack):
        """Test that json_schema type requires schema field."""
        valid_promptpack["cases"][0]["expected"] = {
            "type": "json_schema",
            # Missing "schema" field
        }
        result = validator.validate(valid_promptpack)
        assert not result.valid

    def test_exact_type_requires_text(self, validator, valid_promptpack):
        """Test that exact type requires text field."""
        valid_promptpack["cases"][0]["expected"] = {
            "type": "exact",
            # Missing "text" field
        }
        result = validator.validate(valid_promptpack)
        assert not result.valid


class TestCanonicalization:
    """Tests for canonicalization rules (PRD §12.2)."""

    def test_normalize_line_endings_crlf(self, validator):
        """Test that CRLF is normalized to LF."""
        text = "line1\r\nline2\r\nline3"
        result = validator.canonicalize(text)
        assert result == "line1\nline2\nline3"

    def test_normalize_line_endings_cr(self, validator):
        """Test that CR is normalized to LF."""
        text = "line1\rline2\rline3"
        result = validator.canonicalize(text)
        assert result == "line1\nline2\nline3"

    def test_trim_whitespace(self, validator):
        """Test that leading/trailing whitespace is trimmed."""
        text = "  \n  hello world  \n  "
        result = validator.canonicalize(text)
        assert result == "hello world"

    def test_canonicalize_json_sorted_keys(self, validator):
        """Test that JSON is serialized with sorted keys."""
        data = {"z": 1, "a": 2, "m": 3}
        result = validator.canonicalize_json(data)
        assert result == '{"a":2,"m":3,"z":1}'

    def test_canonicalize_json_no_whitespace(self, validator):
        """Test that canonical JSON has no whitespace."""
        data = {"key": "value", "nested": {"inner": True}}
        result = validator.canonicalize_json(data)
        assert " " not in result
        assert "\n" not in result


class TestJsonStringValidation:
    """Tests for JSON string parsing."""

    def test_valid_json_string(self, validator, valid_promptpack):
        """Test validation from valid JSON string."""
        import json

        json_str = json.dumps(valid_promptpack)
        result = validator.validate_json_string(json_str)
        assert result.valid

    def test_invalid_json_string(self, validator):
        """Test that invalid JSON strings fail."""
        result = validator.validate_json_string("not valid json {")
        assert not result.valid
        assert any(e.code == "INVALID_JSON" for e in result.errors)

    def test_empty_json_string(self, validator):
        """Test that empty strings fail."""
        result = validator.validate_json_string("")
        assert not result.valid


class TestValidationResult:
    """Tests for ValidationResult behavior."""

    def test_raise_if_invalid(self, validator):
        """Test that raise_if_invalid raises on invalid data."""
        result = validator.validate({})
        assert not result.valid
        with pytest.raises(ValidationError) as exc_info:
            result.raise_if_invalid()
        assert "failed" in str(exc_info.value).lower()

    def test_raise_if_invalid_noop_on_valid(self, validator, valid_promptpack):
        """Test that raise_if_invalid is a no-op on valid data."""
        result = validator.validate(valid_promptpack)
        result.raise_if_invalid()  # Should not raise
