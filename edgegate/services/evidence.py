"""
Evidence bundle builder.

Creates signed evidence bundles containing:
- summary.json (signed with Ed25519)
- normalized_metrics.json
- gates_eval.json
- original model hash
- timestamps
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from edgegate.core.security import (
    LocalKeyManagementService,
    sign_data,
)


# ============================================================================
# Types
# ============================================================================


@dataclass
class EvidenceSummary:
    """Summary of a test run for evidence bundle."""
    run_id: str
    workspace_id: str
    pipeline_id: str
    pipeline_name: str
    model_artifact_id: str
    model_sha256: str
    status: str  # passed, failed, error
    trigger: str
    created_at: str
    completed_at: str
    gates_passed: bool
    gate_count: int
    gates_evaluated: int
    gates_failed: List[str]
    devices_tested: List[str]
    promptpack_id: str
    promptpack_version: str
    promptpack_sha256: str
    
    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)
    
    def sha256(self) -> str:
        """Compute SHA256 of the JSON representation."""
        return hashlib.sha256(self.to_json().encode()).hexdigest()


@dataclass
class SignedSummary:
    """Summary with Ed25519 signature."""
    summary: EvidenceSummary
    signature: str  # base64-encoded
    key_id: str
    
    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps({
            "summary": asdict(self.summary),
            "signature": self.signature,
            "key_id": self.key_id,
        }, indent=2, sort_keys=True)


@dataclass
class EvidenceBundle:
    """Complete evidence bundle for a run."""
    signed_summary: SignedSummary
    normalized_metrics: Dict[str, Any]
    gates_eval: Dict[str, Any]
    device_results: Dict[str, Dict[str, Any]]  # device_name -> results
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "signed_summary": json.loads(self.signed_summary.to_json()),
            "normalized_metrics": self.normalized_metrics,
            "gates_eval": self.gates_eval,
            "device_results": self.device_results,
        }
    
    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


# ============================================================================
# Bundle Builder
# ============================================================================


class EvidenceBundleBuilder:
    """
    Builds signed evidence bundles for test runs.
    
    Evidence bundles provide cryptographic proof of test results
    that can be verified offline without EdgeGate access.
    """

    def __init__(self, kms: LocalKeyManagementService):
        self.kms = kms

    def build(
        self,
        run_id: UUID,
        workspace_id: UUID,
        pipeline_id: UUID,
        pipeline_name: str,
        model_artifact_id: UUID,
        model_sha256: str,
        status: str,
        trigger: str,
        created_at: datetime,
        completed_at: datetime,
        gates_passed: bool,
        gates_eval: Dict[str, Any],
        normalized_metrics: Dict[str, Any],
        device_results: Dict[str, Dict[str, Any]],
        devices_tested: List[str],
        promptpack_id: str,
        promptpack_version: str,
        promptpack_sha256: str,
    ) -> EvidenceBundle:
        """
        Build a signed evidence bundle.
        
        Args:
            run_id: Run UUID.
            workspace_id: Workspace UUID.
            pipeline_id: Pipeline UUID.
            pipeline_name: Pipeline name.
            model_artifact_id: Model artifact UUID.
            model_sha256: SHA256 of model artifact.
            status: Final run status.
            trigger: Run trigger type.
            created_at: Run creation timestamp.
            completed_at: Run completion timestamp.
            gates_passed: Whether all gates passed.
            gates_eval: Gates evaluation results.
            normalized_metrics: Aggregated metrics.
            device_results: Per-device results.
            devices_tested: List of device names.
            promptpack_id: PromptPack identifier.
            promptpack_version: PromptPack version.
            promptpack_sha256: SHA256 of PromptPack content.
            
        Returns:
            Signed EvidenceBundle.
        """
        # Extract gates info
        gate_results = gates_eval.get("gates", [])
        gates_failed = [g["metric"] for g in gate_results if not g.get("passed", False)]
        
        # Build summary
        summary = EvidenceSummary(
            run_id=str(run_id),
            workspace_id=str(workspace_id),
            pipeline_id=str(pipeline_id),
            pipeline_name=pipeline_name,
            model_artifact_id=str(model_artifact_id),
            model_sha256=model_sha256,
            status=status,
            trigger=trigger,
            created_at=created_at.isoformat(),
            completed_at=completed_at.isoformat(),
            gates_passed=gates_passed,
            gate_count=len(gate_results),
            gates_evaluated=len(gate_results),
            gates_failed=gates_failed,
            devices_tested=devices_tested,
            promptpack_id=promptpack_id,
            promptpack_version=promptpack_version,
            promptpack_sha256=promptpack_sha256,
        )
        
        # Sign summary
        summary_json = summary.to_json()
        signature, key_id = sign_data(summary_json.encode(), self.kms)
        
        signed_summary = SignedSummary(
            summary=summary,
            signature=signature,
            key_id=key_id,
        )
        
        # Build bundle
        return EvidenceBundle(
            signed_summary=signed_summary,
            normalized_metrics=normalized_metrics,
            gates_eval=gates_eval,
            device_results=device_results,
        )

    def verify(
        self,
        bundle: EvidenceBundle,
    ) -> bool:
        """
        Verify the signature on an evidence bundle.
        
        Args:
            bundle: The evidence bundle to verify.
            
        Returns:
            True if signature is valid, False otherwise.
        """
        from edgegate.core.security import verify_signature
        
        summary_json = bundle.signed_summary.summary.to_json()
        
        return verify_signature(
            data=summary_json.encode(),
            signature=bundle.signed_summary.signature,
            key_id=bundle.signed_summary.key_id,
            kms=self.kms,
        )
