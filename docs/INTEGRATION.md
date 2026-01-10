# EdgeGate CI/CD Integration Guide

Integrate EdgeGate into your GitHub Actions workflow to automatically test AI model performance on Snapdragon hardware.

## Quick Start

### 1. Create EdgeGate Account

1. Go to [EdgeGate Dashboard](https://edgegate-web.railway.app)
2. Register and create a workspace
3. Note your **Workspace ID** from Settings

### 2. Generate API Secret

1. Go to **Settings → Integrations** in your workspace
2. Click **Generate CI Secret**
3. Copy the secret (shown once only)

### 3. Upload Your Model

1. Go to **Artifacts → Upload Model**
2. Upload your ONNX model
3. Note the **Model Artifact ID**

### 4. Create a Pipeline

1. Go to **Pipelines → Create Pipeline**
2. Select target devices (e.g., Snapdragon 8 Gen 3)
3. Define quality gates:
   - Inference time ≤ 50ms
   - Memory ≤ 500MB
   - NPU utilization ≥ 80%
4. Note the **Pipeline ID**

### 5. Add GitHub Secrets

Add to your repository's **Settings → Secrets → Actions**:

| Secret | Value |
|--------|-------|
| `EDGEGATE_WORKSPACE_ID` | Your workspace UUID |
| `EDGEGATE_API_SECRET` | The CI secret from step 2 |

### 6. Add Workflow

Create `.github/workflows/edgegate.yml`:

```yaml
name: EdgeGate AI Tests

on:
  pull_request:
    branches: [main]
    paths:
      - 'models/**'

jobs:
  performance-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Trigger EdgeGate Run
        env:
          WORKSPACE_ID: ${{ secrets.EDGEGATE_WORKSPACE_ID }}
          API_SECRET: ${{ secrets.EDGEGATE_API_SECRET }}
          API_URL: https://edgegate-api.railway.app
        run: |
          # Your pipeline and model IDs
          PIPELINE_ID="your-pipeline-uuid"
          MODEL_ID="your-model-artifact-uuid"
          
          # Generate signature
          TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
          NONCE=$(uuidgen)
          BODY='{"pipeline_id":"'${PIPELINE_ID}'","model_artifact_id":"'${MODEL_ID}'","commit_sha":"${{ github.sha }}"}'
          PAYLOAD=$(printf "%s\n%s\n%s" "${TIMESTAMP}" "${NONCE}" "${BODY}")
          SIGNATURE=$(echo -n "${PAYLOAD}" | openssl dgst -sha256 -hmac "${API_SECRET}" | awk '{print $2}')
          
          # Trigger run
          curl -X POST "${API_URL}/v1/ci/github/run" \
            -H "Content-Type: application/json" \
            -H "X-EdgeGate-Workspace: ${WORKSPACE_ID}" \
            -H "X-EdgeGate-Timestamp: ${TIMESTAMP}" \
            -H "X-EdgeGate-Nonce: ${NONCE}" \
            -H "X-EdgeGate-Signature: ${SIGNATURE}" \
            -d "${BODY}"
```

## API Reference

### POST /v1/ci/github/run

Trigger a performance test run.

**Headers:**
| Header | Description |
|--------|-------------|
| `X-EdgeGate-Workspace` | Workspace UUID |
| `X-EdgeGate-Timestamp` | ISO8601 timestamp |
| `X-EdgeGate-Nonce` | Unique request ID |
| `X-EdgeGate-Signature` | HMAC-SHA256 signature |

**Body:**
```json
{
  "pipeline_id": "uuid",
  "model_artifact_id": "uuid",
  "commit_sha": "abc123",
  "branch": "feature/x",
  "pull_request": 42
}
```

**Response (202):**
```json
{
  "run_id": "uuid",
  "status": "queued",
  "pipeline_id": "uuid",
  "message": "Run queued successfully"
}
```

### GET /v1/ci/status

Verify CI authentication is working.

**Response:**
```json
{
  "status": "ok",
  "workspace_id": "uuid",
  "message": "CI authentication successful"
}
```

## Signature Generation

```bash
# Payload format
PAYLOAD="${TIMESTAMP}\n${NONCE}\n${BODY}"

# Compute HMAC-SHA256
SIGNATURE=$(echo -n "${PAYLOAD}" | openssl dgst -sha256 -hmac "${SECRET}" | awk '{print $2}')
```

## Support

- 📧 Email: support@edgegate.io
- 📖 Docs: https://docs.edgegate.io
- 🐛 Issues: https://github.com/edgegate/edgegate/issues
