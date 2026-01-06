"""
ONNX External Weights Package Validator.

Validates ONNX packages with external weights per PRD §8.3:
- Exactly 1 .onnx file
- Exactly 1 .data file
- Best-effort check that ONNX references .data by relative name
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


class OnnxExternalValidator:
    """Validates ONNX packages with external weights."""

    REQUIRED_EXTENSIONS = {".onnx": 1, ".data": 1}

    def validate_directory(self, directory: Path) -> PackageValidationResult:
        """
        Validate an ONNX external weights package from a directory.

        Args:
            directory: Path to the directory containing the package files.

        Returns:
            PackageValidationResult with validation status and discovered files.
        """
        if not directory.is_dir():
            return PackageValidationResult(
                valid=False,
                package_type="onnx_external",
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
        file_counts: dict[str, int] = {}

        # Scan directory for relevant files
        for file_path in directory.iterdir():
            if file_path.is_file():
                ext = file_path.suffix.lower()
                if ext in self.REQUIRED_EXTENSIONS:
                    file_counts[ext] = file_counts.get(ext, 0) + 1
                    if ext == ".onnx":
                        files["onnx"] = file_path
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

        # Check for exactly 1 .data file
        data_count = file_counts.get(".data", 0)
        if data_count == 0:
            issues.append(
                ValidationIssue(
                    message="Missing .data file",
                    severity=ValidationSeverity.ERROR,
                    code="MISSING_DATA",
                )
            )
        elif data_count > 1:
            issues.append(
                ValidationIssue(
                    message=f"Found {data_count} .data files, expected exactly 1",
                    severity=ValidationSeverity.ERROR,
                    code="MULTIPLE_DATA",
                )
            )

        # Best-effort: check if ONNX references the .data file
        if "onnx" in files and "data" in files:
            reference_check = self._check_onnx_data_reference(files["onnx"], files["data"])
            if reference_check:
                issues.append(reference_check)

        # Compute manifest with hashes
        manifest: dict[str, str] = {}
        for key, path in files.items():
            manifest[key] = {
                "path": str(path.name),
                "sha256": self._compute_sha256(path),
                "size_bytes": path.stat().st_size,
            }

        valid = len([i for i in issues if i.severity == ValidationSeverity.ERROR]) == 0
        return PackageValidationResult(
            valid=valid,
            package_type="onnx_external",
            issues=issues,
            files=files,
            manifest=manifest,
        )

    def validate_zip(self, zip_path: Path) -> PackageValidationResult:
        """
        Validate an ONNX external weights package from a zip file.

        Args:
            zip_path: Path to the zip file.

        Returns:
            PackageValidationResult with validation status.
        """
        if not zip_path.is_file():
            return PackageValidationResult(
                valid=False,
                package_type="onnx_external",
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
                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(tmpdir)
                return self.validate_directory(Path(tmpdir))
        except zipfile.BadZipFile:
            return PackageValidationResult(
                valid=False,
                package_type="onnx_external",
                issues=[
                    ValidationIssue(
                        message="Invalid zip file",
                        severity=ValidationSeverity.ERROR,
                        code="INVALID_ZIP",
                    )
                ],
            )

    def validate_stream(self, stream: BinaryIO) -> PackageValidationResult:
        """
        Validate an ONNX external weights package from a file stream.

        Args:
            stream: Binary file stream of a zip file.

        Returns:
            PackageValidationResult with validation status.
        """
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                with zipfile.ZipFile(stream, "r") as zf:
                    zf.extractall(tmpdir)
                return self.validate_directory(Path(tmpdir))
        except zipfile.BadZipFile:
            return PackageValidationResult(
                valid=False,
                package_type="onnx_external",
                issues=[
                    ValidationIssue(
                        message="Invalid zip file",
                        severity=ValidationSeverity.ERROR,
                        code="INVALID_ZIP",
                    )
                ],
            )

    def _check_onnx_data_reference(
        self, onnx_path: Path, data_path: Path
    ) -> ValidationIssue | None:
        """
        Best-effort check if ONNX file references the .data file.

        This is a heuristic check - we look for the .data filename in the ONNX file.
        Per PRD §8.3: "try to confirm ONNX references .data by relative name;
        if cannot parse, warn but do not block probe."

        Args:
            onnx_path: Path to the .onnx file.
            data_path: Path to the .data file.

        Returns:
            ValidationIssue (warning) if reference check fails, None otherwise.
        """
        try:
            # Read ONNX file and look for data filename reference
            onnx_content = onnx_path.read_bytes()
            data_filename = data_path.name.encode("utf-8")

            if data_filename not in onnx_content:
                return ValidationIssue(
                    message=f"ONNX file may not reference external data file '{data_path.name}'",
                    severity=ValidationSeverity.WARNING,
                    code="DATA_REFERENCE_NOT_FOUND",
                )
        except Exception:
            # Per PRD: "if cannot parse, warn but do not block probe"
            return ValidationIssue(
                message="Could not verify ONNX references external data file",
                severity=ValidationSeverity.WARNING,
                code="DATA_REFERENCE_CHECK_FAILED",
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
