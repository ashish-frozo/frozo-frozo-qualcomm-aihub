"""
Generate fixed input tensor for the TinyMLP probe model.

Produces deterministic input data for reproducible testing.
"""

import torch

from edgegate.probe_models.torch.model import INPUT_SHAPE, SEED


def create_input(seed: int = SEED, batch_size: int = 1) -> torch.Tensor:
    """
    Create a deterministic input tensor for the TinyMLP model.

    Args:
        seed: Random seed for reproducibility.
        batch_size: Batch size (default 1 for probing).

    Returns:
        Input tensor of shape (batch_size, 16).
    """
    torch.manual_seed(seed)
    # Create input with same seed for determinism
    input_shape = (batch_size, INPUT_SHAPE[1])
    return torch.randn(input_shape)


def create_input_numpy(seed: int = SEED, batch_size: int = 1):
    """
    Create a deterministic input as numpy array.

    Useful for inference jobs that require numpy input.

    Args:
        seed: Random seed for reproducibility.
        batch_size: Batch size (default 1 for probing).

    Returns:
        Numpy array of shape (batch_size, 16).
    """
    return create_input(seed, batch_size).numpy()


def get_expected_output(seed: int = SEED) -> torch.Tensor:
    """
    Get the expected output for the default input.

    This is useful for validating that the model produces
    consistent results across different runtimes.

    Args:
        seed: Random seed used for model and input creation.

    Returns:
        Expected output tensor.
    """
    from edgegate.probe_models.torch.model import create_model

    model = create_model(seed)
    x = create_input(seed)
    with torch.no_grad():
        return model(x)


if __name__ == "__main__":
    # Print the expected input and output for reference
    x = create_input()
    print(f"Input shape: {x.shape}")
    print(f"Input values: {x.tolist()}")

    y = get_expected_output()
    print(f"Expected output shape: {y.shape}")
    print(f"Expected output values: {y.tolist()}")
