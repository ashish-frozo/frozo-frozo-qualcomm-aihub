# Implementation Plan: Edge GenAI Regression Gates for Snapdragon (AI Hub–Orchestrated)

> **PRD Version**: 0.3  
> **Generated**: 2026-01-06  
> **Status**: Awaiting Approval

---

## 1. Executive Summary

This document outlines the implementation plan for the Edge GenAI Regression Gates system as specified in the PRD. The system enables robotics startups and IoT OEMs to run regression tests on real Snapdragon devices through Qualcomm AI Hub, with deterministic CI gating and signed evidence bundles.

---

## 2. Technology Stack

| Component | Technology |
|-----------|------------|
| **Language** | Python 3.11+ |
| **API Framework** | FastAPI with Pydantic v2 |
| **Database** | PostgreSQL 15+ |
| **Object Storage** | S3-compatible (MinIO for local dev) |
| **Task Queue** | Celery with Redis |
| **Authentication** | JWT (RS256) + API Keys |
| **Encryption** | PyNaCl (Ed25519 signing), cryptography (envelope encryption) |
| **AI Hub SDK** | `qai_hub` (Qualcomm AI Hub Python SDK) |
| **Testing** | pytest, pytest-asyncio, pytest-cov |
| **Containerization** | Docker, Docker Compose |

---

## 3. Module/Service Architecture

```
edgegate/
├── alembic/                    # Database migrations
│   ├── env.py
│   └── versions/
├── api/                        # FastAPI application
│   ├── main.py
│   ├── dependencies.py
│   ├── middleware/
│   │   ├── auth.py
│   │   ├── rbac.py
│   │   ├── tenant.py
│   │   └── logging.py         # Redaction middleware
│   ├── routers/
│   │   ├── integrations.py
│   │   ├── capabilities.py
│   │   ├── promptpacks.py
│   │   ├── pipelines.py
│   │   ├── artifacts.py
│   │   ├── runs.py
│   │   ├── ci.py
│   │   └── signing_keys.py
│   └── models/                 # Pydantic request/response models
├── core/
│   ├── config.py              # Settings via pydantic-settings
│   ├── security.py            # Envelope encryption, HMAC, signing
│   ├── hashing.py             # SHA-256 content-addressed storage
│   └── limits.py              # Hard limit enforcement
├── db/
│   ├── session.py             # Database session factory
│   └── models.py              # SQLAlchemy ORM models
├── storage/
│   ├── interface.py           # Abstract storage interface
│   └── s3.py                  # S3-compatible implementation
├── services/
│   ├── integration_service.py
│   ├── capability_service.py
│   ├── promptpack_service.py
│   ├── pipeline_service.py
│   ├── run_service.py
│   ├── artifact_service.py
│   ├── audit_service.py
│   └── signing_service.py
├── workers/
│   ├── celery_app.py
│   ├── tasks/
│   │   ├── probe_task.py      # ProbeSuite execution
│   │   └── run_task.py        # Pipeline run execution
│   └── executor/
│       ├── job_spec.py        # job_spec.json parser
│       ├── run_executor.py    # Main executor (runner-ready design)
│       ├── state_machine.py   # Run state transitions
│       └── gating.py          # Deterministic gate evaluation
├── aihub/
│   ├── client.py              # AI Hub client wrapper
│   ├── adapter.py             # InferenceAdapterV1
│   └── probe_suite.py         # ProbeSuite implementation
├── validators/
│   ├── promptpack.py
│   ├── model_metadata.py
│   ├── onnx_external.py       # ONNX external weights validator
│   └── aimet.py               # AIMET package validator
├── schemas/                   # JSON Schema files (.schema.json)
│   ├── promptpack.schema.json
│   ├── model_metadata.schema.json
│   ├── workspace_capabilities.schema.json
│   └── metric_mapping.schema.json
├── evidence/
│   ├── bundle_builder.py
│   └── report_generator.py
├── probe_models/              # Probe fixture files
│   ├── torch/
│   │   └── tiny_model.pt
│   ├── onnx_external/
│   │   ├── model.onnx
│   │   └── model.data
│   └── aimet_quant.aimet/
│       ├── model.onnx
│       └── model.encodings
├── examples/
│   ├── probe_suite_runbook.md
│   ├── aihub_probe.py
│   └── github_action.yml
└── tests/
    ├── unit/
    ├── integration/
    └── security/
```

