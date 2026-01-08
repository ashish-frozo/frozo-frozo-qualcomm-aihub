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
from edgegate.db import Run, RunStatus, Artifact, ArtifactKind, Pipeline, PromptPack
from edgegate.core.security import LocalKeyManagementService
from edgegate.services.evidence import EvidenceBundleBuilder


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
    
    Args:
        run_id: Run UUID string.
        workspace_id: Workspace UUID string.
        
    Returns:
        job_spec dictionary.
    """
    logger.info(f"Preparing run {run_id}")
    update_run_sync(run_id, status=RunStatus.PREPARING)
    
    # This would normally:
    # 1. Load run from database
    # 2. Load pipeline configuration
    # 3. Load model artifact metadata
    # 4. Load PromptPack content
    # 5. Build job_spec
    
    # For now, return a mock job_spec
    # In production, this would use async SQLAlchemy within sync context
    return {
        "run_id": run_id,
        "workspace_id": workspace_id,
        "status": "prepared",
        "job_spec": {
            "version": "1.0",
            "run_id": run_id,
        },
    }


@celery_app.task(bind=True, name="edgegate.tasks.submit_run")
def submit_run(
    self,
    prepare_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    PREPARING → SUBMITTING: Submit jobs to AI Hub.
    
    Args:
        prepare_result: Result from prepare_run task.
        
    Returns:
        Submission result with job IDs.
    """
    run_id = prepare_result["run_id"]
    logger.info(f"Submitting run {run_id}")
    update_run_sync(run_id, status=RunStatus.SUBMITTING)
    
    # This would normally:
    # 1. Get AI Hub token for workspace
    # 2. Submit compile job
    # 3. Wait for compile job
    # 4. Submit profile job
    # 5. Return job IDs
    
    return {
        "run_id": run_id,
        "status": "submitted",
        "job_ids": {
            "compile": f"mock-compile-{run_id[:8]}",
            "profile": f"mock-profile-{run_id[:8]}",
        },
    }


@celery_app.task(bind=True, name="edgegate.tasks.poll_run")
def poll_run(
    self,
    submit_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    SUBMITTING → RUNNING: Poll AI Hub for completion.
    
    Args:
        submit_result: Result from submit_run task.
        
    Returns:
        Poll result with completion status.
    """
    run_id = submit_result["run_id"]
    logger.info(f"Polling run {run_id}")
    update_run_sync(run_id, status=RunStatus.RUNNING)
    
    # This would normally:
    # 1. Poll AI Hub for job status
    # 2. Wait for completion
    # 3. Handle timeouts
    
    return {
        "run_id": run_id,
        "status": "completed",
        "job_ids": submit_result["job_ids"],
    }


@celery_app.task(bind=True, name="edgegate.tasks.collect_results")
def collect_results(
    self,
    poll_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    RUNNING → COLLECTING: Download results from AI Hub.
    
    Args:
        poll_result: Result from poll_run task.
        
    Returns:
        Raw results from AI Hub.
    """
    run_id = poll_result["run_id"]
    logger.info(f"Collecting results for run {run_id}")
    update_run_sync(run_id, status=RunStatus.COLLECTING)
    
    # This would normally:
    # 1. Download profile results
    # 2. Download inference outputs (if applicable)
    # 3. Store raw results
    
    # Mock results
    return {
        "run_id": run_id,
        "status": "collected",
        "raw_results": {
            "devices": {
                "Samsung Galaxy S24": {
                    "measurements": [
                        {"inference_time_ms": 15.2, "peak_memory_mb": 42.1},
                        {"inference_time_ms": 12.8, "peak_memory_mb": 41.9},
                        {"inference_time_ms": 13.1, "peak_memory_mb": 42.0},
                        {"inference_time_ms": 12.5, "peak_memory_mb": 41.8},
                    ],
                },
            },
        },
    }


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
