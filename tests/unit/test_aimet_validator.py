"""
Unit tests for AIMET package validator.

Tests cover:
- Valid packages with .aimet directory name
- Missing file detection (.onnx, .encodings)
- Optional .data file handling
- Encodings file JSON validation
- Directory name requirements
"""

import json
import tempfile
import zipfile
from pathlib import Path

import pytest

from edgegate.validators import AimetValidator


@pytest.fixture
def validator():
    """Create an AimetValidator instance."""
    return AimetValidator()


@pytest.fixture
def valid_aimet_dir(tmp_path):
    """Create a valid AIMET package directory."""
    # Directory must contain .aimet
    aimet_dir = tmp_path / "model.aimet"
    aimet_dir.mkdir()

    # Create required files
    (aimet_dir / "model.onnx").write_bytes(b"ONNX model content")
    (aimet_dir / "model.encodings").write_text(json.dumps({
        "activation_encodings": {},
        "param_encodings": {},
    }))

    return aimet_dir


@pytest.fixture
def valid_aimet_with_data(valid_aimet_dir):
    """Create a valid AIMET package with optional .data file."""
    (valid_aimet_dir / "model.data").write_bytes(b"External weights")
    return valid_aimet_dir


class TestValidAimetPackage:
    """Tests for valid AIMET packages."""

    def test_valid_directory(self, validator, valid_aimet_dir):
        """Test validation of a valid AIMET package directory."""
        result = validator.validate_directory(valid_aimet_dir)

        assert result.valid
        assert result.package_type == "aimet"
        assert len(result.errors) == 0
        assert "onnx" in result.files
        assert "encodings" in result.files

    def test_valid_directory_with_data(self, validator, valid_aimet_with_data):
        """Test validation of AIMET package with optional .data file."""
        result = validator.validate_directory(valid_aimet_with_data)

        assert result.valid
        assert "data" in result.files

    def test_valid_directory_has_hashes(self, validator, valid_aimet_dir):
        """Test that validation produces SHA-256 hashes."""
        result = validator.validate_directory(valid_aimet_dir)

        assert result.manifest["onnx"]["sha256"]
        assert len(result.manifest["onnx"]["sha256"]) == 64
        assert result.manifest["encodings"]["sha256"]


class TestAimetDirectoryName:
    """Tests for .aimet directory name requirement."""

    def test_directory_without_aimet_marker_fails(self, validator, tmp_path):
        """Test that directory without .aimet in name fails (PRD §8.3)."""
        plain_dir = tmp_path / "model_package"
        plain_dir.mkdir()
        (plain_dir / "model.onnx").write_bytes(b"onnx")
        (plain_dir / "model.encodings").write_text('{}')

        result = validator.validate_directory(plain_dir)

        assert not result.valid
        assert any(e.code == "INVALID_AIMET_DIR_NAME" for e in result.errors)

    def test_directory_with_aimet_suffix_passes(self, validator, tmp_path):
        """Test that directory ending with .aimet passes."""
        aimet_dir = tmp_path / "my_model.aimet"
        aimet_dir.mkdir()
        (aimet_dir / "model.onnx").write_bytes(b"onnx")
        (aimet_dir / "model.encodings").write_text('{}')

        result = validator.validate_directory(aimet_dir)

        assert result.valid

    def test_directory_with_aimet_anywhere_passes(self, validator, tmp_path):
        """Test that directory containing .aimet anywhere passes."""
        aimet_dir = tmp_path / "model.aimet.v2"
        aimet_dir.mkdir()
        (aimet_dir / "model.onnx").write_bytes(b"onnx")
        (aimet_dir / "model.encodings").write_text('{}')

        result = validator.validate_directory(aimet_dir)

        assert result.valid


class TestMissingFiles:
    """Tests for missing file detection."""

    def test_missing_onnx_file(self, validator, tmp_path):
        """Test that missing .onnx file is detected."""
        aimet_dir = tmp_path / "test.aimet"
        aimet_dir.mkdir()
        (aimet_dir / "model.encodings").write_text('{}')

        result = validator.validate_directory(aimet_dir)

        assert not result.valid
        assert any(e.code == "MISSING_ONNX" for e in result.errors)

    def test_missing_encodings_file(self, validator, tmp_path):
        """Test that missing .encodings file is detected."""
        aimet_dir = tmp_path / "test.aimet"
        aimet_dir.mkdir()
        (aimet_dir / "model.onnx").write_bytes(b"onnx")

        result = validator.validate_directory(aimet_dir)

        assert not result.valid
        assert any(e.code == "MISSING_ENCODINGS" for e in result.errors)


