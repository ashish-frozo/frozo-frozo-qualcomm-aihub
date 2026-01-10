"""
Integration tests for AI Hub client.

These tests require a valid QAIHUB_API_TOKEN environment variable.
They will be automatically skipped if the token is not set.
"""

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.aihub]


class TestAIHubClient:
    """Test AI Hub client integration."""

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test AI Hub client can be initialized."""
        import os
        from edgegate.aihub.client import QAIHubClient

        token = os.environ.get("QAIHUB_API_TOKEN")
        if not token:
            pytest.skip("QAIHUB_API_TOKEN not set")

        client = QAIHubClient(token)
        assert client is not None

    @pytest.mark.asyncio
    async def test_list_devices(self):
        """Test listing available devices."""
        import os
        from edgegate.aihub.client import QAIHubClient

        token = os.environ.get("QAIHUB_API_TOKEN")
        if not token:
            pytest.skip("QAIHUB_API_TOKEN not set")

        client = QAIHubClient(token)
        devices = client.list_devices()
        
        assert isinstance(devices, list)
        # AI Hub should have at least some devices
        assert len(devices) > 0

    @pytest.mark.asyncio
    async def test_device_attributes(self):
        """Test device objects have required attributes."""
        import os
        from edgegate.aihub.client import QAIHubClient

        token = os.environ.get("QAIHUB_API_TOKEN")
        if not token:
            pytest.skip("QAIHUB_API_TOKEN not set")

        client = QAIHubClient(token)
        devices = client.list_devices()
        
        if devices:
            device = devices[0]
            # Devices should have name attribute
            assert hasattr(device, "name") or hasattr(device, "display_name")


class TestAIHubJobSubmission:
    """Test AI Hub job submission (requires real credentials)."""

    @pytest.mark.asyncio
    async def test_compile_job_validation(self):
        """Test that compile job validates inputs."""
        import os
        from edgegate.aihub.client import QAIHubClient

        token = os.environ.get("QAIHUB_API_TOKEN")
        if not token:
            pytest.skip("QAIHUB_API_TOKEN not set")

        client = QAIHubClient(token)
        
        # Attempting to compile with invalid model should raise error
        with pytest.raises(Exception):
            client.submit_compile_job(
                model_path="/nonexistent/model.onnx",
                device="invalid_device",
            )
