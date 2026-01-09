"""
AI Hub client interface and implementation.

Provides abstraction over the qai_hub SDK for:
- Token validation
- Device listing
- Model compilation
- Profiling
- Inference

This module is designed with a Protocol interface to allow mocking in tests.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from uuid import UUID


# ============================================================================
# Types and Enums
# ============================================================================


class JobStatus(str, Enum):
    """Status of an AI Hub job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TargetRuntime(str, Enum):
    """Target runtime for compilation."""
    TFLITE = "tflite"
    ONNX = "onnx"
    QNN_LIB = "qnn_lib_aarch64_android"
    QNN_CONTEXT = "qnn_context_binary"
    QNN_DLC = "qnn_dlc"


@dataclass
class DeviceInfo:
    """Information about an AI Hub device."""
    name: str
    device_id: str
    chipset: str
    os: str
    form_factor: str
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class JobInfo:
    """Information about an AI Hub job."""
    job_id: str
    status: JobStatus
    job_type: str  # compile, profile, inference
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    result_url: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None


@dataclass
class CompileResult:
    """Result of a compilation job."""
    job_id: str
    status: JobStatus
    target_runtime: str
    model_url: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class ProfileResult:
    """Result of a profiling job."""
    job_id: str
    status: JobStatus
    metrics: Dict[str, Any] = field(default_factory=dict)
    raw_profile: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


@dataclass
class InferenceResult:
    """Result of an inference job."""
    job_id: str
    status: JobStatus
    outputs: Optional[Dict[str, Any]] = None
    timing: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


# ============================================================================
# Client Protocol
# ============================================================================


@runtime_checkable
class AIHubClient(Protocol):
    """
    Protocol for AI Hub client implementations.
    
    This allows for both real and mock implementations.
    """

    async def validate_token(self) -> bool:
        """
        Validate the API token.
        
        Returns:
            True if token is valid, False otherwise.
        """
        ...

    async def list_devices(self) -> List[DeviceInfo]:
        """
        List available devices.
        
        Returns:
            List of DeviceInfo objects.
        """
        ...

    async def submit_compile_job(
        self,
        model_path: str,
        device_name: str,
        input_specs: Dict[str, tuple],
        target_runtime: TargetRuntime = TargetRuntime.TFLITE,
        options: Optional[str] = None,
    ) -> str:
        """
        Submit a compilation job.
        
        Args:
            model_path: Path to the model file.
            device_name: Target device name.
            input_specs: Input specifications.
            target_runtime: Target runtime.
            options: Additional compile options.
            
        Returns:
            Job ID.
        """
        ...

    async def get_job_status(self, job_id: str) -> JobInfo:
        """
        Get the status of a job.
        
        Args:
            job_id: The job ID.
            
        Returns:
            JobInfo with current status.
        """
        ...

    async def wait_for_job(
        self,
        job_id: str,
        timeout_seconds: int = 1800,
        poll_interval: int = 10,
    ) -> JobInfo:
        """
        Wait for a job to complete.
        
        Args:
            job_id: The job ID.
            timeout_seconds: Maximum wait time.
            poll_interval: Seconds between status checks.
            
        Returns:
            JobInfo with final status.
        """
        ...

    async def submit_profile_job(
        self,
        model_url: str,
        device_name: str,
    ) -> str:
        """
        Submit a profiling job.
        
        Args:
            model_url: URL of the compiled model.
            device_name: Target device name.
            
        Returns:
            Job ID.
        """
        ...

    async def get_profile_results(self, job_id: str) -> ProfileResult:
        """
        Get profiling results.
        
        Args:
            job_id: The profile job ID.
            
        Returns:
            ProfileResult with metrics.
        """
        ...

    async def submit_inference_job(
        self,
        model_url: str,
        device_name: str,
        inputs: Dict[str, Any],
    ) -> str:
        """
        Submit an inference job.
        
        Args:
            model_url: URL of the compiled model.
            device_name: Target device name.
            inputs: Input tensors.
            
        Returns:
            Job ID.
        """
        ...

    async def get_inference_results(self, job_id: str) -> InferenceResult:
        """
        Get inference results.
        
        Args:
            job_id: The inference job ID.
            
        Returns:
            InferenceResult with outputs.
        """
        ...


