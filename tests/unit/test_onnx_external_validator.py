"""
Unit tests for ONNX external weights validator.

Tests cover:
- Valid packages with exactly 1 .onnx and 1 .data file
- Missing file detection
- Multiple file detection
- Zip file validation
- SHA-256 hash computation
"""

import json
import tempfile
import zipfile
from pathlib import Path

import pytest

from edgegate.validators import OnnxExternalValidator


@pytest.fixture
def validator():
    """Create an OnnxExternalValidator instance."""
    return OnnxExternalValidator()


@pytest.fixture
def valid_package_dir(tmp_path):
    """Create a valid ONNX external weights package directory."""
    # Create mock .onnx file that references model.data
    onnx_content = b"ONNX model content with reference to model.data"
    (tmp_path / "model.onnx").write_bytes(onnx_content)

    # Create mock .data file
    (tmp_path / "model.data").write_bytes(b"External weights data")

    return tmp_path


@pytest.fixture
def valid_package_zip(valid_package_dir, tmp_path):
    """Create a valid ONNX external weights package as a zip file."""
    zip_path = tmp_path / "package.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(valid_package_dir / "model.onnx", "model.onnx")
        zf.write(valid_package_dir / "model.data", "model.data")
    return zip_path


class TestValidOnnxExternalPackage:
    """Tests for valid ONNX external packages."""

    def test_valid_directory(self, validator, valid_package_dir):
        """Test validation of a valid package directory."""
        result = validator.validate_directory(valid_package_dir)

        assert result.valid
        assert result.package_type == "onnx_external"
        assert len(result.errors) == 0
        assert "onnx" in result.files
        assert "data" in result.files
        assert "onnx" in result.manifest
        assert "data" in result.manifest

    def test_valid_directory_has_hashes(self, validator, valid_package_dir):
        """Test that validation produces SHA-256 hashes."""
        result = validator.validate_directory(valid_package_dir)

        assert result.manifest["onnx"]["sha256"]
        assert len(result.manifest["onnx"]["sha256"]) == 64  # SHA-256 hex length
        assert result.manifest["data"]["sha256"]
        assert len(result.manifest["data"]["sha256"]) == 64

    def test_valid_zip(self, validator, valid_package_zip):
        """Test validation of a valid package zip file."""
        result = validator.validate_zip(valid_package_zip)

        assert result.valid
        assert result.package_type == "onnx_external"
        assert len(result.errors) == 0


class TestMissingFiles:
    """Tests for missing file detection."""

    def test_missing_onnx_file(self, validator, tmp_path):
        """Test that missing .onnx file is detected."""
        (tmp_path / "model.data").write_bytes(b"data")

        result = validator.validate_directory(tmp_path)

        assert not result.valid
        assert any(e.code == "MISSING_ONNX" for e in result.errors)

    def test_missing_data_file(self, validator, tmp_path):
        """Test that missing .data file is detected."""
        (tmp_path / "model.onnx").write_bytes(b"onnx")

        result = validator.validate_directory(tmp_path)

        assert not result.valid
        assert any(e.code == "MISSING_DATA" for e in result.errors)

    def test_empty_directory(self, validator, tmp_path):
        """Test that empty directory fails validation."""
        result = validator.validate_directory(tmp_path)

        assert not result.valid
        assert any(e.code == "MISSING_ONNX" for e in result.errors)
        assert any(e.code == "MISSING_DATA" for e in result.errors)


class TestMultipleFiles:
    """Tests for multiple file detection."""

    def test_multiple_onnx_files(self, validator, tmp_path):
        """Test that multiple .onnx files fail validation."""
        (tmp_path / "model1.onnx").write_bytes(b"onnx1")
        (tmp_path / "model2.onnx").write_bytes(b"onnx2")
        (tmp_path / "model.data").write_bytes(b"data")

        result = validator.validate_directory(tmp_path)

        assert not result.valid
        assert any(e.code == "MULTIPLE_ONNX" for e in result.errors)

    def test_multiple_data_files(self, validator, tmp_path):
        """Test that multiple .data files fail validation."""
        (tmp_path / "model.onnx").write_bytes(b"onnx with model.data reference")
        (tmp_path / "weights1.data").write_bytes(b"data1")
        (tmp_path / "weights2.data").write_bytes(b"data2")

        result = validator.validate_directory(tmp_path)

        assert not result.valid
        assert any(e.code == "MULTIPLE_DATA" for e in result.errors)


class TestDataReferenceCheck:
    """Tests for best-effort data reference check."""

    def test_data_reference_found(self, validator, tmp_path):
        """Test that no warning when ONNX references data file."""
        # Create ONNX that contains reference to model.data
        (tmp_path / "model.onnx").write_bytes(b"ONNX content with model.data reference")
        (tmp_path / "model.data").write_bytes(b"data")

        result = validator.validate_directory(tmp_path)

        assert result.valid
        # No warning about missing reference
        assert not any(e.code == "DATA_REFERENCE_NOT_FOUND" for e in result.warnings)

    def test_data_reference_missing_warning(self, validator, tmp_path):
        """Test that warning is issued when ONNX doesn't reference data file."""
        # Create ONNX without reference to data file
        (tmp_path / "model.onnx").write_bytes(b"ONNX content without any file reference")
        (tmp_path / "other.data").write_bytes(b"data")  # Different name

        result = validator.validate_directory(tmp_path)

        # Should still be valid (warning, not error) - but this case has MISSING_DATA
        # Let's use the correct filename
        (tmp_path / "model.data").write_bytes(b"data")
        (tmp_path / "other.data").unlink()

        result = validator.validate_directory(tmp_path)

        # Validation should pass (warning only)
        assert result.valid
        assert any(e.code == "DATA_REFERENCE_NOT_FOUND" for e in result.warnings)


class TestZipValidation:
    """Tests for zip file validation."""

    def test_invalid_zip_file(self, validator, tmp_path):
        """Test that invalid zip files fail validation."""
        bad_zip = tmp_path / "bad.zip"
        bad_zip.write_bytes(b"not a zip file")

        result = validator.validate_zip(bad_zip)

        assert not result.valid
        assert any(e.code == "INVALID_ZIP" for e in result.errors)

    def test_nonexistent_zip_file(self, validator, tmp_path):
        """Test that nonexistent files fail validation."""
        result = validator.validate_zip(tmp_path / "nonexistent.zip")

        assert not result.valid
        assert any(e.code == "FILE_NOT_FOUND" for e in result.errors)


class TestEdgeCases:
    """Tests for edge cases."""

    def test_not_a_directory(self, validator, tmp_path):
        """Test that file path (not directory) fails validation."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("not a directory")

        result = validator.validate_directory(file_path)

        assert not result.valid
        assert any(e.code == "NOT_A_DIRECTORY" for e in result.errors)

    def test_case_insensitive_extensions(self, validator, tmp_path):
        """Test that extensions are matched case-insensitively."""
        (tmp_path / "model.ONNX").write_bytes(b"onnx with model.data")
        (tmp_path / "model.DATA").write_bytes(b"data")

        result = validator.validate_directory(tmp_path)

        assert result.valid

    def test_extra_files_ignored(self, validator, tmp_path):
        """Test that extra files (not .onnx/.data) are ignored."""
        (tmp_path / "model.onnx").write_bytes(b"onnx with model.data")
        (tmp_path / "model.data").write_bytes(b"data")
        (tmp_path / "readme.txt").write_text("readme")
        (tmp_path / "config.json").write_text("{}")

        result = validator.validate_directory(tmp_path)

        assert result.valid
        assert len(result.files) == 2  # Only .onnx and .data
