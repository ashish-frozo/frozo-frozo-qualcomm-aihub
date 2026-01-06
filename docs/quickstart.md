# Consumer Quickstart Guide

This guide walks you through the end-to-end flow of using EdgeGate as a consumer. We will use the provided `examples/quickstart.py` script as a reference.

## 1. Prerequisites

- Python 3.9+
- A running EdgeGate API (see [README.md](../README.md) for local setup)
- `httpx` and `greenlet` installed in your environment

```bash
pip install httpx greenlet bcrypt==3.2.0
```

## 2. End-to-End Workflow

The `examples/quickstart.py` script demonstrates the following steps:

### A. User Registration & Login
First, you need to create an account and obtain an access token.

```python
# Register
resp = client.post("/v1/auth/register", json={"email": email, "password": password})
# Login
resp = client.post("/v1/auth/login", data={"username": email, "password": password})
token = resp.json()["access_token"]
```

### B. Workspace Creation
Create a workspace to organize your integrations, pipelines, and runs.

```python
resp = client.post("/v1/workspaces", json={"name": "Robotics Fleet A"}, headers=headers)
ws_id = resp.json()["id"]
```

### C. Connect AI Hub
Connect your Qualcomm AI Hub account using an API token.

```python
resp = client.post(
    f"/v1/workspaces/{ws_id}/integrations/qaihub",
    json={"token": "YOUR_AI_HUB_TOKEN"},
    headers=headers
)
```

### D. Capability Discovery (Probe)
Run a probe to discover available devices and compiler capabilities.

```python
resp = client.post(f"/v1/workspaces/{ws_id}/capabilities/probe", headers=headers)
task_id = resp.json()["task_id"]
# Poll for results...
```

### E. Create & Publish a PromptPack
Define your test cases and publish them for use in pipelines.

```python
resp = client.post(
    f"/v1/workspaces/{ws_id}/promptpacks",
    json={
        "promptpack_id": "vision-qa",
        "version": "1.0.0",
        "content": {
            "promptpack_id": "vision-qa",
            "version": "1.0.0",
            "name": "Vision QA Suite",
            "cases": [
                {
                    "case_id": "detect_object",
                    "name": "Detect Robot",
                    "prompt": "What is in this image?",
                    "expected": {"type": "exact", "text": "robot"}
                }
            ]
        }
    },
    headers=headers
)
# Publish
client.put(f"/v1/workspaces/{ws_id}/promptpacks/vision-qa/1.0.0/publish", headers=headers)
```

### F. Create a Pipeline
Define the device matrix and quality gates for your regression tests.

```python
resp = client.post(
    f"/v1/workspaces/{ws_id}/pipelines",
    json={
        "name": "Production Gate - RB5",
        "promptpack_ref": {"promptpack_id": "vision-qa", "version": "1.0.0"},
        "device_matrix": [{"name": "RB5", "enabled": True}],
        "gates": [
            {"metric": "inference_time_ms", "operator": "lte", "threshold": 150.0}
        ]
    },
    headers=headers
)
pipeline_id = resp.json()["id"]
```

### G. Trigger a Test Run
Upload your model artifact and trigger a pipeline run.

```python
# Upload model
with open("model.pt", "rb") as f:
    resp = client.post(f"/v1/workspaces/{ws_id}/artifacts", files={"file": f}, data={"kind": "torchscript"}, headers=headers)
artifact_id = resp.json()["id"]

# Trigger run
resp = client.post(
    f"/v1/workspaces/{ws_id}/runs",
    json={"pipeline_id": pipeline_id, "model_artifact_id": artifact_id},
    headers=headers
)
```

## 3. Running the Example Script

You can run the full automated flow using:

```bash
python examples/quickstart.py
```

This script will:
1. Generate a random user.
2. Perform all steps above.
3. Poll for the final run status.
4. Provide a URL to view the results.

## 4. Troubleshooting

- **500 Internal Server Error**: Check the API logs. Common causes include invalid `EDGEGENAI_MASTER_KEY` encoding or missing database migrations.
- **422 Unprocessable Entity**: The request body does not match the schema. Refer to the Swagger docs at `/docs`.
- **424 Failed Dependency**: The PromptPack referenced in the pipeline is not published.
