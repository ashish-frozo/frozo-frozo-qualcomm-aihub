"""
ProbeSuite - Capability discovery through AI Hub probes.

This module implements the capability discovery system that:
1. Validates AI Hub token
2. Lists available devices
3. Tests model compilation for each packaging type
4. Tests profiling capabilities
5. Tests inference capabilities
6. Generates workspace_capabilities.json and metric_mapping.json
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from edgegate.aihub.client import (
    AIHubClient,
    DeviceInfo,
    JobStatus,
    TargetRuntime,
    ProfileResult,
)


# ============================================================================
# Types
# ============================================================================


class ProbeType(str, Enum):
    """Types of probes."""
    TOKEN_VALIDATION = "token_validation"
    DEVICE_LIST = "device_list"
    COMPILE_TORCH = "compile_torch"
    COMPILE_ONNX = "compile_onnx"
    COMPILE_ONNX_EXTERNAL = "compile_onnx_external"
    COMPILE_AIMET = "compile_aimet"
    PROFILE = "profile"
    INFERENCE = "inference"


class ProbeStatus(str, Enum):
    """Status of a probe."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ProbeResult:
    """Result of a single probe."""
    probe_type: ProbeType
    status: ProbeStatus
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[float] = None
    error: Optional[str] = None


@dataclass
class PackagingTypeCapability:
    """Capability for a specific packaging type."""
    packaging_type: str  # torch, onnx, onnx_external, aimet
    supported: bool
    compile_target: Optional[str] = None  # e.g., "qnn_dlc"
    compile_time_ms: Optional[float] = None
    notes: Optional[str] = None


@dataclass
class DeviceCapability:
    """Capability discovered for a device."""
    device_name: str
    device_id: str
    chipset: str
    packaging_types: List[PackagingTypeCapability] = field(default_factory=list)
    profile_supported: bool = False
    inference_supported: bool = False


@dataclass
class MetricPath:
    """JSONPath specification for a metric."""
    metric_name: str
    jsonpath: str
    unit: str
    stability: str  # stable, experimental, unknown
    description: Optional[str] = None


@dataclass
class WorkspaceCapabilities:
    """Complete workspace capabilities from ProbeSuite."""
    workspace_id: str
    probe_run_id: str
    probed_at: str  # ISO format
    token_valid: bool
    devices: List[DeviceCapability] = field(default_factory=list)
    probe_results: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(asdict(self), indent=2, default=str)
    
    def sha256(self) -> str:
        """Compute SHA256 of the JSON representation."""
        return hashlib.sha256(self.to_json().encode()).hexdigest()


@dataclass
class MetricMapping:
    """Metric extraction mapping."""
    workspace_id: str
    generated_at: str  # ISO format
    metrics: List[MetricPath] = field(default_factory=list)
    
    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(asdict(self), indent=2, default=str)
    
    def sha256(self) -> str:
        """Compute SHA256 of the JSON representation."""
        return hashlib.sha256(self.to_json().encode()).hexdigest()


# ============================================================================
# ProbeSuite
# ============================================================================


class ProbeSuiteError(Exception):
    """Error during probe execution."""
    
    def __init__(self, message: str, probe_type: Optional[ProbeType] = None):
        self.message = message
        self.probe_type = probe_type
        super().__init__(message)