class TestMultipleFiles:
    """Tests for multiple file detection."""

    def test_multiple_onnx_files(self, validator, tmp_path):
        """Test that multiple .onnx files fail validation."""
        aimet_dir = tmp_path / "test.aimet"
        aimet_dir.mkdir()
        (aimet_dir / "model1.onnx").write_bytes(b"onnx1")
        (aimet_dir / "model2.onnx").write_bytes(b"onnx2")
        (aimet_dir / "model.encodings").write_text('{}')

        result = validator.validate_directory(aimet_dir)

        assert not result.valid
        assert any(e.code == "MULTIPLE_ONNX" for e in result.errors)

    def test_multiple_encodings_files(self, validator, tmp_path):
        """Test that multiple .encodings files fail validation."""
        aimet_dir = tmp_path / "test.aimet"
        aimet_dir.mkdir()
        (aimet_dir / "model.onnx").write_bytes(b"onnx")
        (aimet_dir / "model1.encodings").write_text('{}')
        (aimet_dir / "model2.encodings").write_text('{}')

        result = validator.validate_directory(aimet_dir)

        assert not result.valid
        assert any(e.code == "MULTIPLE_ENCODINGS" for e in result.errors)

    def test_multiple_data_files(self, validator, tmp_path):
        """Test that multiple .data files fail validation."""
        aimet_dir = tmp_path / "test.aimet"
        aimet_dir.mkdir()
        (aimet_dir / "model.onnx").write_bytes(b"onnx")
        (aimet_dir / "model.encodings").write_text('{}')
        (aimet_dir / "weights1.data").write_bytes(b"data1")
        (aimet_dir / "weights2.data").write_bytes(b"data2")

        result = validator.validate_directory(aimet_dir)

        assert not result.valid
        assert any(e.code == "MULTIPLE_DATA" for e in result.errors)


class TestEncodingsValidation:
    """Tests for encodings file JSON validation."""

    def test_valid_encodings_json(self, validator, valid_aimet_dir):
        """Test that valid JSON encodings file passes."""
        result = validator.validate_directory(valid_aimet_dir)
        assert result.valid

    def test_invalid_encodings_json(self, validator, tmp_path):
        """Test that invalid JSON in encodings file fails."""
        aimet_dir = tmp_path / "test.aimet"
        aimet_dir.mkdir()
        (aimet_dir / "model.onnx").write_bytes(b"onnx")
        (aimet_dir / "model.encodings").write_text("not valid json {")

        result = validator.validate_directory(aimet_dir)

        assert not result.valid
        assert any(e.code == "INVALID_ENCODINGS_JSON" for e in result.errors)

    def test_empty_encodings_json(self, validator, tmp_path):
        """Test that empty JSON object in encodings is valid."""
        aimet_dir = tmp_path / "test.aimet"
        aimet_dir.mkdir()
        (aimet_dir / "model.onnx").write_bytes(b"onnx")
        (aimet_dir / "model.encodings").write_text('{}')

        result = validator.validate_directory(aimet_dir)

        assert result.valid


class TestZipValidation:
    """Tests for zip file validation."""

    def test_valid_aimet_zip_with_directory(self, validator, valid_aimet_dir, tmp_path):
        """Test validation of zip containing AIMET directory."""
        zip_path = tmp_path / "model.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            # Include directory structure
            zf.write(valid_aimet_dir / "model.onnx", "model.aimet/model.onnx")
            zf.write(valid_aimet_dir / "model.encodings", "model.aimet/model.encodings")

        result = validator.validate_zip(zip_path)

        assert result.valid

    def test_aimet_zip_name_fallback(self, validator, valid_aimet_dir, tmp_path):
        """Test that zip with .aimet in name allows flat structure."""
        zip_path = tmp_path / "model.aimet.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            # Flat structure - files at root
            zf.write(valid_aimet_dir / "model.onnx", "model.onnx")
            zf.write(valid_aimet_dir / "model.encodings", "model.encodings")

        result = validator.validate_zip(zip_path)

        assert result.valid

    def test_invalid_zip_file(self, validator, tmp_path):
        """Test that invalid zip files fail validation."""
        bad_zip = tmp_path / "bad.zip"
        bad_zip.write_bytes(b"not a zip")

        result = validator.validate_zip(bad_zip)

        assert not result.valid
        assert any(e.code == "INVALID_ZIP" for e in result.errors)


class TestBlockingIssue:
    """Tests for AIMET blocking issue documentation."""

    def test_blocking_issue_documented(self):
        """Verify blocking issue is documented in the module."""
        from edgegate.validators.aimet import BLOCKING_ISSUE

        assert "AIMET" in BLOCKING_ISSUE
        assert "model.onnx" in BLOCKING_ISSUE
        assert "model.encodings" in BLOCKING_ISSUE
        assert "BLOCKED" in BLOCKING_ISSUE
