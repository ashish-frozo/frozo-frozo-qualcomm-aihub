PRD: Edge GenAI Regression Gates for Snapdragon (AI Hub–Orchestrated)

Purpose: This PRD is written for a coding agent. It is intentionally strict, deterministic, and capability-driven (no guessing AI Hub fields). It includes the ProbeSuite and model packaging requirements derived from the provided AI Hub Workbench pages.

⸻

0) Document control
	•	Product (working): EdgeGenAI Gates
	•	PRD version: 0.3 (includes ProbeSuite + packaging validators + adapter + deterministic gating + limits + threat model)
	•	Owner: Ashish
	•	Target users: Robotics startups + IoT OEMs shipping GenAI on edge
	•	Execution provider: Qualcomm AI Hub Workbench (via qai_hub SDK/CLI)

⸻

1) Problem statement

Edge GenAI teams routinely introduce regressions when changing:
	•	model weights/quantization
	•	runtime/SDK/firmware
	•	prompt templates/decoding params
	•	device target matrix

Regressions appear on real devices as:
	•	slower responsiveness (TTFT-like)
	•	lower throughput (tokens/sec-like)
	•	higher memory usage / OOM
	•	correctness drift on fixed prompt suites
	•	unstable outputs across repeated runs (non-determinism)

They need a repeatable system that:
	1.	runs tests on real target devices
	2.	enforces CI pass/fail gates deterministically
	3.	produces auditable evidence bundles for release sign-off

⸻

2) Goals and non-goals

Goals (MVP)
	1.	Execute tests on real Snapdragon devices through AI Hub using a customer-provided token (Option A).
	2.	Provide deterministic CI gating:
	•	warmup excluded
	•	median-of-N repeats
	•	flake detection leading to controlled error outcomes
	3.	Support PromptPacks + correctness + determinism scoring.
	4.	Produce signed evidence bundles with SHA-256 artifact hashes.
	5.	Implement ProbeSuite to discover:
	•	available capabilities
	•	stable metric mappings (JSON paths)
	•	supported model packaging formats (plain, ONNX external, AIMET)

Non-goals (MVP)
	•	Any “certification” branding/claims.
	•	Thermal/power/soak tests unless proven stable via probes.
	•	On-prem runner (must be runner-ready by design only).
	•	Full MLOps/training/deployment.

⸻

3) Personas
	•	P1: Robotics ML Engineer: wants regressions blocked before integration.
	•	P2: IoT OEM AI Lead: wants evidence bundle; later may require on-prem runner.
	•	P3: DevOps/Release Engineer: wants stable CI checks and time-bounded runs.
	•	P4: Security/IT: wants secret safety, auditability, isolation.

⸻

4) Definitions
	•	Workspace: tenant boundary.
	•	Pipeline: configuration (devices, PromptPack, gates, run policy).
	•	Run: execution instance of a pipeline.
	•	PromptPack: versioned JSON defining prompts, decoding params, expected checks.
	•	Capability: proven available feature of AI Hub within a workspace (by probe).
	•	Metric mapping: JSONPath mapping from raw AI Hub payloads to normalized metrics.
	•	Evidence bundle: signed zip containing report + raw payloads + hashes.

⸻

5) Hard limits (MVP; enforce server-side)
	•	Model upload size ≤ 500 MB
	•	PromptPack cases ≤ 50
	•	Devices/run ≤ 5
	•	Warmup runs/device = 1
	•	Measurement repeats N default 3, max 5
	•	max_new_tokens default 128, max 256
	•	Run timeout default 20 min, max 45 min
	•	Workspace concurrency: 1 active run
	•	Artifact retention: 30 days

If exceeded: return error_code=LIMIT_EXCEEDED + details.

⸻

6) User stories (acceptance criteria)

US1: Connect AI Hub token
	•	Admin pastes token, tests connection, saves.
	•	Token encrypted at rest, never logged.
	•	Stores only token_last4 for UX.

Accept: POST /integrations/qaihub/connect succeeds and test works.

US2: Probe workspace capabilities
	•	Admin triggers ProbeSuite.
	•	System runs probes, stores raw probe artifacts, generates workspace_capabilities.json and metric_mapping.json.

Accept: GET /capabilities returns populated capabilities + mapping artifact.

US3: Create pipeline and run manually
	•	Admin selects devices, PromptPack, gates, run policy.
	•	Triggers run; sees pass/fail/error with detailed reasons.