---

## 4. Data Model

### 4.1 Tables (per PRD §19)

#### `workspaces`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| name | VARCHAR(255) | |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

#### `users`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| email | VARCHAR(255) | |
| hashed_password | VARCHAR(255) | |
| created_at | TIMESTAMP | |

#### `workspace_memberships`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| workspace_id | UUID | FK→workspaces |
| user_id | UUID | FK→users |
| role | ENUM('owner','admin','viewer') | |
| created_at | TIMESTAMP | |

#### `integrations`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| workspace_id | UUID | FK→workspaces |
| provider | VARCHAR(50) | 'qaihub' |
| status | ENUM('active','disabled') | |
| token_blob | BYTEA | Envelope encrypted |
| token_last4 | VARCHAR(4) | Last 4 chars for UX |
| created_by | UUID | FK→users |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

#### `workspace_capabilities`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| workspace_id | UUID | FK→workspaces, UNIQUE |
| capabilities_artifact_id | UUID | FK→artifacts |
| metric_mapping_artifact_id | UUID | FK→artifacts |
| probed_at | TIMESTAMP | |
| probe_run_id | UUID | Nullable, FK→probe_runs |

#### `promptpacks`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| workspace_id | UUID | FK→workspaces, nullable for global |
| promptpack_id | VARCHAR(255) | Logical ID |
| version | VARCHAR(50) | Semver |
| sha256 | VARCHAR(64) | |
| json_content | JSONB | Full PromptPack JSON |
| published | BOOLEAN | Default false |
| created_at | TIMESTAMP | |
| UNIQUE(workspace_id, promptpack_id, version) | | |

#### `pipelines`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| workspace_id | UUID | FK→workspaces |
| name | VARCHAR(255) | |
| device_matrix_json | JSONB | |
| promptpack_ref_json | JSONB | {promptpack_id, version} |
| gates_json | JSONB | Per PRD §14 |
| run_policy_json | JSONB | {warmup_count, repeats, flake_thresholds, timeout, concurrency} |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

#### `runs`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| workspace_id | UUID | FK→workspaces |
| pipeline_id | UUID | FK→pipelines |
| trigger | VARCHAR(50) | 'manual', 'ci' |
| status | VARCHAR(50) | State machine states |
| model_artifact_id | UUID | FK→artifacts |
| normalized_metrics_json | JSONB | Nullable |
| gates_eval_json | JSONB | Nullable |
| bundle_artifact_id | UUID | FK→artifacts, nullable |
| error_code | VARCHAR(100) | Nullable |
| error_detail | TEXT | Nullable |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

#### `artifacts`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| workspace_id | UUID | FK→workspaces |
| kind | VARCHAR(50) | model, bundle, probe_raw, etc. |
| storage_url | VARCHAR(1000) | S3 key/URL |
| sha256 | VARCHAR(64) | |
| bytes | BIGINT | |
| created_at | TIMESTAMP | |
| expires_at | TIMESTAMP | 30 days retention |

#### `audit_events`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| workspace_id | UUID | FK→workspaces |
| actor_user_id | UUID | FK→users, nullable for system |
| event_type | VARCHAR(100) | |
| event_json | JSONB | |
| timestamp | TIMESTAMP | |

#### `signing_keys`
| Column | Type | Notes |
|--------|------|-------|
| id | VARCHAR(50) | PK (versioned key ID) |
| public_key | BYTEA | Ed25519 public key |
| created_at | TIMESTAMP | |
| revoked_at | TIMESTAMP | Nullable |

#### `ci_nonces`
| Column | Type | Notes |
|--------|------|-------|
| nonce | VARCHAR(64) | PK |
| workspace_id | UUID | FK→workspaces |
| used_at | TIMESTAMP | |
| expires_at | TIMESTAMP | +5 minutes |

