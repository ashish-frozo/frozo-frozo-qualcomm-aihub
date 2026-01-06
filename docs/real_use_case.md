# Real Use Case: Model Optimization Regression Testing

This guide explains how to use EdgeGate to manage the lifecycle of model optimization, specifically focusing on comparing a baseline model with an optimized version.

## The Problem

When optimizing models for edge devices (e.g., quantizing from FP32 to INT8), developers face two main risks:
1.  **Quality Regression**: The optimized model might lose accuracy on critical edge cases.
2.  **Performance Uncertainty**: The optimization might not provide the expected speedup or memory reduction on the target hardware (e.g., Qualcomm NPU).

## The EdgeGate Solution

EdgeGate provides a structured workflow to mitigate these risks using **Pipelines** and **Quality Gates**.

### Workflow Steps

1.  **Define a Baseline**: Run your original FP32 model through a Pipeline to establish "Golden Metrics" for latency, memory, and accuracy.
2.  **Set Quality Gates**: Define strict thresholds in your Pipeline. For example:
    - `inference_time_ms` <= 50ms
    - `accuracy` >= 99% of baseline
3.  **Automated Comparison**: Trigger a new run with the optimized model. EdgeGate automatically:
    - Deploys to the target device (e.g., RB5).
    - Measures performance across multiple repeats.
    - Evaluates the model against your PromptPack.
    - Signs an **Evidence Bundle** if the gates pass.

## Example Scenario: Robotics Person Detection

In the `examples/regression_test.py` script, we simulate a robotics developer:

- **Baseline**: A TorchScript model running in FP32.
- **Optimized**: An AIMET-quantized version of the same model.
- **Target**: Qualcomm RB5 (NPU).
- **Goal**: 4x speedup with < 50MB memory footprint.

### Running the Scenario

```bash
python examples/regression_test.py
```

### Interpreting the Results

The script generates a comparison report:

```text
Metric               | Baseline (FP32) | Optimized (INT8) | Delta     
----------------------------------------------------------------------
Latency              |     180.00 ms   |      45.00 ms   |  -75.0%
Memory               |     120.00 MB   |      32.00 MB   |  -73.3%

Final Verdict:
  ✅ PASS: Optimized model meets all quality gates.
  🚀 Speedup: 4.0x faster
  📉 Memory Reduction: 73.3%
```

## Why this matters

By integrating this into your CI/CD pipeline (see [github_action.yml](../examples/github_action.yml)), you ensure that **no regressed model ever reaches your production fleet**. Every deployment is backed by a cryptographically signed evidence bundle proving it meets your standards.