Accept: Run executes deterministically and produces evidence bundle.

US4: CI gating
	•	GitHub Action triggers run and blocks PR on failure.

Accept: Action exits non-zero on failed/error, includes report URL.

US5: Evidence bundle verification
	•	User downloads bundle; verifies signature offline; hashes match.

Accept: Signature verifies against published public key; hash list matches files.

⸻

7) Functional requirements

FR1 — Auth, RBAC, multi-tenancy

Roles:
	•	Owner: all
	•	Admin: manage integrations/pipelines/runs
	•	Viewer: read-only runs/reports

Isolation:
	•	All resources must include workspace_id.
	•	API must enforce workspace membership for every resource.

FR2 — AI Hub integration (Option A)

Integration supports:
	•	connect, test, rotate, disable
	•	store token using envelope encryption
	•	decrypt token only in worker process memory for the duration of a run

FR3 — PromptPack CRUD (immutable versions)
	•	Upload PromptPack JSON.
	•	Validate schema.
	•	Store by {promptpack_id, version}.
	•	Published PromptPacks are immutable.

FR4 — Pipeline CRUD

Pipeline stores:
	•	device matrix
	•	PromptPack ref
	•	gates
	•	run policy:
	•	warmup count (fixed=1 MVP)
	•	repeats N
	•	flake thresholds
	•	timeout
	•	concurrency behavior (reject or queue; MVP: queue)

FR5 — Run orchestration and state machine

States:
	•	queued → preparing → submitting → running → collecting → evaluating → reporting → passed|failed|error

Retry/backoff:
	•	poll errors: exponential backoff, max 10 minutes total
	•	submission errors: 1 retry if network-related, else error

FR6 — Deterministic gating policy

Mandatory (see §12):
	•	warmup excluded
	•	N repeats; median aggregation
	•	flake detection converts required-gate volatility into controlled error

FR7 — Evidence bundle
	•	Build signed .zip per run with raw artifacts and mapping.
	•	Hash and store content-addressed artifacts.

FR8 — Observability + audit logs

Audit events:
	•	integration.connected/rotated/tested/disabled
	•	capabilities.probed
	•	pipeline.created/updated/deleted
	•	run.created/status_changed/bundle_downloaded

⸻

8) AI Hub Workbench model compilation and packaging (normative)

8.1 Supported input formats (from provided pages)

System must support validating and probing these model packaging types:
	1.	PyTorch/TorchScript (probe)
	2.	ONNX single-file
	3.	ONNX with external weights (.onnx + .data) in a directory/zip
	4.	AIMET quantized package: .onnx + .encodings (optional .data) in a directory whose name contains .aimet

8.2 Target runtime outputs (from provided pages)

AI Hub can compile to multiple runtimes (TFLite, QNN variants, ONNX runtime). For MVP probes, support compiling to:
	•	qnn_dlc (recommended first)
	•	tflite (optional second)

Explicit MVP rule: Do not require QNN context binary or model library in MVP. (They are more specialized; context is SoC-specific; model library has ABI considerations.)

8.3 Packaging validators (MVP must implement)

Validator: ONNX external weights package
Input: directory/zip
Rules:
	•	exactly 1 .onnx
	•	exactly 1 .data
	•	reject if more than one .onnx or .data

Best-effort check:
	•	try to confirm ONNX references .data by relative name; if cannot parse, warn but do not block probe.

Fail → error_code=INVALID_MODEL_PACKAGE

Validator: AIMET package
Input: directory/zip
Rules:
	•	directory name contains .aimet (strict for MVP)
	•	exactly 1 .onnx
	•	exactly 1 .encodings
	•	.data optional (0 or 1)
Fail → error_code=INVALID_MODEL_PACKAGE

⸻

9) ProbeSuite (MVP-critical)

9.1 Purpose

ProbeSuite is the only allowed mechanism to:
	•	discover which AI Hub features are available
	•	discover stable metric fields and create metric_mapping.json
	•	confirm model packaging/compile/profile/inference workflows work

9.2 Probe outputs (required)

After a successful probe, system must store:
	•	workspace_capabilities.json (capability list)
	•	metric_mapping.json (metric JSONPaths + stability)
	•	raw probe artifacts:
	•	raw/token_validation.json
	•	raw/device_list.json
	•	raw/compile_job_response.json
	•	raw/profile_result_<device>.json (if available)
	•	raw/inference_outputs_<device>.json (if available)
	•	raw/logs_<device>.* (if available)
	•	raw/onnx_packaging_validation.json
	•	raw/aimet_packaging_validation.json