---

## 5. Run State Machine (PRD §FR5)

```
States and Transitions:
[*] --> queued
queued --> preparing: worker picks up
preparing --> submitting: resources ready
preparing --> error: preparation failed
submitting --> running: AI Hub job submitted
submitting --> error: submission failed (after 1 retry)
running --> collecting: AI Hub job complete
running --> error: timeout or poll failure (10 min max backoff)
collecting --> evaluating: metrics collected
collecting --> error: collection failed
evaluating --> reporting: gates evaluated
evaluating --> error: FLAKY_METRIC, MISSING_REQUIRED_METRIC
reporting --> passed: all required gates pass
reporting --> failed: any required gate fails
reporting --> error: bundle creation failed
```

---

## 6. Deterministic Gating Algorithm (PRD §13)

```python
def evaluate_run(run_data):
    # 1. Exclude warmup data (warmup_count=1)
    measurement_data = run_data.exclude_warmup()
    
    # 2. For each device:
    for device in devices:
        # 3. For each metric, compute median over N repeats
        for metric in metrics:
            values = measurement_data.get_metric_values(device, metric)
            median = compute_median(values)
            
            # 4. Compute dispersion for flake detection
            dispersion = compute_cv(values)  # coefficient of variation
            if metric.is_throughput and dispersion > 0.15:
                if gate_requires(metric) and gate.required:
                    raise FlakeError("FLAKY_METRIC", metric)
            if metric.is_latency and dispersion > 0.20:
                if gate_requires(metric) and gate.required:
                    raise FlakeError("FLAKY_METRIC", metric)
        
        # 5. Correctness scoring
        for case in promptpack.cases:
            scores = [evaluate_case(case, repeat) for repeat in repeats]
            median_score = compute_median(scores)
        aggregate_correctness = mean(median_scores)
    
    # 6. Evaluate gates
    for gate in gates:
        if not metric_available(gate.metric):
            if gate.required:
                raise MissingMetricError("MISSING_REQUIRED_METRIC")
            else:
                gate.result = "skipped"
                continue
        
        if is_flaky(gate.metric) and not gate.required:
            gate.result = "skipped"
            continue
        
        value = get_median_value(gate.metric)
        gate.result = "pass" if evaluate_op(value, gate.op, gate.value) else "fail"
```

---

## 7. Implementation Phases

### Phase 1: Schemas and Validators
- Create JSON schema files
- Implement validators
- Unit tests for all validators

### Phase 2: Core Backend (Auth/RBAC/Workspaces)
- Database migrations
- User, workspace, membership models
- JWT authentication
- RBAC middleware
- Multi-tenancy enforcement

### Phase 3: Integrations with Envelope Encryption
- Token storage with envelope encryption
- Connect/test/rotate/disable endpoints
- Audit logging
- Token redaction middleware

### Phase 4: ProbeSuite + Capabilities
- AI Hub client wrapper
- Probe sequence implementation
- Capability discovery
- Metric mapping generation
- Probe model fixtures

### Phase 5: PromptPack and Pipeline CRUD
- PromptPack schema validation
- Version immutability
- Pipeline CRUD with gates config
- Run policy validation

### Phase 6: Run Orchestration
- State machine implementation
- Celery worker tasks
- Job spec runner-ready design
- Deterministic gating
- Evidence bundle with Ed25519 signing

### Phase 7: CI Integration
- GitHub endpoint with HMAC+timestamp+nonce
- GitHub Action example
- Anti-replay protection

### Phase 8: Testing and Documentation
- Integration tests
- Security tests
- AI Hub integration test harness
- README with curl examples

---

## 8. Test Plan

