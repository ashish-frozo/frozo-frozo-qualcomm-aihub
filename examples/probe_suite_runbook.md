# EdgeGate ProbeSuite Runbook

The `ProbeSuite` is the core capability discovery engine of EdgeGate. It runs a series of "probes" against the Qualcomm AI Hub to determine what devices, runtimes, and models are supported for a given workspace.

## Prerequisites

- Qualcomm AI Hub API Token
- EdgeGate Workspace ID
- Python 3.9+ environment

## How to Run a Probe

### 1. Via API (Recommended)

Trigger a probe discovery for a workspace:

```bash
curl -X POST "http://localhost:8000/v1/workspaces/{workspace_id}/capabilities/probe" \
  -H "Authorization: Bearer {your_token}"
```

### 2. Via CLI (Development)

You can run the probe suite directly using the provided example script:

```bash
export QAI_HUB_API_TOKEN="your_token"
python examples/aihub_probe.py --workspace-id {workspace_id}
```

## Probes Executed

1. **Token Validation**: Verifies the AI Hub token is valid and has access.
2. **Device Listing**: Retrieves the list of available devices for the workspace.
3. **Compilation Probes**:
   - **TorchScript**: Compiles a dummy model to TFLite/QNN.
   - **ONNX**: Compiles an ONNX model to TFLite/QNN.
4. **Profiling Probes**: Runs a profile job on selected devices to capture performance metrics.

## Artifacts Generated

After a successful probe, the following artifacts are stored in the workspace:

- `workspace_capabilities.json`: Summary of supported devices and runtimes.
- `metric_mapping.json`: Mapping of AI Hub raw metrics to EdgeGate normalized metrics.

## Troubleshooting

### NoIntegrationError
The workspace does not have a Qualcomm AI Hub integration configured. Add one via:
`POST /v1/workspaces/{id}/integrations`

### ProbeFailedError
A specific probe failed (e.g., compilation error). Check the `probe_raw` artifact for detailed logs from AI Hub.

### Token Expired
Update the integration token:
`PUT /v1/workspaces/{id}/integrations/{integration_id}`