All artifacts must have SHA-256 hashes and be stored immutably.

9.3 Probe device selection
	•	Choose up to 2 devices from device list:
	•	device_primary
	•	device_secondary (optional)
Store probe_devices.json.

9.4 Probe model fixtures (must exist in repo)

Repo must include probe fixtures:
	•	probe_models/torch/ (tiny model that can be traced)
	•	probe_models/onnx_external/ (directory with .onnx + .data)
	•	probe_models/aimet_quant.aimet/ (directory with .onnx + .encodings [+ optional .data])

9.5 Probe sequence (normative)
	1.	Token validation probe
	2.	Device list probe
	3.	For each packaging type (in order):
	•	validate package
	•	upload model package
	•	submit compile job (target runtime = qnn_dlc for MVP)
	•	submit profile job (if supported)
	•	submit inference outputs job (if supported)
	•	download and store raw payloads

9.6 Capability discovery rules (strict)

workspace_capabilities must include at least these capability IDs:
	•	TOKEN_VALIDATION
	•	DEVICE_LIST
	•	TARGET_QNN_DLC (or TARGET_TFLITE if you choose that first)
	•	MODEL_ONNX_EXTERNAL_DATA
	•	MODEL_AIMET_ONNX_ENCODINGS
	•	PROFILE_METRICS (only if profile payload successfully downloaded)
	•	INFERENCE_OUTPUTS (only if output payload successfully downloaded)
	•	JOB_LOGS (only if logs successfully fetched and consistent)

9.7 Stability rule for metrics

A metric can be marked stable only if:
	•	it is present in profile payloads across ≥2 probe runs (same mapping path)
	•	units are consistent
Otherwise mark unstable or unavailable.

⸻

10) Capability Contract (strict, no guessing)

10.1 Capability schema

{
  "capability_id": "string",
  "available": true,
  "stability": "stable | unstable | unknown",
  "probe_method": "string",
  "response_shape_artifact_id": "string",
  "notes": "string"
}

10.2 Metric mapping schema (normative)

{
  "mapping_version": "1.0",
  "derived_from_artifacts": ["artifact_id_1", "artifact_id_2"],
  "metrics": {
    "peak_ram_mb": {
      "json_path": "$.path.to.value",
      "unit": "MB",
      "stability": "stable"
    },
    "ttft_ms": {
      "json_path": null,
      "unit": "ms",
      "stability": "unavailable"
    }
  }
}

Rule: json_path MUST NOT be filled unless derived from probe payloads.

⸻

11) InferenceAdapterV1 (GenAI I/O contract)

11.1 Adapter interface (normative)

InferenceAdapter must implement:
	•	supports(model_metadata) -> bool
	•	prepare_inputs(prompt_case, defaults) -> AdapterInputs
	•	parse_outputs(raw_outputs) -> AdapterOutputs
	•	canonicalize(text) -> string

Optional:
	•	extract_token_timestamps(raw_outputs, raw_logs) -> array|null

11.2 TextGenAdapterV1 (MVP)

Inputs:

{
  "prompt": "string",
  "generation_params": {
    "max_new_tokens": 128,
    "temperature": 0.2,
    "top_p": 0.95,
    "seed": 42
  }
}

Outputs:

{
  "output_text": "string",
  "tokens": null,
  "token_timestamps_ms": null
}

MVP constraint: If token timestamps aren’t available, TTFT/TPS metrics must be unavailable (unless profile payload includes them stably).

⸻

12) PromptPack spec (v1)

12.1 Schema (normative)

{
  "promptpack_id": "string",
  "version": "semver",
  "name": "string",
  "description": "string",
  "tags": ["string"],
  "defaults": {
    "max_new_tokens": 128,
    "temperature": 0.2,
    "top_p": 0.95,
    "seed": 42
  },
  "cases": [
    {
      "case_id": "string",
      "name": "string",
      "prompt": "string",
      "expected": {
        "type": "json_schema | regex | exact | none",
        "schema": {},
        "pattern": "string",
        "text": "string"
      },
      "overrides": {}
    }
  ]
}

12.2 Canonicalization rules (normative)
	•	normalize line endings to LF
	•	trim leading/trailing whitespace
	•	JSON expected:
	•	parse JSON; re-serialize with sorted keys, no whitespace

