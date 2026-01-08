"""
Celery tasks for run orchestration.

Implements the run execution pipeline:
1. PREPARING: Validate inputs, build job_spec
2. SUBMITTING: Submit to AI Hub
3. RUNNING: Poll for completion
4. COLLECTING: Download results
5. EVALUATING: Aggregate metrics, evaluate gates
6. REPORTING: Build evidence bundle
7. PASSED/FAILED/ERROR: Terminal states
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from celery import Celery, chain
from celery.utils.log import get_task_logger

from edgegate.core import get_settings
from edgegate.db import Run, RunStatus, Artifact, ArtifactKind, Pipeline, PromptPack, Integration, IntegrationProvider, IntegrationStatus
from edgegate.core.security import LocalKeyManagementService, envelope_decrypt
from edgegate.services.evidence import EvidenceBundleBuilder
from edgegate.aihub.client import QAIHubClient, ProfileResult, JobStatus
import asyncio
import os
import tempfile
import boto3


# Initialize Celery with lazy configuration
# We don't pass broker/backend here - they'll be configured below
celery_app = Celery("edgegate")


def configure_celery():
    """Configure Celery with settings from environment."""
    settings = get_settings()
    celery_app.conf.update(
        broker_url=settings.celery_broker_url,
        result_backend=settings.celery_result_backend,
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_time_limit=3600,  # 1 hour max
        worker_prefetch_multiplier=1,  # Fair scheduling
    )
    return settings


# Configure Celery immediately (but after the app is created)
settings = configure_celery()

logger = get_task_logger(__name__)

# Sync Database for Celery Tasks
sync_engine = create_engine(settings.database_url_sync)
SyncSession = sessionmaker(bind=sync_engine)


# ============================================================================
# Database Helpers
# ============================================================================


def update_run_sync(
    run_id: str,
    status: Optional[RunStatus] = None,
    metrics: Optional[Dict[str, Any]] = None,
    gates_eval: Optional[Dict[str, Any]] = None,
    error_code: Optional[str] = None,
    error_detail: Optional[str] = None,
) -> None:
    """Update run record in database using sync session."""
    try:
        with SyncSession() as session:
            stmt = select(Run).where(Run.id == UUID(run_id))
            run = session.execute(stmt).scalar_one_or_none()
            if not run:
                return

            if status:
                run.status = status
            if metrics:
                run.normalized_metrics_json = metrics
            if gates_eval:
                run.gates_eval_json = gates_eval
            if error_code:
                run.error_code = error_code
            if error_detail:
                run.error_detail = error_detail
            
            run.updated_at = datetime.now(timezone.utc)
            session.commit()
    except Exception as e:
        logger.error(f"Failed to update run {run_id} in DB: {e}")


def get_aihub_token_for_workspace(workspace_id: str) -> Optional[str]:
    """Get the AI Hub API token for a workspace from encrypted credentials.
    
    Falls back to the global QAIHUB_API_TOKEN setting if no workspace credential is found.
    """
    try:
        with SyncSession() as session:
            # First try to get workspace-specific credential
            stmt = select(Integration).where(
                Integration.workspace_id == UUID(workspace_id),
                Integration.provider == IntegrationProvider.QAIHUB,
                Integration.status == IntegrationStatus.ACTIVE,
            )
            integration = session.execute(stmt).scalar_one_or_none()
            
            if integration and integration.token_blob:
                # Decrypt the token
                kms = LocalKeyManagementService(
                    master_key_b64=settings.edgegenai_master_key,
                    signing_keys_path=settings.signing_keys_dir,
                )
                decrypted = envelope_decrypt(integration.token_blob, kms)
                return decrypted.decode()
            
            # Fall back to global setting
            return settings.qaihub_api_token
    except Exception as e:
        logger.warning(f"Failed to get AI Hub token for workspace {workspace_id}: {e}")
        return settings.qaihub_api_token


def get_run_with_pipeline(run_id: str) -> Optional[Dict[str, Any]]:
    """Get run details with pipeline configuration from database."""
    try:
        with SyncSession() as session:
            stmt = select(Run).where(Run.id == UUID(run_id))
            run = session.execute(stmt).scalar_one_or_none()
            
            if not run:
                return None
            
            # Get pipeline
            pipeline_stmt = select(Pipeline).where(Pipeline.id == run.pipeline_id)
            pipeline = session.execute(pipeline_stmt).scalar_one_or_none()
            
            # Get model artifact if exists
            model_artifact = None
            if run.model_artifact_id:
                artifact_stmt = select(Artifact).where(Artifact.id == run.model_artifact_id)
                model_artifact = session.execute(artifact_stmt).scalar_one_or_none()
            
            return {
                "run_id": str(run.id),
                "workspace_id": str(run.workspace_id),
                "pipeline_id": str(run.pipeline_id),
                "pipeline_config": {
                    "device_matrix": pipeline.device_matrix_json if pipeline else [],
                    "promptpack_ref": pipeline.promptpack_ref_json if pipeline else {},
                    "gates": pipeline.gates_json if pipeline else [],
                    "run_policy": pipeline.run_policy_json if pipeline else {},
                },
                "model_artifact_path": model_artifact.storage_url if model_artifact else None,
                "model_artifact_kind": model_artifact.kind.value if model_artifact else None,
                "model_artifact_filename": model_artifact.original_filename if model_artifact else None,
            }
    except Exception as e:
        logger.error(f"Failed to get run {run_id} with pipeline: {e}")
        return None


def create_aihub_client(workspace_id: str) -> Optional[QAIHubClient]:
    """Create a QAIHubClient for the given workspace."""
    token = get_aihub_token_for_workspace(workspace_id)
    if not token:
        logger.error(f"No AI Hub token found for workspace {workspace_id}")
        return None
    return QAIHubClient(api_token=token)


def run_async(coro):
    """Run an async coroutine in a sync context."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def download_artifact(storage_url: str, filename: str) -> str:
    """Download artifact to a temporary file with the correct extension."""
    settings = get_settings()
    
    # Handle local file URLs
    if storage_url.startswith("file://"):
        local_path = storage_url.replace("file://", "")
        if os.path.exists(local_path):
            return local_path
        # If file doesn't exist at the absolute path, try relative to current dir
        # (though storage_url should be absolute)
        return local_path
    
    # Parse s3://bucket/key
    if not storage_url.startswith("s3://"):
        return storage_url
        
    parts = storage_url.replace("s3://", "").split("/", 1)
    if len(parts) < 2:
        raise ValueError(f"Invalid S3 URL: {storage_url}")
        
    bucket = parts[0]
    key = parts[1]
    
    # Get extension from filename
    ext = os.path.splitext(filename)[1]
    
    # Create temp file
    fd, path = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    
    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url or None,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            region_name=settings.s3_region,
        )
        
        logger.info(f"Downloading artifact from {storage_url} to {path}")
        s3.download_file(bucket, key, path)
        return path
    except Exception as e:
        if os.path.exists(path):
            os.remove(path)
        logger.error(f"Failed to download artifact from S3: {e}")
        raise


