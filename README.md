# EdgeGate - Edge GenAI Regression Gates for Snapdragon

EdgeGate enables robotics startups and IoT OEMs to run regression tests on real Snapdragon devices through Qualcomm AI Hub, with deterministic CI gating and signed evidence bundles.

## Features

- **Multi-tenant workspaces** with RBAC (Owner, Admin, Viewer)
- **AI Hub integration** with envelope encryption for token storage
- **ProbeSuite** for capability discovery and metric mapping
- **PromptPack** versioned test suites with correctness validation
- **Deterministic gating** with warmup exclusion, median-of-N, and flake detection
- **Signed evidence bundles** with SHA-256 hashes and Ed25519 signatures
- **CI integration** with HMAC anti-replay protection

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- (Optional) Qualcomm AI Hub API token for real device testing

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repo-url>
   cd frozo-qualcomm-aihub
   ```

2. **Start infrastructure services**
   ```bash
   docker-compose up -d
   ```

3. **Create virtual environment and install dependencies**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```

4. **Copy environment configuration**
   ```bash
   cp .env.example .env
   # Edit .env and set EDGEGENAI_MASTER_KEY
   ```

5. **Generate probe model fixtures**
   ```bash
   python -m edgegate.probe_models.torch.export_torchscript
   python -m edgegate.probe_models.onnx_external.generate_onnx_external
   ```

6. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

7. **Start the API server**
   ```bash
   uvicorn edgegate.api.main:app --reload
   ```

## Running Tests

### Unit Tests
```bash
pytest tests/unit -v
```

### Integration Tests (requires Docker services)
```bash
docker-compose up -d
pytest tests/integration -v
```

### AI Hub Integration Tests
These tests require a valid AI Hub token:
```bash
QAIHUB_API_TOKEN=your_token pytest tests/integration/test_aihub.py -v
```

Without the token, these tests are automatically skipped.

## API Documentation

Once the server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
edgegate/
├── api/              # FastAPI application
├── core/             # Configuration, security, utilities
├── db/               # Database models and sessions
├── services/         # Business logic services
├── validators/       # Schema and package validators
├── workers/          # Celery tasks and executor
├── aihub/            # AI Hub client integration
├── evidence/         # Evidence bundle generation
└── probe_models/     # Probe model fixtures
    ├── torch/        # TorchScript probe model
    ├── onnx_external/# ONNX with external weights
    └── aimet_quant.aimet/  # AIMET fixture (requires real data)
```

## Hard Limits (from PRD)

| Limit | Value |
|-------|-------|
| Model upload size | ≤ 500 MB |
| PromptPack cases | ≤ 50 |
| Devices per run | ≤ 5 |
| Measurement repeats | default 3, max 5 |
| max_new_tokens | default 128, max 256 |
| Run timeout | default 20 min, max 45 min |
| Workspace concurrency | 1 active run |
| Artifact retention | 30 days |

## Known Unknowns

Per PRD §22, the following are unknown until ProbeSuite discovers them:

- Whether TTFT/tokens/sec are directly exposed or derivable
- Which profile keys exist and their units
- Whether job logs are accessible and stable

**Do not implement TTFT/TPS gating unless ProbeSuite marks them stable.**

## Usage Examples

### 1. Authentication
```bash
# Get access token
curl -X POST "http://localhost:8000/v1/auth/token" \
  -d "username=owner@example.com&password=password"
```

### 2. Run Capability Discovery
```bash
curl -X POST "http://localhost:8000/v1/workspaces/{ws_id}/capabilities/probe" \
  -H "Authorization: Bearer {token}"
```

### 3. Create a PromptPack
```bash
curl -X POST "http://localhost:8000/v1/workspaces/{ws_id}/promptpacks" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "promptpack_id": "chat-v1",
    "version": "1.0.0",
    "content": {
      "cases": [{"case_id": "hello", "input": "Hi", "expected": {"type": "exact", "value": "Hello"}}]
    }
  }'
```

### 4. Trigger a CI Run
```bash
# Requires HMAC headers (see edgegate/api/ci_auth.py)
curl -X POST "http://localhost:8000/v1/ci/github/run" \
  -H "X-EdgeGate-Workspace: {ws_id}" \
  -H "X-EdgeGate-Timestamp: {iso_ts}" \
  -H "X-EdgeGate-Nonce: {nonce}" \
  -H "X-EdgeGate-Signature: {hmac}" \
  -d '{"pipeline_id": "{pipe_id}", "model_artifact_id": "{art_id}"}'
```

## License

MIT
