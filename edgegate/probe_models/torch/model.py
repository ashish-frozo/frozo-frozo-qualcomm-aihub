"""
Tiny deterministic PyTorch model for ProbeSuite.

This is the smallest possible model that:
- Can be torch.jit.traced
- Accepts a fixed-shape tensor input
- Produces deterministic output
- Is fast to compile and run

Architecture: 2-layer MLP (Linear -> ReLU -> Linear)
Input shape: (1, 16) - batch of 1, 16 features
Output shape: (1, 8) - batch of 1, 8 features
"""

import torch
import torch.nn as nn


# Fixed seed for deterministic weight initialization
SEED = 42
INPUT_SHAPE = (1, 16)
OUTPUT_SHAPE = (1, 8)


class TinyMLP(nn.Module):
    """
    Minimal 2-layer MLP for probe testing.

    This model is designed to be:
    - Extremely small (< 1KB weights)
    - Deterministic with fixed seed
    - Fast to trace and compile
    - Compatible with ONNX export
    """

    def __init__(self, input_dim: int = 16, hidden_dim: int = 8, output_dim: int = 8):
        super().__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(hidden_dim, output_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass through the network."""
        x = self.fc1(x)
        x = self.relu(x)
        x = self.fc2(x)
        return x


def create_model(seed: int = SEED) -> TinyMLP:
    """
    Create a TinyMLP with deterministic weights.

    Args:
        seed: Random seed for weight initialization.

    Returns:
        TinyMLP instance with deterministic weights.
    """
    torch.manual_seed(seed)
    model = TinyMLP()
    model.eval()
    return model


def get_input_spec() -> dict:
    """
    Get the input specification for the model.

    Returns:
        Dictionary with input specs for AI Hub.
    """
    return {
        "x": {
            "shape": list(INPUT_SHAPE),
            "dtype": "float32",
        }
    }


if __name__ == "__main__":
    # Quick sanity check
    model = create_model()
    print(f"TinyMLP created with {sum(p.numel() for p in model.parameters())} parameters")

    # Test forward pass
    from edgegate.probe_models.torch.inputs import create_input

    x = create_input()
    with torch.no_grad():
        y = model(x)
    print(f"Input shape: {x.shape}, Output shape: {y.shape}")
    print(f"Output (first 4 values): {y[0, :4].tolist()}")