# ============================================================================
# Job Spec
# ============================================================================


def build_job_spec(
    run_id: str,
    workspace_id: str,
    pipeline_config: Dict[str, Any],
    model_artifact_url: str,
    promptpack_content: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build the job specification for AI Hub execution.
    
    Args:
        run_id: Run UUID string.
        workspace_id: Workspace UUID string.
        pipeline_config: Pipeline configuration.
        model_artifact_url: URL to model artifact.
        promptpack_content: PromptPack JSON content.
        
    Returns:
        job_spec dictionary.
    """
    run_policy = pipeline_config.get("run_policy", {})
    
    return {
        "version": "1.0",
        "run_id": run_id,
        "workspace_id": workspace_id,
        "model": {
            "artifact_url": model_artifact_url,
        },
        "devices": pipeline_config.get("device_matrix", []),
        "promptpack": promptpack_content,
        "run_policy": {
            "warmup_runs": run_policy.get("warmup_runs", 1),
            "measurement_repeats": run_policy.get("measurement_repeats", 3),
            "max_new_tokens": run_policy.get("max_new_tokens", 128),
            "timeout_minutes": run_policy.get("timeout_minutes", 20),
        },
        "gates": pipeline_config.get("gates", []),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================================
# Celery Tasks
# ============================================================================


@celery_app.task(bind=True, name="edgegate.tasks.prepare_run")
def prepare_run(
    self,
    run_id: str,
    workspace_id: str,
) -> Dict[str, Any]:
    """
    QUEUED → PREPARING: Validate inputs and build job_spec.
    
    Fetches run and pipeline data from database to prepare for AI Hub submission.
    
    Args:
        run_id: Run UUID string.
        workspace_id: Workspace UUID string.
        
    Returns:
        job_spec dictionary.
    """
    logger.info(f"Preparing run {run_id}")
    update_run_sync(run_id, status=RunStatus.PREPARING)
    
    # Load run and pipeline from database
    run_data = get_run_with_pipeline(run_id)
    
    if not run_data:
        update_run_sync(run_id, status=RunStatus.ERROR, error_code="RUN_NOT_FOUND")
        raise ValueError(f"Run {run_id} not found in database")
    
    pipeline_config = run_data.get("pipeline_config", {})
    model_path = run_data.get("model_artifact_path")
    
    # Validate required data
    if not model_path:
        logger.warning(f"No model artifact for run {run_id} - will fail at submit step")
    
    # Build job_spec from real data
    job_spec = build_job_spec(
        run_id=run_id,
        workspace_id=workspace_id,
        pipeline_config=pipeline_config,
        model_artifact_url=model_path or "",
        promptpack_content={},  # TODO: Load promptpack if needed
    )
    
    logger.info(f"Prepared run {run_id} with pipeline config")
    
    return {
        "run_id": run_id,
        "workspace_id": workspace_id,
        "status": "prepared",
        "job_spec": job_spec,
    }


@celery_app.task(bind=True, name="edgegate.tasks.submit_run")
def submit_run(
    self,
    prepare_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    PREPARING → SUBMITTING: Submit jobs to AI Hub.
    
    Uses the real QAIHubClient to submit compile and profile jobs.
    
    Args:
        prepare_result: Result from prepare_run task.
        
    Returns:
        Submission result with job IDs.
    """
    run_id = prepare_result["run_id"]
    workspace_id = prepare_result["workspace_id"]
    job_spec = prepare_result.get("job_spec", {})
    
    logger.info(f"Submitting run {run_id}")
    update_run_sync(run_id, status=RunStatus.SUBMITTING)
    
    # Get run details from database
    run_data = get_run_with_pipeline(run_id)
    if not run_data:
        update_run_sync(run_id, status=RunStatus.ERROR, error_code="RUN_NOT_FOUND")
        raise ValueError(f"Run {run_id} not found in database")
    
    # Create AI Hub client
    client = create_aihub_client(workspace_id)
    if not client:
        update_run_sync(run_id, status=RunStatus.ERROR, error_code="NO_AIHUB_TOKEN")
        raise ValueError(f"No AI Hub token configured for workspace {workspace_id}")
    
    # Get model path and device targets from pipeline config
    pipeline_config = run_data.get("pipeline_config", {})
    model_path = run_data.get("model_artifact_path")
    device_matrix = pipeline_config.get("device_matrix", [])
    
    if not model_path:
        # If no model artifact, we can't run profiling
        update_run_sync(run_id, status=RunStatus.ERROR, error_code="NO_MODEL_ARTIFACT")
        raise ValueError(f"No model artifact found for run {run_id}")
    
    if not device_matrix:
        device_matrix = ["Samsung Galaxy S24 (Family)"]  # Default device
    
    # Get the first device for now (future: support multiple devices)
    target_device = device_matrix[0] if isinstance(device_matrix[0], str) else device_matrix[0].get("name", "Samsung Galaxy S24 (Family)")
    
    # Submit compile job
    local_model_path = None
    try:
        model_to_submit = model_path
        if model_path.startswith("s3://"):
            model_filename = run_data.get("model_artifact_filename") or "model.pt"
            local_model_path = download_artifact(model_path, model_filename)
            model_to_submit = local_model_path

        logger.info(f"Submitting compile job for run {run_id} on device {target_device}")
        
        # Determine input specs from pipeline config or use defaults
        input_specs = pipeline_config.get("input_specs", {"image": (1, 3, 224, 224)})
        
        compile_job_id = run_async(client.submit_compile_job(
            model_path=model_to_submit,
            device_name=target_device,
            input_specs=input_specs,
        ))
        logger.info(f"Compile job submitted: {compile_job_id}")
        
        # Wait for compile job to complete
        logger.info(f"Waiting for compile job {compile_job_id} to complete...")
        compile_result = run_async(client.wait_for_job(compile_job_id, timeout_seconds=1800))
        
        if compile_result.status != JobStatus.COMPLETED:
            update_run_sync(run_id, status=RunStatus.ERROR, error_code="COMPILE_FAILED", 
                          error_detail=compile_result.error_message)
            raise ValueError(f"Compile job failed: {compile_result.error_message}")
        
        # Get the compiled model URL
        compiled_model_url = compile_result.result_url or f"https://aihub.qualcomm.com/jobs/{compile_job_id}/model"
        
        # Submit profile job
        logger.info(f"Submitting profile job for run {run_id}")
        profile_job_id = run_async(client.submit_profile_job(
            model_url=compiled_model_url,
            device_name=target_device,
        ))
        logger.info(f"Profile job submitted: {profile_job_id}")
        
        return {
            "run_id": run_id,
            "workspace_id": workspace_id,
            "status": "submitted",
            "job_ids": {
                "compile": compile_job_id,
                "profile": profile_job_id,
            },
            "device": target_device,
            "compiled_model_url": compiled_model_url,
        }
        
    except Exception as e:
        logger.error(f"Failed to submit AI Hub jobs for run {run_id}: {e}")
        update_run_sync(run_id, status=RunStatus.ERROR, error_code="SUBMIT_FAILED", error_detail=str(e))
        raise
    finally:
        if local_model_path and os.path.exists(local_model_path):
            try:
                os.remove(local_model_path)
                logger.info(f"Cleaned up temporary model file: {local_model_path}")
            except Exception as e:
                logger.warning(f"Failed to remove temporary model file {local_model_path}: {e}")


@celery_app.task(bind=True, name="edgegate.tasks.poll_run")
def poll_run(
    self,
    submit_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    SUBMITTING → RUNNING: Poll AI Hub for profile job completion.
    
    Uses the real QAIHubClient to wait for the profile job to complete.
    
    Args:
        submit_result: Result from submit_run task.
        
    Returns:
        Poll result with completion status.
    """
    run_id = submit_result["run_id"]
    workspace_id = submit_result.get("workspace_id")
    job_ids = submit_result.get("job_ids", {})
    profile_job_id = job_ids.get("profile")
    
    logger.info(f"Polling run {run_id} for profile job {profile_job_id}")
    update_run_sync(run_id, status=RunStatus.RUNNING)
    
    if not workspace_id:
        # Get workspace_id from database
        run_data = get_run_with_pipeline(run_id)
        workspace_id = run_data.get("workspace_id") if run_data else None
    
    if not workspace_id:
        update_run_sync(run_id, status=RunStatus.ERROR, error_code="NO_WORKSPACE")
        raise ValueError(f"No workspace found for run {run_id}")
    
    # Create AI Hub client
    client = create_aihub_client(workspace_id)
    if not client:
        update_run_sync(run_id, status=RunStatus.ERROR, error_code="NO_AIHUB_TOKEN")
        raise ValueError(f"No AI Hub token configured for workspace {workspace_id}")
    
    try:
        # Wait for profile job to complete
        logger.info(f"Waiting for profile job {profile_job_id} to complete...")
        profile_result = run_async(client.wait_for_job(profile_job_id, timeout_seconds=1800))
        
        if profile_result.status == JobStatus.FAILED:
            update_run_sync(run_id, status=RunStatus.ERROR, error_code="PROFILE_FAILED",
                          error_detail=profile_result.error_message)
            raise ValueError(f"Profile job failed: {profile_result.error_message}")
        
        logger.info(f"Profile job {profile_job_id} completed with status {profile_result.status}")
        
        return {
            "run_id": run_id,
            "workspace_id": workspace_id,
            "status": "completed",
            "job_ids": job_ids,
            "device": submit_result.get("device"),
            "compiled_model_url": submit_result.get("compiled_model_url"),
        }
        
    except Exception as e:
        logger.error(f"Failed to poll AI Hub for run {run_id}: {e}")
        update_run_sync(run_id, status=RunStatus.ERROR, error_code="POLL_FAILED", error_detail=str(e))
        raise


@celery_app.task(bind=True, name="edgegate.tasks.collect_results")
def collect_results(
    self,
    poll_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    RUNNING → COLLECTING: Download results from AI Hub.
    
    Uses the real QAIHubClient to download profile metrics.
    
    Args:
        poll_result: Result from poll_run task.
        
    Returns:
        Raw results from AI Hub.
    """
    run_id = poll_result["run_id"]
    workspace_id = poll_result.get("workspace_id")
    job_ids = poll_result.get("job_ids", {})
    profile_job_id = job_ids.get("profile")
    device = poll_result.get("device", "Unknown Device")
    
    logger.info(f"Collecting results for run {run_id}")
    update_run_sync(run_id, status=RunStatus.COLLECTING)
    
    # Create AI Hub client
    client = create_aihub_client(workspace_id)
    if not client:
        update_run_sync(run_id, status=RunStatus.ERROR, error_code="NO_AIHUB_TOKEN")
        raise ValueError(f"No AI Hub token configured for workspace {workspace_id}")
    
    try:
        # Download profile results
        logger.info(f"Downloading profile results for job {profile_job_id}")
        profile_result = run_async(client.get_profile_results(profile_job_id))
        
        if profile_result.status == JobStatus.FAILED:
            update_run_sync(run_id, status=RunStatus.ERROR, error_code="COLLECT_FAILED",
                          error_detail=profile_result.error_message)
            raise ValueError(f"Failed to collect profile results: {profile_result.error_message}")
        
        # Extract metrics from profile results
        raw_metrics = profile_result.metrics or {}
        raw_profile = profile_result.raw_profile or {}
        
        # Normalize metrics to expected format
        measurements = [{
            "inference_time_ms": raw_metrics.get("inference_time_ms", 0.0),
            "peak_memory_mb": raw_metrics.get("peak_memory_mb", 0.0),
        }]
        
        # Include compute unit breakdown if available
        compute_units = raw_metrics.get("compute_units", {})
        if compute_units:
            measurements[0]["compute_units"] = compute_units
        
        logger.info(f"Collected metrics for run {run_id}: {raw_metrics}")
        
        return {
            "run_id": run_id,
            "workspace_id": workspace_id,
            "status": "collected",
            "raw_results": {
                "devices": {
                    device: {
                        "measurements": measurements,
                        "raw_profile": raw_profile,
                    },
                },
            },
        }
        
    except Exception as e:
        logger.error(f"Failed to collect results for run {run_id}: {e}")
        update_run_sync(run_id, status=RunStatus.ERROR, error_code="COLLECT_FAILED", error_detail=str(e))
        raise


@celery_app.task(bind=True, name="edgegate.tasks.evaluate_run")
def evaluate_run(
    self,
    collect_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    COLLECTING → EVALUATING: Aggregate metrics and evaluate gates.
    
    Args:
        collect_result: Result from collect_results task.
        
    Returns:
        Evaluation result with metrics and gate status.
    """
    from edgegate.services.run import (
        aggregate_metrics_median,
        evaluate_gates,
        detect_flaky_metrics,
    )
    
    run_id = collect_result["run_id"]
    logger.info(f"Evaluating run {run_id}")
    update_run_sync(run_id, status=RunStatus.EVALUATING)
    
    # Process results
    raw_results = collect_result.get("raw_results", {})
    devices = raw_results.get("devices", {})
    
    all_metrics = {}
    device_metrics = {}
    
    for device_name, device_data in devices.items():
        measurements = device_data.get("measurements", [])
        
        # Aggregate with warmup exclusion (first measurement)
        aggregated = aggregate_metrics_median(measurements, warmup_count=1)
        device_metrics[device_name] = aggregated
        
        # Merge into all_metrics
        for k, v in aggregated.items():
            if k not in all_metrics:
                all_metrics[k] = []
            all_metrics[k].append(v)
        
        # Detect flaky metrics
        flaky = detect_flaky_metrics(measurements)
        if flaky:
            logger.warning(f"Flaky metrics for {device_name}: {flaky}")
    
    # Final aggregated metrics (average across devices)
    normalized_metrics = {}
    for k, values in all_metrics.items():
        normalized_metrics[k] = sum(values) / len(values)
    
    # Mock gates (in production, load from pipeline)
    gates = [
        {"metric": "inference_time_ms", "operator": "lt", "threshold": 50.0},
        {"metric": "peak_memory_mb", "operator": "lt", "threshold": 100.0},
    ]
    
    # Evaluate gates
    gates_eval = evaluate_gates(gates, normalized_metrics)
    
    return {
        "run_id": run_id,
        "status": "evaluated",
        "normalized_metrics": normalized_metrics,
        "gates_eval": gates_eval.to_dict(),
        "device_metrics": device_metrics,
        "gates_passed": gates_eval.passed,
    }


@celery_app.task(bind=True, name="edgegate.tasks.report_run")
def report_run(
    self,
    evaluate_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    EVALUATING → REPORTING → PASSED/FAILED: Build evidence bundle.
    
    Args:
        evaluate_result: Result from evaluate_run task.
        
    Returns:
        Final result with evidence bundle.
    """
    run_id = evaluate_result["run_id"]
    run_id_uuid = UUID(run_id)
    gates_passed = evaluate_result.get("gates_passed", False)
    
    logger.info(f"Reporting run {run_id}, gates_passed={gates_passed}")
    
    # Initialize KMS and Builder
    kms = LocalKeyManagementService(
        master_key_b64=settings.edgegenai_master_key,
        signing_keys_path=settings.signing_keys_dir,
    )
    builder = EvidenceBundleBuilder(kms)
    
    bundle_artifact_id = None
    
    try:
        with SyncSession() as session:
            # 1. Fetch all metadata for the bundle
            run_stmt = select(Run).where(Run.id == run_id_uuid)
            run = session.execute(run_stmt).scalar_one_or_none()
            if not run:
                raise ValueError(f"Run {run_id} not found")
                
            pipeline_stmt = select(Pipeline).where(Pipeline.id == run.pipeline_id)
            pipeline = session.execute(pipeline_stmt).scalar_one_or_none()
            
            model_stmt = select(Artifact).where(Artifact.id == run.model_artifact_id)
            model_artifact = session.execute(model_stmt).scalar_one_or_none()
            
            # Get PromptPack info
            pp_ref = pipeline.promptpack_ref_json
            from sqlalchemy import and_
            pp_stmt = select(PromptPack).where(
                and_(
                    PromptPack.workspace_id == run.workspace_id,
                    PromptPack.promptpack_id == pp_ref["promptpack_id"],
                    PromptPack.version == pp_ref["version"]
                )
            )
            promptpack = session.execute(pp_stmt).scalar_one_or_none()
            
            # 2. Build the signed bundle
            bundle = builder.build(
                run_id=run.id,
                workspace_id=run.workspace_id,
                pipeline_id=run.pipeline_id,
                pipeline_name=pipeline.name,
                model_artifact_id=run.model_artifact_id,
                model_sha256=model_artifact.sha256 if model_artifact else "unknown",
                status="passed" if gates_passed else "failed",
                trigger=run.trigger.value,
                created_at=run.created_at,
                completed_at=datetime.now(timezone.utc),
                gates_passed=gates_passed,
                gates_eval=evaluate_result.get("gates_eval", {}),
                normalized_metrics=evaluate_result.get("normalized_metrics", {}),
                device_results=evaluate_result.get("device_metrics", {}),
                devices_tested=list(evaluate_result.get("device_metrics", {}).keys()),
                promptpack_id=str(promptpack.id) if promptpack else "unknown",
                promptpack_version=promptpack.version if promptpack else "unknown",
                promptpack_sha256=promptpack.sha256 if promptpack else "unknown",
            )
            
            # 3. Store bundle as artifact
            bundle_json = bundle.to_json()
            from edgegate.core.security import compute_sha256
            sha256 = compute_sha256(bundle_json.encode())
            
            # Local storage
            from pathlib import Path
            storage_dir = Path("./data/artifacts")
            storage_dir.mkdir(parents=True, exist_ok=True)
            storage_path = storage_dir / sha256
            storage_path.write_bytes(bundle_json.encode())
            storage_url = f"file://{storage_path.absolute()}"
            
            bundle_artifact = Artifact(
                workspace_id=run.workspace_id,
                kind=ArtifactKind.BUNDLE,
                storage_url=storage_url,
                sha256=sha256,
                size_bytes=len(bundle_json),
                original_filename="evidence_bundle.json",
            )
            session.add(bundle_artifact)
            session.flush()
            bundle_artifact_id = bundle_artifact.id
            
            # 4. Update run with final status and bundle ID
            run.status = RunStatus.PASSED if gates_passed else RunStatus.FAILED
            run.normalized_metrics_json = evaluate_result.get("normalized_metrics")
            run.gates_eval_json = evaluate_result.get("gates_eval")
            run.bundle_artifact_id = bundle_artifact_id
            run.updated_at = datetime.now(timezone.utc)
            
            session.commit()
            logger.info(f"Run {run_id} reported successfully with bundle {bundle_artifact_id}")
            
    except Exception as e:
        logger.error(f"Failed to build evidence bundle for run {run_id}: {e}")
        # Fallback: update status without bundle if bundle creation fails
        update_run_sync(
            run_id,
            status=RunStatus.PASSED if gates_passed else RunStatus.FAILED,
            metrics=evaluate_result.get("normalized_metrics"),
            gates_eval=evaluate_result.get("gates_eval"),
        )
    
    return {
        "run_id": run_id,
        "status": "passed" if gates_passed else "failed",
        "bundle_artifact_id": str(bundle_artifact_id) if bundle_artifact_id else None,
        "gates_passed": gates_passed,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================================
# Task Chains
# ============================================================================


def execute_run_pipeline(run_id: str, workspace_id: str) -> str:
    """
    Execute the full run pipeline as a Celery chain.
    
    Args:
        run_id: Run UUID string.
        workspace_id: Workspace UUID string.
        
    Returns:
        Celery task ID for tracking.
    """
    pipeline = chain(
        prepare_run.s(run_id, workspace_id),
        submit_run.s(),
        poll_run.s(),
        collect_results.s(),
        evaluate_run.s(),
        report_run.s(),
    )
    
    result = pipeline.apply_async()
    return result.id


@celery_app.task(bind=True, name="edgegate.tasks.execute_run")
def execute_run(
    self,
    run_id: str,
    workspace_id: str,
) -> Dict[str, Any]:
    """
    Execute a complete run (convenience task for simple execution).
    
    This runs all stages synchronously within a single task.
    For production, use execute_run_pipeline for better monitoring.
    
    Args:
        run_id: Run UUID string.
        workspace_id: Workspace UUID string.
        
    Returns:
        Final result.
    """
    logger.info(f"Starting run execution for {run_id}")
    
    try:
        # Execute each stage
        prepare_result = prepare_run(run_id, workspace_id)
        submit_result = submit_run(prepare_result)
        poll_result = poll_run(submit_result)
        collect_result = collect_results(poll_result)
        evaluate_result = evaluate_run(collect_result)
        final_result = report_run(evaluate_result)
        
        logger.info(f"Run {run_id} completed: {final_result['status']}")
        return final_result
        
    except Exception as e:
        logger.error(f"Run {run_id} failed: {e}")
        return {
            "run_id": run_id,
            "status": "error",
            "error": str(e),
        }