class ProbeSuite:
    """
    ProbeSuite discovers AI Hub capabilities for a workspace.
    
    The suite runs a series of probes to determine:
    - Token validity
    - Available devices
    - Supported packaging types (torch, onnx, onnx_external, aimet)
    - Profiling capabilities
    - Inference capabilities
    
    Results are stored as workspace_capabilities.json and metric_mapping.json.
    """

    # Default probe model paths (relative to probe_models directory)
    DEFAULT_TORCH_MODEL = "torch/model.pt"
    DEFAULT_ONNX_MODEL = "onnx_external/model.onnx"
    DEFAULT_ONNX_DATA = "onnx_external/model.data"

    def __init__(
        self,
        client: AIHubClient,
        workspace_id: UUID,
        probe_models_path: Optional[Path] = None,
    ):
        """
        Initialize ProbeSuite.
        
        Args:
            client: AI Hub client instance.
            workspace_id: Workspace UUID.
            probe_models_path: Path to probe model fixtures.
        """
        self.client = client
        self.workspace_id = workspace_id
        self.probe_models_path = probe_models_path or Path("edgegate/probe_models")
        self.probe_run_id = str(uuid4())
        self.results: List[ProbeResult] = []

    async def run_all(self) -> WorkspaceCapabilities:
        """
        Run all probes and return workspace capabilities.
        
        Returns:
            WorkspaceCapabilities with all discovered capabilities.
        """
        import time
        
        # Initialize capabilities
        capabilities = WorkspaceCapabilities(
            workspace_id=str(self.workspace_id),
            probe_run_id=self.probe_run_id,
            probed_at=datetime.now(timezone.utc).isoformat(),
            token_valid=False,
            devices=[],
            probe_results=[],
        )

        # Probe 1: Token validation
        token_result = await self._probe_token_validation()
        self.results.append(token_result)
        capabilities.token_valid = token_result.status == ProbeStatus.PASSED
        
        if not capabilities.token_valid:
            # Cannot proceed without valid token
            capabilities.probe_results = [asdict(r) for r in self.results]
            return capabilities

        # Probe 2: Device list
        device_result = await self._probe_device_list()
        self.results.append(device_result)
        
        if device_result.status != ProbeStatus.PASSED:
            capabilities.probe_results = [asdict(r) for r in self.results]
            return capabilities

        # Extract device info
        devices_data = device_result.data.get("devices", [])
        
        # For each device, test packaging types
        for device_info in devices_data[:3]:  # Limit to first 3 devices
            device_cap = DeviceCapability(
                device_name=device_info["name"],
                device_id=device_info["device_id"],
                chipset=device_info["chipset"],
            )
            
            # Test TorchScript compilation
            torch_result = await self._probe_compile_torch(device_info["name"])
            self.results.append(torch_result)
            device_cap.packaging_types.append(PackagingTypeCapability(
                packaging_type="torch",
                supported=torch_result.status == ProbeStatus.PASSED,
                compile_target="qnn_dlc",
                compile_time_ms=torch_result.duration_ms,
            ))
            
            # Test ONNX compilation
            onnx_result = await self._probe_compile_onnx(device_info["name"])
            self.results.append(onnx_result)
            device_cap.packaging_types.append(PackagingTypeCapability(
                packaging_type="onnx",
                supported=onnx_result.status == ProbeStatus.PASSED,
                compile_target="qnn_dlc",
                compile_time_ms=onnx_result.duration_ms,
            ))
            
            # Test profiling (if compile succeeded)
            if torch_result.status == ProbeStatus.PASSED:
                profile_result = await self._probe_profile(
                    device_info["name"],
                    torch_result.data.get("model_url"),
                )
                self.results.append(profile_result)
                device_cap.profile_supported = profile_result.status == ProbeStatus.PASSED
                device_cap.inference_supported = profile_result.status == ProbeStatus.PASSED
            
            capabilities.devices.append(device_cap)

        # Store all probe results
        capabilities.probe_results = [asdict(r) for r in self.results]
        
        return capabilities

    async def generate_metric_mapping(
        self,
        capabilities: WorkspaceCapabilities,
    ) -> MetricMapping:
        """
        Generate metric mapping from capabilities.
        
        Args:
            capabilities: Discovered capabilities.
            
        Returns:
            MetricMapping with JSONPath specifications.
        """
        mapping = MetricMapping(
            workspace_id=str(self.workspace_id),
            generated_at=datetime.now(timezone.utc).isoformat(),
            metrics=[],
        )

        # Standard metrics (always available if profiling works)
        if any(d.profile_supported for d in capabilities.devices):
            mapping.metrics.extend([
                MetricPath(
                    metric_name="inference_time_ms",
                    jsonpath="$.execution_summary.estimated_inference_time_ms",
                    unit="ms",
                    stability="stable",
                    description="Total inference time in milliseconds",
                ),
                MetricPath(
                    metric_name="peak_memory_mb",
                    jsonpath="$.execution_summary.peak_memory_mb",
                    unit="MB",
                    stability="stable",
                    description="Peak memory usage in megabytes",
                ),
                MetricPath(
                    metric_name="npu_compute_percent",
                    jsonpath="$.compute_unit_breakdown.npu",
                    unit="%",
                    stability="experimental",
                    description="Percentage of computation on NPU",
                ),
                MetricPath(
                    metric_name="gpu_compute_percent",
                    jsonpath="$.compute_unit_breakdown.gpu",
                    unit="%",
                    stability="experimental",
                    description="Percentage of computation on GPU",
                ),
                MetricPath(
                    metric_name="cpu_compute_percent",
                    jsonpath="$.compute_unit_breakdown.cpu",
                    unit="%",
                    stability="experimental",
                    description="Percentage of computation on CPU",
                ),
            ])

            # LLM-specific metrics (experimental - PRD §22 unknown)
            mapping.metrics.extend([
                MetricPath(
                    metric_name="ttft_ms",
                    jsonpath="$.llm_metrics.time_to_first_token_ms",
                    unit="ms",
                    stability="unknown",
                    description="Time to first token (LLM)",
                ),
                MetricPath(
                    metric_name="tps",
                    jsonpath="$.llm_metrics.tokens_per_second",
                    unit="tokens/s",
                    stability="unknown",
                    description="Tokens per second (LLM)",
                ),
            ])

        return mapping

    # ========================================================================
    # Individual Probes
    # ========================================================================

    async def _probe_token_validation(self) -> ProbeResult:
        """Probe: Validate API token."""
        import time
        start = time.time()
        
        try:
            is_valid = await self.client.validate_token()
            duration = (time.time() - start) * 1000
            
            if is_valid:
                return ProbeResult(
                    probe_type=ProbeType.TOKEN_VALIDATION,
                    status=ProbeStatus.PASSED,
                    message="Token is valid",
                    duration_ms=duration,
                )
            else:
                return ProbeResult(
                    probe_type=ProbeType.TOKEN_VALIDATION,
                    status=ProbeStatus.FAILED,
                    message="Token validation failed",
                    duration_ms=duration,
                    error="Invalid or expired token",
                )
        except Exception as e:
            return ProbeResult(
                probe_type=ProbeType.TOKEN_VALIDATION,
                status=ProbeStatus.FAILED,
                message="Token validation error",
                error=str(e),
            )

    async def _probe_device_list(self) -> ProbeResult:
        """Probe: List available devices."""
        import time
        start = time.time()
        
        try:
            devices = await self.client.list_devices()
            duration = (time.time() - start) * 1000
            
            device_data = [
                {
                    "name": d.name,
                    "device_id": d.device_id,
                    "chipset": d.chipset,
                    "os": d.os,
                    "form_factor": d.form_factor,
                }
                for d in devices
            ]
            
            return ProbeResult(
                probe_type=ProbeType.DEVICE_LIST,
                status=ProbeStatus.PASSED,
                message=f"Found {len(devices)} devices",
                data={"devices": device_data, "count": len(devices)},
                duration_ms=duration,
            )
        except Exception as e:
            return ProbeResult(
                probe_type=ProbeType.DEVICE_LIST,
                status=ProbeStatus.FAILED,
                message="Failed to list devices",
                error=str(e),
            )

    async def _probe_compile_torch(self, device_name: str) -> ProbeResult:
        """Probe: Compile TorchScript model."""
        import time
        start = time.time()
        
        model_path = self.probe_models_path / self.DEFAULT_TORCH_MODEL
        
        if not model_path.exists():
            return ProbeResult(
                probe_type=ProbeType.COMPILE_TORCH,
                status=ProbeStatus.SKIPPED,
                message=f"Probe model not found: {model_path}",
            )
        
        try:
            job_id = await self.client.submit_compile_job(
                model_path=str(model_path),
                device_name=device_name,
                input_specs={"x": (1, 8)},  # TinyMLP input shape
                target_runtime=TargetRuntime.QNN_DLC,
            )
            
            job_info = await self.client.wait_for_job(job_id, timeout_seconds=300)
            duration = (time.time() - start) * 1000
            
            if job_info.status == JobStatus.COMPLETED:
                return ProbeResult(
                    probe_type=ProbeType.COMPILE_TORCH,
                    status=ProbeStatus.PASSED,
                    message=f"TorchScript compilation succeeded on {device_name}",
                    data={
                        "job_id": job_id,
                        "device": device_name,
                        "model_url": job_info.result_url,
                    },
                    duration_ms=duration,
                )
            else:
                return ProbeResult(
                    probe_type=ProbeType.COMPILE_TORCH,
                    status=ProbeStatus.FAILED,
                    message=f"Compilation failed: {job_info.error_message}",
                    data={"job_id": job_id, "device": device_name},
                    duration_ms=duration,
                    error=job_info.error_message,
                )
        except Exception as e:
            return ProbeResult(
                probe_type=ProbeType.COMPILE_TORCH,
                status=ProbeStatus.FAILED,
                message="Compilation error",
                error=str(e),
            )

    async def _probe_compile_onnx(self, device_name: str) -> ProbeResult:
        """Probe: Compile ONNX model."""
        import time
        start = time.time()
        
        model_path = self.probe_models_path / self.DEFAULT_ONNX_MODEL
        
        if not model_path.exists():
            return ProbeResult(
                probe_type=ProbeType.COMPILE_ONNX,
                status=ProbeStatus.SKIPPED,
                message=f"Probe model not found: {model_path}",
            )
        
        try:
            job_id = await self.client.submit_compile_job(
                model_path=str(model_path),
                device_name=device_name,
                input_specs={"x": (1, 8)},  # TinyMLP input shape
                target_runtime=TargetRuntime.QNN_DLC,
            )
            
            job_info = await self.client.wait_for_job(job_id, timeout_seconds=300)
            duration = (time.time() - start) * 1000
            
            if job_info.status == JobStatus.COMPLETED:
                return ProbeResult(
                    probe_type=ProbeType.COMPILE_ONNX,
                    status=ProbeStatus.PASSED,
                    message=f"ONNX compilation succeeded on {device_name}",
                    data={
                        "job_id": job_id,
                        "device": device_name,
                        "model_url": job_info.result_url,
                    },
                    duration_ms=duration,
                )
            else:
                return ProbeResult(
                    probe_type=ProbeType.COMPILE_ONNX,
                    status=ProbeStatus.FAILED,
                    message=f"Compilation failed: {job_info.error_message}",
                    data={"job_id": job_id, "device": device_name},
                    duration_ms=duration,
                    error=job_info.error_message,
                )
        except Exception as e:
            return ProbeResult(
                probe_type=ProbeType.COMPILE_ONNX,
                status=ProbeStatus.FAILED,
                message="Compilation error",
                error=str(e),
            )

    async def _probe_profile(
        self,
        device_name: str,
        model_url: Optional[str],
    ) -> ProbeResult:
        """Probe: Profile compiled model."""
        import time
        start = time.time()
        
        if not model_url:
            return ProbeResult(
                probe_type=ProbeType.PROFILE,
                status=ProbeStatus.SKIPPED,
                message="No compiled model URL available",
            )
        
        try:
            job_id = await self.client.submit_profile_job(
                model_url=model_url,
                device_name=device_name,
            )
            
            job_info = await self.client.wait_for_job(job_id, timeout_seconds=300)
            duration = (time.time() - start) * 1000
            
            if job_info.status == JobStatus.COMPLETED:
                # Get profile results
                profile = await self.client.get_profile_results(job_id)
                
                return ProbeResult(
                    probe_type=ProbeType.PROFILE,
                    status=ProbeStatus.PASSED,
                    message=f"Profiling succeeded on {device_name}",
                    data={
                        "job_id": job_id,
                        "device": device_name,
                        "metrics": profile.metrics,
                    },
                    duration_ms=duration,
                )
            else:
                return ProbeResult(
                    probe_type=ProbeType.PROFILE,
                    status=ProbeStatus.FAILED,
                    message=f"Profiling failed: {job_info.error_message}",
                    data={"job_id": job_id, "device": device_name},
                    duration_ms=duration,
                    error=job_info.error_message,
                )
        except Exception as e:
            return ProbeResult(
                probe_type=ProbeType.PROFILE,
                status=ProbeStatus.FAILED,
                message="Profiling error",
                error=str(e),
            )
