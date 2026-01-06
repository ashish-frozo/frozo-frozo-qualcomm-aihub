"""
Unit tests for limits enforcement.

Tests cover:
- All PRD §5 hard limits
- Check vs enforce methods
- LimitExceededError
"""

import pytest

from edgegate.core import Settings
from edgegate.core.limits import LimitExceededError, LimitsEnforcer


@pytest.fixture
def settings():
    """Create settings with default limits."""
    return Settings(
        edgegenai_master_key="QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVowMTIzNA==",  # 32 bytes base64
    )


@pytest.fixture
def enforcer(settings):
    """Create a LimitsEnforcer instance."""
    return LimitsEnforcer(settings)


class TestModelUploadSize:
    """Tests for model upload size limit."""

    def test_check_within_limit(self, enforcer):
        """Test check passes for size within limit."""
        result = enforcer.check_model_upload_size(100 * 1024 * 1024)  # 100 MB
        assert result.valid
        assert result.message is None

    def test_check_at_limit(self, enforcer, settings):
        """Test check passes for size at limit."""
        max_bytes = settings.limit_model_upload_size_bytes
        result = enforcer.check_model_upload_size(max_bytes)
        assert result.valid

    def test_check_exceeds_limit(self, enforcer, settings):
        """Test check fails for size exceeding limit."""
        max_bytes = settings.limit_model_upload_size_bytes
        result = enforcer.check_model_upload_size(max_bytes + 1)
        assert not result.valid
        assert result.message is not None
        assert "500" in result.message  # Default limit in MB

    def test_enforce_raises_on_exceed(self, enforcer, settings):
        """Test enforce raises LimitExceededError on exceed."""
        max_bytes = settings.limit_model_upload_size_bytes
        with pytest.raises(LimitExceededError) as exc_info:
            enforcer.enforce_model_upload_size(max_bytes + 1)

        assert exc_info.value.limit_name == "model_upload_size"


class TestPromptPackCases:
    """Tests for PromptPack cases limit."""

    def test_check_within_limit(self, enforcer):
        """Test check passes for case count within limit."""
        result = enforcer.check_promptpack_cases(30)
        assert result.valid

    def test_check_at_limit(self, enforcer, settings):
        """Test check passes for case count at limit."""
        result = enforcer.check_promptpack_cases(settings.limit_promptpack_cases)
        assert result.valid

    def test_check_exceeds_limit(self, enforcer, settings):
        """Test check fails for case count exceeding limit."""
        result = enforcer.check_promptpack_cases(settings.limit_promptpack_cases + 1)
        assert not result.valid
        assert "50" in result.message  # Default limit

    def test_enforce_raises_on_exceed(self, enforcer, settings):
        """Test enforce raises on exceed."""
        with pytest.raises(LimitExceededError):
            enforcer.enforce_promptpack_cases(settings.limit_promptpack_cases + 1)


class TestDevicesPerRun:
    """Tests for devices per run limit."""

    def test_check_within_limit(self, enforcer):
        """Test check passes for device count within limit."""
        result = enforcer.check_devices_per_run(3)
        assert result.valid

    def test_check_at_limit(self, enforcer, settings):
        """Test check passes for device count at limit."""
        result = enforcer.check_devices_per_run(settings.limit_devices_per_run)
        assert result.valid

    def test_check_exceeds_limit(self, enforcer, settings):
        """Test check fails for device count exceeding limit."""
        result = enforcer.check_devices_per_run(settings.limit_devices_per_run + 1)
        assert not result.valid

    def test_enforce_raises_on_exceed(self, enforcer, settings):
        """Test enforce raises on exceed."""
        with pytest.raises(LimitExceededError):
            enforcer.enforce_devices_per_run(settings.limit_devices_per_run + 1)


class TestMeasurementRepeats:
    """Tests for measurement repeats limit."""

    def test_check_default_value(self, enforcer, settings):
        """Test check passes for default value."""
        result = enforcer.check_repeats(settings.limit_repeats_default)
        assert result.valid

    def test_check_at_max(self, enforcer, settings):
        """Test check passes at maximum."""
        result = enforcer.check_repeats(settings.limit_repeats_max)
        assert result.valid

    def test_check_exceeds_max(self, enforcer, settings):
        """Test check fails exceeding maximum."""
        result = enforcer.check_repeats(settings.limit_repeats_max + 1)
        assert not result.valid

    def test_enforce_raises_on_exceed(self, enforcer, settings):
        """Test enforce raises on exceed."""
        with pytest.raises(LimitExceededError):
            enforcer.enforce_repeats(settings.limit_repeats_max + 1)


class TestMaxNewTokens:
    """Tests for max_new_tokens limit."""

    def test_check_default_value(self, enforcer, settings):
        """Test check passes for default value."""
        result = enforcer.check_max_new_tokens(settings.limit_max_new_tokens_default)
        assert result.valid

    def test_check_at_max(self, enforcer, settings):
        """Test check passes at maximum."""
        result = enforcer.check_max_new_tokens(settings.limit_max_new_tokens_max)
        assert result.valid

    def test_check_exceeds_max(self, enforcer, settings):
        """Test check fails exceeding maximum."""
        result = enforcer.check_max_new_tokens(settings.limit_max_new_tokens_max + 1)
        assert not result.valid
        assert "256" in result.message  # Default max

    def test_enforce_raises_on_exceed(self, enforcer, settings):
        """Test enforce raises on exceed."""
        with pytest.raises(LimitExceededError):
            enforcer.enforce_max_new_tokens(settings.limit_max_new_tokens_max + 1)


class TestRunTimeout:
    """Tests for run timeout limit."""

    def test_check_default_value(self, enforcer, settings):
        """Test check passes for default value."""
        result = enforcer.check_run_timeout(settings.limit_run_timeout_default_minutes)
        assert result.valid

    def test_check_at_max(self, enforcer, settings):
        """Test check passes at maximum."""
        result = enforcer.check_run_timeout(settings.limit_run_timeout_max_minutes)
        assert result.valid

    def test_check_exceeds_max(self, enforcer, settings):
        """Test check fails exceeding maximum."""
        result = enforcer.check_run_timeout(settings.limit_run_timeout_max_minutes + 1)
        assert not result.valid
        assert "45" in result.message  # Default max

    def test_enforce_raises_on_exceed(self, enforcer, settings):
        """Test enforce raises on exceed."""
        with pytest.raises(LimitExceededError):
            enforcer.enforce_run_timeout(settings.limit_run_timeout_max_minutes + 1)


class TestLimitExceededError:
    """Tests for LimitExceededError."""

    def test_error_message(self):
        """Test error message format."""
        error = LimitExceededError("test_limit", 100, 50)

        assert error.limit_name == "test_limit"
        assert error.value == 100
        assert error.max_value == 50
        assert "test_limit" in str(error)
        assert "100" in str(error)
        assert "50" in str(error)