# ============================================================================
# Real Implementation (requires qai_hub SDK)
# ============================================================================


class QAIHubClient:
    """
    Real AI Hub client using the qai_hub SDK.
    
    Note: This implementation wraps the synchronous SDK in asyncio.
    """

    # Mapping of common chipset IDs or aliases to valid AI Hub device names
    DEVICE_MAPPING = {
        "sm8650": "Samsung Galaxy S24 (Family)",
        "sm8550": "Samsung Galaxy S23 (Family)",
        "sm8450": "Samsung Galaxy S22 (Family)",
        "sm8350": "Samsung Galaxy S21 (Family)",
        "sm8250": "Samsung Galaxy S20 (Family)",
        "sa8650": "SA8650 (Proxy)",
        "sa8775": "SA8775 (Proxy)",
        "sa8255": "SA8255 (Proxy)",
        "qcs6490": "QCS6490 (Proxy)",
        "qcs8550": "QCS8550 (Proxy)",
        "rb5": "RB5 (Proxy)",
        "rb3": "RB3 Gen 2 (Proxy)",
    }

    def __init__(self, api_token: str):
        """
        Initialize the client.
        
        Args:
            api_token: AI Hub API token.
        """
        self._token = api_token
        self._hub = None  # Lazy import

    def _get_hub(self):
        """Get or initialize the hub module."""
        if self._hub is None:
            try:
                import qai_hub as hub
                # Configure authentication
                # In newer versions (>=0.40.0), use set_session_token
                if hasattr(hub, "set_session_token"):
                    hub.set_session_token(self._token)
                elif hasattr(hub, "hub") and hasattr(hub.hub, "set_session_token"):
                    hub.hub.set_session_token(self._token)
                else:
                    # Fallback for older versions if needed, though we now require >=0.40.0
                    logger.warning("qai_hub.set_session_token not found. Attempting to proceed without it.")
                
                self._hub = hub
            except ImportError:
                raise RuntimeError(
                    "qai_hub package not installed. "
                    "Install with: pip install qai_hub"
                )
        return self._hub

    async def validate_token(self) -> bool:
        """Validate the API token by attempting to list devices."""
        import asyncio
        try:
            hub = self._get_hub()
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            devices = await loop.run_in_executor(None, hub.get_devices)
            return len(devices) > 0
        except Exception:
            return False

    async def list_devices(self) -> List[DeviceInfo]:
        """List available devices."""
        import asyncio
        hub = self._get_hub()
        loop = asyncio.get_event_loop()
        devices = await loop.run_in_executor(None, hub.get_devices)
        
        return [
            DeviceInfo(
                name=d.name,
                device_id=str(d.name),  # Use name as ID
                chipset=getattr(d, 'chipset', 'unknown'),
                os=getattr(d, 'os', 'unknown'),
                form_factor=getattr(d, 'form_factor', 'unknown'),
                attributes=getattr(d, 'attributes', {}),
            )
            for d in devices
        ]

    async def submit_compile_job(
        self,
        model_path: str,
        device_name: str,
        input_specs: Dict[str, tuple],
        target_runtime: TargetRuntime = TargetRuntime.TFLITE,
        options: Optional[str] = None,
    ) -> str:
        """Submit a compilation job."""
        import asyncio
        hub = self._get_hub()
        
        # Map device name if it's an alias or chipset ID
        mapped_device = self.DEVICE_MAPPING.get(device_name.lower(), device_name)
        
        # Validate device name
        try:
            # Try to get the device directly
            hub_device = hub.Device(mapped_device)
        except Exception:
            # If failed, try to find a match in available devices
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Device '{device_name}' not found. Searching for alternatives...")
            
            available_devices = hub.get_devices()
            match = None
            for d in available_devices:
                if mapped_device.lower() in d.name.lower() or d.name.lower() in mapped_device.lower():
                    match = d
                    break
            
            if match:
                logger.info(f"Found matching device: {match.name}")
                hub_device = match
            else:
                logger.error(f"No matching device found for '{device_name}'")
                # Fallback to default if everything fails, or re-raise
                hub_device = hub.Device("Samsung Galaxy S24 (Family)")
        
        compile_options = ""
        if target_runtime != TargetRuntime.TFLITE:
            compile_options = f"--target_runtime {target_runtime.value}"
        if options:
            compile_options = f"{compile_options} {options}".strip()
        
        def submit():
            job = hub.submit_compile_job(
                model=model_path,
                device=hub_device,
                input_specs=input_specs,
                options=compile_options if compile_options else None,
            )
            return str(job.job_id)
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, submit)

    async def get_job_status(self, job_id: str) -> JobInfo:
        """Get job status."""
        import asyncio
        hub = self._get_hub()
        
        def get_status():
            job = hub.get_job(job_id)
            status_map = {
                'PENDING': JobStatus.PENDING,
                'RUNNING': JobStatus.RUNNING,
                'SUCCEEDED': JobStatus.COMPLETED,
                'FAILED': JobStatus.FAILED,
                'CANCELLED': JobStatus.CANCELLED,
            }
            return JobInfo(
                job_id=job_id,
                status=status_map.get(job.status, JobStatus.PENDING),
                job_type=getattr(job, 'job_type', 'unknown'),
                error_message=getattr(job, 'error', None),
            )
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, get_status)

    async def wait_for_job(
        self,
        job_id: str,
        timeout_seconds: int = 1800,
        poll_interval: int = 10,
    ) -> JobInfo:
        """Wait for job completion."""
        import asyncio
        hub = self._get_hub()
        
        def wait():
            job = hub.get_job(job_id)
            job.wait(timeout=timeout_seconds)
            return job
        
        loop = asyncio.get_event_loop()
        job = await loop.run_in_executor(None, wait)
        
        return await self.get_job_status(job_id)

    async def submit_profile_job(
        self,
        model_url: str,
        device_name: str,
    ) -> str:
        """Submit a profiling job."""
        import asyncio
        hub = self._get_hub()
        
        def submit():
            job = hub.submit_profile_job(
                model=model_url,
                device=hub.Device(device_name),
            )
            return str(job.job_id)
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, submit)

    async def get_profile_results(self, job_id: str) -> ProfileResult:
        """Get profiling results."""
        import asyncio
        hub = self._get_hub()
        
        def get_results():
            job = hub.get_job(job_id)
            profile = job.download_profile()
            return profile
        
        loop = asyncio.get_event_loop()
        try:
            profile = await loop.run_in_executor(None, get_results)
            return ProfileResult(
                job_id=job_id,
                status=JobStatus.COMPLETED,
                metrics=profile if isinstance(profile, dict) else {},
                raw_profile=profile if isinstance(profile, dict) else None,
            )
        except Exception as e:
            return ProfileResult(
                job_id=job_id,
                status=JobStatus.FAILED,
                error_message=str(e),
            )

    async def submit_inference_job(
        self,
        model_url: str,
        device_name: str,
        inputs: Dict[str, Any],
    ) -> str:
        """Submit an inference job."""
        import asyncio
        hub = self._get_hub()
        
        def submit():
            job = hub.submit_inference_job(
                model=model_url,
                device=hub.Device(device_name),
                inputs=inputs,
            )
            return str(job.job_id)
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, submit)

    async def get_inference_results(self, job_id: str) -> InferenceResult:
        """Get inference results."""
        import asyncio
        hub = self._get_hub()
        
        def get_results():
            job = hub.get_job(job_id)
            outputs = job.download_output_data()
            return outputs
        
        loop = asyncio.get_event_loop()
        try:
            outputs = await loop.run_in_executor(None, get_results)
            return InferenceResult(
                job_id=job_id,
                status=JobStatus.COMPLETED,
                outputs=outputs,
            )
        except Exception as e:
            return InferenceResult(
                job_id=job_id,
                status=JobStatus.FAILED,
                error_message=str(e),
            )


