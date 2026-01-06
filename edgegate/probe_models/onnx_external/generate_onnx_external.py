"""
Generate ONNX model with external weights from TinyMLP.

This script produces:
- model.onnx - ONNX model file with references to external data
- model.data - External weights data file
- manifest.json - Manifest with SHA-256 hashes

The generated files are deterministic and can be committed to the repo
or regenerated reproducibly.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import torch
import onnx

from edgegate.probe_models.torch.model import create_model, get_input_spec, INPUT_SHAPE
from edgegate.probe_models.torch.inputs import create_input


def generate_onnx_external(output_dir: Path | None = None) -> dict:
    """
    Generate ONNX model with external weights.

    Args:
        output_dir: Directory to save the files. If None, uses default location.

    Returns:
        Dictionary with generation metadata including file paths and hashes.
    """
    if output_dir is None:
        output_dir = Path(__file__).parent

    output_dir.mkdir(parents=True, exist_ok=True)

    # Create the model
    model = create_model()
    example_input = create_input()

    # First export to a temporary ONNX file
    temp_onnx_path = output_dir / "temp_model.onnx"
    final_onnx_path = output_dir / "model.onnx"
    data_path = output_dir / "model.data"

    # Export to ONNX
    torch.onnx.export(
        model,
        example_input,
        str(temp_onnx_path),
        export_params=True,
        opset_version=14,
        do_constant_folding=True,
        input_names=["x"],
        output_names=["output"],
        dynamic_axes=None,  # Fixed shapes for probe
    )

    # Load the ONNX model
    onnx_model = onnx.load(str(temp_onnx_path))

    # Convert to external data format
    onnx.save_model(
        onnx_model,
        str(final_onnx_path),
        save_as_external_data=True,
        all_tensors_to_one_file=True,
        location="model.data",
        size_threshold=0,  # Externalize all tensors
        convert_attribute=True,
    )

    # Remove temporary file
    temp_onnx_path.unlink()

    # Compute hashes
    onnx_hash = _compute_sha256(final_onnx_path)
    data_hash = _compute_sha256(data_path)

    # Create manifest
    manifest = {
        "format": "onnx_external",
        "version": "1.0",
        "files": {
            "onnx": {
                "path": "model.onnx",
                "sha256": onnx_hash,
                "size_bytes": final_onnx_path.stat().st_size,
            },
            "data": {
                "path": "model.data",
                "sha256": data_hash,
                "size_bytes": data_path.stat().st_size,
            },
        },
        "input_specs": get_input_spec(),
        "metadata": {
            "architecture": "TinyMLP",
            "opset_version": 14,
            "source": "torch.onnx.export",
            "torch_version": torch.__version__,
            "onnx_version": onnx.__version__,
        },
    }

    # Save manifest
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Generated ONNX with external weights:")
    print(f"  ONNX file: {final_onnx_path}")
    print(f"  ONNX SHA-256: {onnx_hash}")
    print(f"  Data file: {data_path}")
    print(f"  Data SHA-256: {data_hash}")
    print(f"  Manifest: {manifest_path}")

    return manifest


def verify_onnx_external(directory: Path) -> bool:
    """
    Verify that the ONNX external files are valid.

    Args:
        directory: Directory containing the ONNX files.

    Returns:
        True if valid, False otherwise.
    """
    onnx_path = directory / "model.onnx"
    data_path = directory / "model.data"
    manifest_path = directory / "manifest.json"

    if not all(p.exists() for p in [onnx_path, data_path, manifest_path]):
        print("Missing required files")
        return False

    # Load and verify manifest
    with open(manifest_path) as f:
        manifest = json.load(f)

    # Verify hashes
    onnx_hash = _compute_sha256(onnx_path)
    data_hash = _compute_sha256(data_path)

    if onnx_hash != manifest["files"]["onnx"]["sha256"]:
        print(f"ONNX hash mismatch: {onnx_hash} != {manifest['files']['onnx']['sha256']}")
        return False

    if data_hash != manifest["files"]["data"]["sha256"]:
        print(f"Data hash mismatch: {data_hash} != {manifest['files']['data']['sha256']}")
        return False

    # Load and verify ONNX model
    try:
        onnx_model = onnx.load(str(onnx_path), load_external_data=True)
        onnx.checker.check_model(onnx_model)
        print("ONNX model verification passed")
        return True
    except Exception as e:
        print(f"ONNX verification failed: {e}")
        return False


def _compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        # Verify existing files
        output_dir = Path(__file__).parent
        if verify_onnx_external(output_dir):
            print("Verification passed!")
            sys.exit(0)
        else:
            print("Verification failed!")
            sys.exit(1)
    else:
        # Generate files
        generate_onnx_external()
