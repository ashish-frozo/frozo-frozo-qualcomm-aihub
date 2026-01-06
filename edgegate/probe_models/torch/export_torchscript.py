"""
Export TinyMLP to TorchScript format.

This script generates the traced TorchScript model used by ProbeSuite.
The generated model is deterministic and can be committed to the repo.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import torch

from edgegate.probe_models.torch.model import create_model, get_input_spec
from edgegate.probe_models.torch.inputs import create_input


def export_torchscript(output_dir: Path | None = None) -> dict:
    """
    Export the TinyMLP model to TorchScript format.

    Args:
        output_dir: Directory to save the model. If None, uses the current script's directory.

    Returns:
        Dictionary with export metadata including file paths and hashes.
    """
    if output_dir is None:
        output_dir = Path(__file__).parent

    output_dir.mkdir(parents=True, exist_ok=True)

    # Create model and trace it
    model = create_model()
    example_input = create_input()

    # Trace the model
    traced_model = torch.jit.trace(model, example_input)

    # Save the traced model
    model_path = output_dir / "model.pt"
    traced_model.save(str(model_path))

    # Compute hash
    model_hash = _compute_sha256(model_path)

    # Create manifest
    manifest = {
        "format": "torchscript",
        "version": "1.0",
        "files": {
            "model": {
                "path": "model.pt",
                "sha256": model_hash,
                "size_bytes": model_path.stat().st_size,
            }
        },
        "input_specs": get_input_spec(),
        "metadata": {
            "architecture": "TinyMLP",
            "framework": f"torch {torch.__version__}",
            "trace_method": "torch.jit.trace",
        },
    }

    # Save manifest
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Exported TorchScript model to: {model_path}")
    print(f"Model SHA-256: {model_hash}")
    print(f"Model size: {manifest['files']['model']['size_bytes']} bytes")
    print(f"Manifest saved to: {manifest_path}")

    return manifest


def _compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


if __name__ == "__main__":
    export_torchscript()