### 8.1 Unit Tests
| Area | Test Cases |
|------|------------|
| Schema validation | Valid/invalid PromptPacks, model metadata, capabilities |
| Packaging validators | ONNX external (1 .onnx + 1 .data), AIMET (.aimet dir), rejection cases |
| Hashing/signing | SHA-256 content-addressed, Ed25519 sign/verify |
| Gate evaluation | All ops (<, <=, >, >=, ==), missing metrics, flaky metrics |
| Flake detection | Dispersion calculations, threshold enforcement |
| RBAC | Role hierarchy, permission checks |
| Canonicalization | LF normalization, whitespace trim, JSON sorting |

### 8.2 Integration Tests
| Area | Test Cases |
|------|------------|
| API endpoints | All CRUD operations with real DB |
| Artifact storage | Upload/download with MinIO |
| Run lifecycle | Full state machine traversal |
| Evidence bundle | Zip generation, hash verification |
| Audit logs | Event creation and retrieval |

### 8.3 Security Tests
| Area | Test Cases |
|------|------------|
| Token redaction | Token never in logs, responses, errors |
| Cross-tenant access | Artifact access denied across workspaces |
| CI replay | Stale timestamp rejection, nonce reuse rejection |
| HMAC verification | Invalid signature rejection |

### 8.4 AI Hub Integration Tests (env-gated)
| Area | Test Cases |
|------|------------|
| ProbeSuite execution | Real AI Hub probe with saved artifacts |
| Device list | Fetch and validate device data |
| Compile job | Submit and poll completion |
| Profile job | Extract metrics from real response |

---

## 9. Hard Limits Enforcement (PRD §5)

| Limit | Value | Enforcement Point |
|-------|-------|-------------------|
| Model upload size | <= 500 MB | Artifact upload endpoint |
| PromptPack cases | <= 50 | PromptPack creation/update |
| Devices per run | <= 5 | Pipeline creation, run start |
| Warmup runs | = 1 | Run execution (hardcoded MVP) |
| Measurement repeats | default 3, max 5 | Pipeline run_policy validation |
| max_new_tokens | default 128, max 256 | PromptPack defaults/overrides |
| Run timeout | default 20 min, max 45 min | Run execution with task timeout |
| Workspace concurrency | 1 active run | Run creation check |
| Artifact retention | 30 days | Background cleanup job |

---

## 10. API Endpoints Summary (PRD §18)

| Method | Endpoint | Auth | RBAC |
|--------|----------|------|------|
| POST | `/v1/integrations/qaihub/connect` | JWT | Admin |
| POST | `/v1/integrations/qaihub/test` | JWT | Admin |
| POST | `/v1/integrations/qaihub/rotate` | JWT | Admin |
| POST | `/v1/integrations/qaihub/disable` | JWT | Admin |
| POST | `/v1/capabilities/probe` | JWT | Admin |
| GET | `/v1/capabilities` | JWT | Viewer |
| POST | `/v1/promptpacks` | JWT | Admin |
| GET | `/v1/promptpacks` | JWT | Viewer |
| GET | `/v1/promptpacks/{id}/{version}` | JWT | Viewer |
| POST | `/v1/pipelines` | JWT | Admin |
| PUT | `/v1/pipelines/{id}` | JWT | Admin |
| GET | `/v1/pipelines` | JWT | Viewer |
| GET | `/v1/pipelines/{id}` | JWT | Viewer |
| POST | `/v1/artifacts` | JWT | Admin |
| GET | `/v1/artifacts/{id}` | JWT | Viewer |
| POST | `/v1/runs` | JWT | Admin |
| GET | `/v1/runs/{id}` | JWT | Viewer |
| GET | `/v1/runs/{id}/bundle` | JWT | Viewer |
| POST | `/v1/ci/github/run` | HMAC | N/A |
| GET | `/v1/signing-keys/{id}` | Public | N/A |

---

## 11. Unknowns / Blocking Issues

> **CAUTION**: The following items are marked as **Unknown** per PRD section 22 and must be discovered via ProbeSuite. Implementation must NOT assume these are available.

### 11.1 TTFT/TPS Metrics Availability
- **Status**: Unknown
- **Blocking**: Cannot implement TTFT/TPS gating until ProbeSuite marks them stable
- **Resolution**: ProbeSuite must successfully extract these from profile payloads across 2 or more probe runs