12.3 Correctness scoring
	•	json_schema: pass=1.0 else 0.0
	•	regex: match=1.0 else 0.0
	•	exact: match=1.0 else 0.0
	•	none: excluded from correctness aggregate

⸻

13) Deterministic gating policy (must be implemented exactly)

13.1 Per-device run sequence
	•	Warmup: execute all cases once; store results; do not gate.
	•	Measurement: execute full PromptPack N times (default=3).

13.2 Aggregation

For each metric per device:
	•	use median over N repeats

Correctness:
	•	per-case score = median of repeat scores (0/1)
	•	aggregate correctness = mean across scorable cases

13.3 Flake detection

Compute dispersion across repeats for each available metric:
	•	throughput dispersion > 15% → flaky
	•	latency dispersion > 20% → flaky

Policy:
	•	Required gate depends on flaky metric → error_code=FLAKY_METRIC
	•	Optional gate depends on flaky metric → gate skipped

13.4 Missing metric behavior
	•	Required + unavailable → error_code=MISSING_REQUIRED_METRIC
	•	Optional + unavailable → gate skipped

⸻

14) Gates config (pipeline)

14.1 Schema

{
  "gates": [
    { "metric": "peak_ram_mb", "op": "<=", "value": 3500, "required": true },
    { "metric": "tokens_per_sec", "op": ">=", "value": 12, "required": false },
    { "metric": "ttft_ms", "op": "<=", "value": 1200, "required": false },
    { "metric": "correctness.aggregate_score", "op": ">=", "value": 0.9, "required": true }
  ],
  "device_overrides": {}
}

14.2 Gate evaluation output (normative)

Each gate evaluation emits:

{
  "gate": "string",
  "device_id": "string",
  "metric_available": true,
  "value": 123.4,
  "result": "pass|fail|skipped",
  "reason": "string|null"
}


⸻

15) Normalized metrics schema (v1)

15.1 Per-device normalized output

{
  "device_id": "string",
  "device_name": "string",
  "metrics": {
    "peak_ram_mb": { "value": 0, "available": false, "source_ref": "artifact_id|null" },
    "ttft_ms": { "value": 0, "available": false, "source_ref": "artifact_id|null" },
    "tokens_per_sec": { "value": 0, "available": false, "source_ref": "artifact_id|null" }
  },
  "correctness": {
    "aggregate_score": 0.0,
    "per_case": [{ "case_id": "string", "score": 0.0, "notes": "string|null" }]
  }
}


⸻

16) Evidence bundle (v1, signed)

16.1 Contents (zip)
	•	summary.json
	•	summary.sig
	•	report.html
	•	artifacts.json
	•	raw/device_list.json
	•	raw/profile_<device>.json (if available)
	•	raw/outputs_<device>.json (if available)
	•	raw/logs_<device>.* (if available)
	•	mapping/metric_mapping.json
	•	capabilities/workspace_capabilities.json

16.2 Hashing rules
	•	SHA-256 for every file in the bundle.
	•	Store hash list in summary.json.
	•	Object storage key must include hash.

16.3 summary.json schema (normative)

{
  "bundle_version": "1.0",
  "workspace_id": "string",
  "pipeline_id": "string",
  "run_id": "string",
  "created_at": "ISO8601",
  "inputs": {
    "model": { "artifact_id": "string", "sha256": "string" },
    "promptpack": { "promptpack_id": "string", "version": "string", "sha256": "string" },
    "devices": [{ "device_id": "string", "device_name": "string" }]
  },
  "capabilities_ref": "artifact_id",
  "metric_mapping_ref": "artifact_id",
  "results": {
    "status": "passed|failed|error",
    "normalized_metrics": [],
    "gates_evaluation": []
  },
  "artifacts": [{ "path": "string", "sha256": "string" }],
  "signing": { "algo": "ed25519", "public_key_id": "string" }
}

16.4 Signing and key rotation
	•	Ed25519 signing
	•	Public keys retrievable via GET /v1/signing-keys/{id}
	•	Keys versioned; never delete old keys

⸻

17) System architecture

17.1 Services
	•	API service: auth, CRUD, run trigger, bundle download
	•	Worker: AI Hub calls, probes, execution, metrics, reports, signing
	•	DB: Postgres
	•	Object storage: S3-compatible
	•	KMS/Secret manager: envelope encryption + signing keys

17.2 Run executor design (runner-ready)
	•	Define an internal job_spec.json that fully describes a run.
	•	Worker executes job_spec.json.
	•	Future runner executes same spec (not implemented).