# ============================================================================
# Mock Implementation for Testing
# ============================================================================


class MockAIHubClient:
    """
    Mock AI Hub client for testing without real API access.
    
    Simulates successful responses for all operations.
    """

    def __init__(self, api_token: str = "mock-token"):
        self._token = api_token
        self._job_counter = 0
        self._jobs: Dict[str, JobInfo] = {}

    async def validate_token(self) -> bool:
        """Always returns True for mock."""
        return self._token.startswith("mock") or len(self._token) > 10

    async def list_devices(self) -> List[DeviceInfo]:
        """Return mock device list."""
        return [
            DeviceInfo(
                name="Samsung Galaxy S24 (Family)",
                device_id="samsung_galaxy_s24",
                chipset="Snapdragon 8 Gen 3",
                os="Android 14",
                form_factor="phone",
            ),
            DeviceInfo(
                name="Samsung Galaxy S23 (Family)",
                device_id="samsung_galaxy_s23",
                chipset="Snapdragon 8 Gen 2",
                os="Android 13",
                form_factor="phone",
            ),
            DeviceInfo(
                name="Qualcomm RB3 Gen 2",
                device_id="qc_rb3_gen2",
                chipset="QCS6490",
                os="Linux",
                form_factor="embedded",
            ),
        ]

    async def submit_compile_job(
        self,
        model_path: str,
        device_name: str,
        input_specs: Dict[str, tuple],
        target_runtime: TargetRuntime = TargetRuntime.TFLITE,
        options: Optional[str] = None,
    ) -> str:
        """Submit mock compile job."""
        self._job_counter += 1
        job_id = f"mock-compile-{self._job_counter}"
        self._jobs[job_id] = JobInfo(
            job_id=job_id,
            status=JobStatus.COMPLETED,
            job_type="compile",
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            result_url=f"https://aihub.qualcomm.com/jobs/{job_id}/model",
        )
        return job_id

    async def get_job_status(self, job_id: str) -> JobInfo:
        """Get mock job status."""
        if job_id in self._jobs:
            return self._jobs[job_id]
        return JobInfo(
            job_id=job_id,
            status=JobStatus.COMPLETED,
            job_type="unknown",
        )

    async def wait_for_job(
        self,
        job_id: str,
        timeout_seconds: int = 1800,
        poll_interval: int = 10,
    ) -> JobInfo:
        """Wait returns immediately for mock."""
        return await self.get_job_status(job_id)

    async def submit_profile_job(
        self,
        model_url: str,
        device_name: str,
    ) -> str:
        """Submit mock profile job."""
        self._job_counter += 1
        job_id = f"mock-profile-{self._job_counter}"
        self._jobs[job_id] = JobInfo(
            job_id=job_id,
            status=JobStatus.COMPLETED,
            job_type="profile",
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            metrics={
                "inference_time_ms": 12.5,
                "peak_memory_mb": 45.2,
                "compute_units": {
                    "npu": 85.0,
                    "gpu": 10.0,
                    "cpu": 5.0,
                },
            },
        )
        return job_id

    async def get_profile_results(self, job_id: str) -> ProfileResult:
        """Get mock profile results."""
        job = self._jobs.get(job_id)
        return ProfileResult(
            job_id=job_id,
            status=JobStatus.COMPLETED,
            metrics=job.metrics if job and job.metrics else {
                "inference_time_ms": 12.5,
                "peak_memory_mb": 45.2,
            },
        )

    async def submit_inference_job(
        self,
        model_url: str,
        device_name: str,
        inputs: Dict[str, Any],
    ) -> str:
        """Submit mock inference job."""
        self._job_counter += 1
        job_id = f"mock-inference-{self._job_counter}"
        self._jobs[job_id] = JobInfo(
            job_id=job_id,
            status=JobStatus.COMPLETED,
            job_type="inference",
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        return job_id

    async def get_inference_results(self, job_id: str) -> InferenceResult:
        """Get mock inference results."""
        return InferenceResult(
            job_id=job_id,
            status=JobStatus.COMPLETED,
            outputs={"output_0": [[0.1, 0.2, 0.7]]},
            timing={"inference_ms": 12.5},
        )
