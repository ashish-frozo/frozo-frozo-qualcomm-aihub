"""
AIMET Package Validator.

Validates AIMET quantized model packages per PRD §8.3:
- Directory name must contain ".aimet" (strict for MVP)
- Exactly 1 .onnx file
- Exactly 1 .encodings file
- Optional: 0 or 1 .data file
"""

from __future__ import annotations

import hashlib
import tempfile
import zipfile
from pathlib import Path
from typing import BinaryIO

from edgegate.validators.base import (
    PackageValidationResult,
    ValidationIssue,
    ValidationSeverity,
)


class AimetValidator:
    """Validates AIMET quantized model packages."""

    AIMET_DIR_MARKER = ".aimet"

    def validate_directory(self, directory: Path) -> PackageValidationResult:
        """
        Validate an AIMET package from a directory.

        Args:
            directory: Path to the directory containing the package files.

        Returns:
            PackageValidationResult with validation status and discovered files.
        """
        if not directory.is_dir():
            return PackageValidationResult(
                valid=False,
                package_type="aimet",
                issues=[
                    ValidationIssue(
                        message=f"Path is not a directory: {directory}",
                        severity=ValidationSeverity.ERROR,
                        code="NOT_A_DIRECTORY",
                    )
                ],
            )

        issues: list[ValidationIssue] = []
        files: dict[str, Path] = {}

        # Check directory name contains .aimet (PRD §8.3: strict for MVP)
        if self.AIMET_DIR_MARKER not in directory.name.lower():
            issues.append(
                ValidationIssue(
                    message=f"AIMET package directory name must contain '{self.AIMET_DIR_MARKER}'",
                    severity=ValidationSeverity.ERROR,
                    code="INVALID_AIMET_DIR_NAME",
                )
            )

        # Count files by extension
        file_counts: dict[str, int] = {}
        for file_path in directory.iterdir():
            if file_path.is_file():
                ext = file_path.suffix.lower()
                file_counts[ext] = file_counts.get(ext, 0) + 1

                if ext == ".onnx":
                    files["onnx"] = file_path
                elif ext == ".encodings":
                    files["encodings"] = file_path
                elif ext == ".data":
                    files["data"] = file_path

        # Check for exactly 1 .onnx file
        onnx_count = file_counts.get(".onnx", 0)
        if onnx_count == 0:
            issues.append(
                ValidationIssue(
                    message="Missing .onnx file",
                    severity=ValidationSeverity.ERROR,
                    code="MISSING_ONNX",
                )
            )
        elif onnx_count > 1:
            issues.append(
                ValidationIssue(
                    message=f"Found {onnx_count} .onnx files, expected exactly 1",
                    severity=ValidationSeverity.ERROR,
                    code="MULTIPLE_ONNX",
                )
            )

        # Check for exactly 1 .encodings file
        encodings_count = file_counts.get(".encodings", 0)
        if encodings_count == 0:
            issues.append(
                ValidationIssue(
                    message="Missing .encodings file",
                    severity=ValidationSeverity.ERROR,
                    code="MISSING_ENCODINGS",
                )
            )
        elif encodings_count > 1:
            issues.append(
                ValidationIssue(
                    message=f"Found {encodings_count} .encodings files, expected exactly 1",
                    severity=ValidationSeverity.ERROR,
                    code="MULTIPLE_ENCODINGS",
                )
            )

        # Check for at most 1 .data file (optional)
        data_count = file_counts.get(".data", 0)
        if data_count > 1:
            issues.append(
                ValidationIssue(
                    message=f"Found {data_count} .data files, expected at most 1",
                    severity=ValidationSeverity.ERROR,
                    code="MULTIPLE_DATA",
                )
            )

        # Validate encodings file is valid JSON (if present)
        if "encodings" in files:
            encodings_check = self._validate_encodings_file(files["encodings"])
            if encodings_check:
                issues.append(encodings_check)

        # Compute manifest with hashes
        manifest: dict[str, dict] = {}
        for key, path in files.items():
            manifest[key] = {
                "path": str(path.name),
                "sha256": self._compute_sha256(path),
                "size_bytes": path.stat().st_size,
            }

        valid = len([i for i in issues if i.severity == ValidationSeverity.ERROR]) == 0
        return PackageValidationResult(
            valid=valid,
            package_type="aimet",
            issues=issues,
            files=files,
            manifest=manifest,
        )

    def validate_zip(self, zip_path: Path) -> PackageValidationResult:
        """
        Validate an AIMET package from a zip file.

        The zip must extract to a directory whose name contains '.aimet'.

        Args:
            zip_path: Path to the zip file.

        Returns:
            PackageValidationResult with validation status.
        """
        if not zip_path.is_file():
            return PackageValidationResult(
                valid=False,
                package_type="aimet",
                issues=[
                    ValidationIssue(
                        message=f"File not found: {zip_path}",
                        severity=ValidationSeverity.ERROR,
                        code="FILE_NOT_FOUND",
                    )
                ],
            )

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)
                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(tmpdir_path)

                # Find the extracted directory
                extracted_dirs = [d for d in tmpdir_path.iterdir() if d.is_dir()]

                if len(extracted_dirs) == 1:
                    # Zip contains a single directory
                    return self.validate_directory(extracted_dirs[0])
                elif len(extracted_dirs) == 0:
                    # Files are at root level - create a virtual directory
                    # Check if zip filename contains .aimet
                    if self.AIMET_DIR_MARKER not in zip_path.stem.lower():
                        return PackageValidationResult(
                            valid=False,
                            package_type="aimet",
                            issues=[
                                ValidationIssue(
                                    message=f"AIMET package must have directory or zip name containing '{self.AIMET_DIR_MARKER}'",
                                    severity=ValidationSeverity.ERROR,
                                    code="INVALID_AIMET_DIR_NAME",
                                )
                            ],
                        )
                    # Validate files directly in tmpdir
                    return self._validate_flat_directory(tmpdir_path)
                else:
                    return PackageValidationResult(
                        valid=False,
                        package_type="aimet",
                        issues=[
                            ValidationIssue(
                                message="AIMET zip should contain exactly one directory",
                                severity=ValidationSeverity.ERROR,
                                code="MULTIPLE_ROOT_DIRS",
                            )
                        ],
                    )
        except zipfile.BadZipFile:
            return PackageValidationResult(
                valid=False,
                package_type="aimet",
                issues=[
                    ValidationIssue(
                        message="Invalid zip file",
                        severity=ValidationSeverity.ERROR,
                        code="INVALID_ZIP",
                    )
                ],
            )

    def _validate_flat_directory(self, directory: Path) -> PackageValidationResult:
        """Validate when files are directly in directory (not nested)."""
        issues: list[ValidationIssue] = []
        files: dict[str, Path] = {}
        file_counts: dict[str, int] = {}

        for file_path in directory.iterdir():
            if file_path.is_file():
                ext = file_path.suffix.lower()
                file_counts[ext] = file_counts.get(ext, 0) + 1

                if ext == ".onnx":
                    files["onnx"] = file_path
                elif ext == ".encodings":
                    files["encodings"] = file_path
                elif ext == ".data":
                    files["data"] = file_path

        # Same validation logic as validate_directory
        onnx_count = file_counts.get(".onnx", 0)
        if onnx_count == 0:
            issues.append(
                ValidationIssue(
                    message="Missing .onnx file",
                    severity=ValidationSeverity.ERROR,
                    code="MISSING_ONNX",
                )
            )
        elif onnx_count > 1:
            issues.append(
                ValidationIssue(
                    message=f"Found {onnx_count} .onnx files, expected exactly 1",
                    severity=ValidationSeverity.ERROR,
                    code="MULTIPLE_ONNX",
                )
            )

        encodings_count = file_counts.get(".encodings", 0)
        if encodings_count == 0:
            issues.append(
                ValidationIssue(
                    message="Missing .encodings file",
                    severity=ValidationSeverity.ERROR,
                    code="MISSING_ENCODINGS",
                )
            )
        elif encodings_count > 1:
            issues.append(
                ValidationIssue(
                    message=f"Found {encodings_count} .encodings files, expected exactly 1",
                    severity=ValidationSeverity.ERROR,
                    code="MULTIPLE_ENCODINGS",
                )
            )

        data_count = file_counts.get(".data", 0)
        if data_count > 1:
            issues.append(
                ValidationIssue(
                    message=f"Found {data_count} .data files, expected at most 1",
                    severity=ValidationSeverity.ERROR,
                    code="MULTIPLE_DATA",
                )
            )

        if "encodings" in files:
            encodings_check = self._validate_encodings_file(files["encodings"])
            if encodings_check:
                issues.append(encodings_check)

        manifest: dict[str, dict] = {}
        for key, path in files.items():
            manifest[key] = {
                "path": str(path.name),
                "sha256": self._compute_sha256(path),
                "size_bytes": path.stat().st_size,
            }

        valid = len([i for i in issues if i.severity == ValidationSeverity.ERROR]) == 0
        return PackageValidationResult(
            valid=valid,
            package_type="aimet",
            issues=issues,
            files=files,
            manifest=manifest,
        )

    def _validate_encodings_file(self, encodings_path: Path) -> ValidationIssue | None:
        """
        Validate that the encodings file is valid JSON.

        Note: We do NOT validate the internal structure of encodings,
        as that would require knowledge of AIMET's encoding format.
        Per PRD: do not create fake .encodings files.

        Args:
            encodings_path: Path to the .encodings file.

        Returns:
            ValidationIssue if invalid, None otherwise.
        """
        try:
            import json

            with open(encodings_path) as f:
                json.load(f)
        except json.JSONDecodeError as e:
            return ValidationIssue(
                message=f"Invalid JSON in .encodings file: {e}",
                severity=ValidationSeverity.ERROR,
                code="INVALID_ENCODINGS_JSON",
            )
        except Exception as e:
            return ValidationIssue(
                message=f"Could not read .encodings file: {e}",
                severity=ValidationSeverity.ERROR,
                code="ENCODINGS_READ_ERROR",
            )
        return None

    @staticmethod
    def _compute_sha256(file_path: Path) -> str:
        """Compute SHA-256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()


# Blocking issue per user requirements
BLOCKING_ISSUE = """
# Blocking Issue: Provide real AIMET ONNX+encodings fixture

## Status: BLOCKED

## Description
The AIMET probe step requires a real AIMET-generated fixture containing:
- `model.onnx` - Quantized ONNX model file generated by AIMET
- `model.encodings` - AIMET encodings file (JSON format with quantization parameters)
- `model.data` (optional) - External weights data file

## Requirements
1. The fixture must be generated by the actual AIMET toolkit
2. Do NOT create fake/synthetic .encodings files
3. The directory must be named with `.aimet` suffix (e.g., `probe_model.aimet/`)

## How to Generate
1. Install AIMET: https://github.com/quic/aimet
2. Quantize a simple model (e.g., the tiny MLP from probe_models/torch)
3. Export using AIMET's ONNX export with encodings
4. Place files in `probe_models/aimet_quant.aimet/`

## Current Workaround
The ProbeSuite will skip the AIMET probe step if no valid fixture exists.
The `MODEL_AIMET_ONNX_ENCODINGS` capability will be marked as unavailable.

## Priority
Medium - Not blocking MVP, but required for full AIMET support.
"""