⸻

18) API endpoints (normative)

Integrations
	•	POST /v1/integrations/qaihub/connect {api_token}
	•	POST /v1/integrations/qaihub/test
	•	POST /v1/integrations/qaihub/rotate {api_token}
	•	POST /v1/integrations/qaihub/disable

Capabilities/Probe
	•	POST /v1/capabilities/probe (Owner/Admin only)
	•	GET /v1/capabilities

PromptPacks
	•	POST /v1/promptpacks
	•	GET /v1/promptpacks
	•	GET /v1/promptpacks/{id}/{version}

Pipelines
	•	POST /v1/pipelines
	•	PUT /v1/pipelines/{id}
	•	GET /v1/pipelines
	•	GET /v1/pipelines/{id}

Artifacts
	•	POST /v1/artifacts (model upload)
	•	GET /v1/artifacts/{id}

Runs
	•	POST /v1/runs {pipeline_id, model_artifact_id, trigger}
	•	GET /v1/runs/{id}
	•	GET /v1/runs/{id}/bundle

CI
	•	POST /v1/ci/github/run (HMAC + timestamp + nonce) → {run_id, status_url}

⸻

19) Data model (normative tables)

integrations
	•	id, workspace_id, provider, status
	•	token_blob (envelope encrypted)
	•	token_last4, created_by, timestamps

workspace_capabilities
	•	workspace_id
	•	capabilities_artifact_id
	•	metric_mapping_artifact_id
	•	probed_at, probe_run_id

promptpacks
	•	workspace_id (or global later)
	•	promptpack_id, version, sha256, json, timestamp

pipelines
	•	id, workspace_id, name
	•	device_matrix_json, promptpack_ref_json
	•	gates_json, run_policy_json
	•	timestamps

runs
	•	id, workspace_id, pipeline_id, trigger, status
	•	normalized_metrics_json, gates_eval_json
	•	bundle_artifact_id
	•	error_code, error_detail
	•	timestamps

artifacts
	•	id, workspace_id, kind, storage_url, sha256, bytes, timestamp

audit_events
	•	id, workspace_id, actor_user_id, event_type, event_json, timestamp

⸻

20) Security and threat model (required)

Threats and mitigations
	1.	Token exfiltration via logs → strict redaction middleware + tests
	2.	Cross-tenant artifact access → auth checks before signed URL issuance
	3.	CI replay → timestamp+nonce+HMAC; reject stale (>5 min)
	4.	SSRF via model URL → disallow arbitrary URLs; only uploaded artifacts
	5.	Worker plaintext token persistence → decrypt in memory only
	6.	Privilege escalation → RBAC enforcement on integration/probe endpoints

Audit:
	•	log integration/probe/run lifecycle events.

⸻

21) Definition of done (MVP)

All must be true:
	1.	Token connect/test/rotate/disable works; token encrypted; no secret logs.
	2.	ProbeSuite runs and produces capability + metric mapping artifacts.
	3.	Packaging validators correctly accept/reject:
	•	ONNX external weights packages
	•	AIMET packages
	4.	Pipeline run executes with deterministic gating rules.
	5.	CI integration blocks PR on fail/error with report link.
	6.	Evidence bundle downloads; signature verifies; hashes match.
	7.	Hard limits enforced.
	8.	Workspace isolation proven by tests (no cross-tenant reads).

⸻

22) Open questions (must remain Unknown until probe proves)
	•	Whether TTFT/tokens/sec are directly exposed or derivable reliably.
	•	Which profile keys exist and units (must be discovered via probes).
	•	Whether job logs are accessible and stable.

Rule: Do not implement TTFT/TPS gating unless ProbeSuite marks them stable.

⸻

23) Repository deliverables required for the coding agent

These must be created in the project repository:

23.1 Schemas
	•	schemas/promptpack.schema.json
	•	schemas/model_metadata.schema.json
	•	schemas/workspace_capabilities.schema.json
	•	schemas/metric_mapping.schema.json

23.2 Probe fixtures
	•	probe_models/torch/...
	•	probe_models/onnx_external/model.onnx + model.data
	•	probe_models/aimet_quant.aimet/model.onnx + model.encodings (+ optional model.data)

23.3 Runbooks/examples
	•	examples/probe_suite_runbook.md
	•	examples/aihub_probe.py (golden script; prints and stores artifacts)
	•	examples/github_action.yml

⸻