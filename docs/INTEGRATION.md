# EdgeGate CI/CD Integration Guide

Integrate EdgeGate into your GitHub Actions workflow to automatically test AI model performance on Qualcomm Snapdragon hardware.

## Quick Start (5 Minutes)

### 1. Get Your Credentials

1. Log in to [EdgeGate Dashboard](https://frozo-frozo-qualcomm-aihub-production.up.railway.app)
2. Open your Workspace → **Settings** → **Integrations**
3. Click **Generate CI Secret** and copy the secret
4. Note your **Workspace ID** from the URL or Settings

### 2. Add GitHub Secrets

Go to your repository: **Settings → Secrets and variables → Actions**

| Secret | Description |
|--------|-------------|
| `EDGEGATE_WORKSPACE_ID` | Your workspace UUID |
| `EDGEGATE_API_SECRET` | The CI secret you generated |
| `EDGEGATE_PIPELINE_ID` | *(Optional)* Pipeline to run |
| `EDGEGATE_MODEL_ARTIFACT_ID` | *(Optional)* Model to test |

### 3. Add the Workflow

Create `.github/workflows/edgegate.yml`:

```yaml
name: EdgeGate AI Test

on:
  pull_request:
    branches: [main]
  workflow_dispatch:

env:
  EDGEGATE_API_URL: https://frozo-frozo-qualcomm-aihub-production.up.railway.app

jobs:
  edgegate-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: EdgeGate Authentication Test
        shell: bash
        env:
          WORKSPACE_ID: ${{ secrets.EDGEGATE_WORKSPACE_ID }}
          API_SECRET: ${{ secrets.EDGEGATE_API_SECRET }}
        run: |
          TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
          NONCE=$(cat /proc/sys/kernel/random/uuid)
          MESSAGE="$TIMESTAMP"$'\n'"$NONCE"$'\n'
          SIGNATURE=$(echo -n "$MESSAGE" | openssl dgst -sha256 -hmac "$API_SECRET" | awk '{print $2}')
          
          curl -s "${{ env.EDGEGATE_API_URL }}/v1/ci/status" \
            -H "X-EdgeGate-Workspace: $WORKSPACE_ID" \
            -H "X-EdgeGate-Timestamp: $TIMESTAMP" \
            -H "X-EdgeGate-Nonce: $NONCE" \
            -H "X-EdgeGate-Signature: $SIGNATURE"
```

### 4. Create a PR

The workflow runs automatically on every PR. You'll see:
- ✅ Authentication status
- 📊 Performance test results (if pipeline configured)

---

## Full Integration

For complete AI performance testing on PRs:

### Step 1: Create a Pipeline

1. Go to **Pipelines → Create Pipeline**
2. Select target devices (e.g., Snapdragon 8 Gen 3)
3. Define quality gates:
   - Inference time ≤ 50ms
   - Memory usage ≤ 500MB  
   - NPU utilization ≥ 80%
4. Copy the **Pipeline ID**

### Step 2: Upload Your Model

1. Go to **Artifacts → Upload Model**
2. Upload your ONNX/TFLite model
3. Copy the **Model Artifact ID**

### Step 3: Add Pipeline Secrets

Add to your repository secrets:

| Secret | Value |
|--------|-------|
| `EDGEGATE_PIPELINE_ID` | Pipeline UUID |
| `EDGEGATE_MODEL_ARTIFACT_ID` | Model Artifact UUID |

Now every PR will trigger full on-device AI tests!

---

## API Reference

### Authentication

All CI requests require HMAC-SHA256 authentication.

**Headers:**
| Header | Description |
|--------|-------------|
| `X-EdgeGate-Workspace` | Workspace UUID |
| `X-EdgeGate-Timestamp` | ISO8601 timestamp (e.g., `2026-01-11T12:00:00Z`) |
| `X-EdgeGate-Nonce` | Unique request ID (UUID) |
| `X-EdgeGate-Signature` | HMAC-SHA256 signature |

**Signature Computation:**
```bash
MESSAGE="${TIMESTAMP}\n${NONCE}\n${BODY}"
SIGNATURE=$(echo -n "$MESSAGE" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')
```

### Endpoints

#### GET /v1/ci/status

Test CI authentication.

**Response (200):**
```json
{
  "status": "ok",
  "workspace_id": "uuid",
  "message": "CI authentication successful"
}
```

#### POST /v1/ci/github/run

Trigger a performance test run.

**Request Body:**
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

---

## Troubleshooting

### "Invalid signature" Error

1. Verify `EDGEGATE_API_SECRET` is correct (43 characters)
2. Check timestamp is current (±5 minutes tolerance)
3. Ensure message format matches: `timestamp\nnonce\nbody`

### "Nonce already used" Error

Each nonce can only be used once. The workflow generates unique nonces automatically.

### Pipeline/Model Not Found

Verify the UUIDs are correct and belong to your workspace.

---

## Support

- 📖 Docs: [EdgeGate Documentation](https://frozo-frozo-qualcomm-aihub-production.up.railway.app/docs)
- 🐛 Issues: [GitHub Issues](https://github.com/ashish-frozo/frozo-frozo-qualcomm-aihub/issues)