### 11.2 Profile Payload JSON Structure
- **Status**: Unknown
- **Blocking**: Cannot hardcode JSONPath mappings for metrics
- **Resolution**: ProbeSuite will discover and record actual JSONPaths from AI Hub responses

### 11.3 Job Logs Accessibility
- **Status**: Unknown
- **Blocking**: Cannot rely on logs for token timestamp extraction
- **Resolution**: ProbeSuite will test log fetching and mark JOB_LOGS capability accordingly

### 11.4 Exact AI Hub API Response Shapes
- **Status**: Unknown (partially documented in ai-hub-doc.md)
- **Blocking for**: Specific field paths in compile/profile/inference responses
- **Resolution**: Store raw responses during probe; derive mappings from actual data

---

## 12. Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/edgegate

# Object Storage (S3-compatible)
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin
S3_BUCKET_NAME=edgegate-artifacts

# Redis (Celery broker)
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=<generate-256-bit-key>
JWT_ALGORITHM=RS256
JWT_PRIVATE_KEY_PATH=/path/to/private.pem
JWT_PUBLIC_KEY_PATH=/path/to/public.pem

# Signing Keys (Ed25519)
SIGNING_KEY_ID=key-v1
SIGNING_PRIVATE_KEY_PATH=/path/to/ed25519.private

# Envelope Encryption
KMS_MASTER_KEY=<256-bit-key-or-kms-id>

# AI Hub Integration Tests
QAIHUB_API_TOKEN=<your-token>  # Only for integration tests
```

---

## 13. Deliverables Checklist

- [ ] `schemas/promptpack.schema.json`
- [ ] `schemas/model_metadata.schema.json`
- [ ] `schemas/workspace_capabilities.schema.json`
- [ ] `schemas/metric_mapping.schema.json`
- [ ] `probe_models/torch/tiny_model.pt`
- [ ] `probe_models/onnx_external/model.onnx`
- [ ] `probe_models/onnx_external/model.data`
- [ ] `probe_models/aimet_quant.aimet/model.onnx`
- [ ] `probe_models/aimet_quant.aimet/model.encodings`
- [ ] `examples/probe_suite_runbook.md`
- [ ] `examples/aihub_probe.py`
- [ ] `examples/github_action.yml`
- [ ] `README.md` with curl examples
- [ ] Unit test suite (schemas, validators, gating, RBAC)
- [ ] Integration test suite (API, DB, storage)
- [ ] Security test suite (token redaction, cross-tenant, replay)
- [ ] AI Hub integration test harness

---

## 14. Verification Plan

### 14.1 Automated Tests
```bash
# Run all unit tests
pytest tests/unit -v --cov=edgegate

# Run integration tests (requires local containers)
docker-compose up -d postgres redis minio
pytest tests/integration -v

# Run security tests
pytest tests/security -v

# Run AI Hub integration tests (requires QAIHUB_API_TOKEN)
QAIHUB_API_TOKEN=xxx pytest tests/integration/test_aihub.py -v
```

### 14.2 Manual Verification
1. Deploy locally with Docker Compose
2. Create workspace and user
3. Connect AI Hub token
4. Run ProbeSuite
5. Create PromptPack and Pipeline
6. Trigger manual run
7. Download and verify evidence bundle signature
8. Test CI endpoint with sample GitHub webhook

---

## 15. Notes for Implementation

1. **No mock AI Hub responses**: Unit tests use real saved probe artifacts from `examples/` (redacted but structurally real).

2. **Capability-driven design**: All metric JSONPaths must be derived from ProbeSuite, never hardcoded.

3. **Envelope encryption**: Use AWS KMS pattern - generate DEK, encrypt with KEK, store `{encrypted_dek, ciphertext}`.

4. **Content-addressed storage**: Artifact keys include SHA-256: `artifacts/{sha256}/{original_name}`.

5. **Ed25519 signing**: Sign `summary.json` with private key; include public key ID for verification.

6. **Runner-ready design**: Worker uses `job_spec.json` that future on-prem runners can execute.
