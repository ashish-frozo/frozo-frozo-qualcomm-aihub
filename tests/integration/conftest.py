"""
Integration test fixtures.

Provides test client and mock data for API testing.
"""

import os
import pytest
from httpx import AsyncClient, ASGITransport

# Set test environment before importing app
os.environ["APP_ENV"] = "development"
os.environ["EDGEGENAI_MASTER_KEY"] = "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXRlc3Rpbmc="
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-for-testing"


@pytest.fixture
async def async_client():
    """Create async test client for API testing."""
    # Import app inside fixture to ensure env vars are set first
    from edgegate.api.main import app
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def test_user_data():
    """Sample user data for registration."""
    return {
        "email": "test@example.com",
        "password": "TestPassword123!",
        "name": "Test User",
    }


@pytest.fixture
def test_workspace_data():
    """Sample workspace data."""
    return {
        "name": "Test Workspace",
        "description": "A workspace for testing",
    }


@pytest.fixture
def test_pipeline_data():
    """Sample pipeline data."""
    return {
        "name": "Test Pipeline",
        "description": "A test pipeline",
        "devices": ["samsung_galaxy_s23"],
        "gates": [
            {
                "metric": "latency_ms_median",
                "operator": "<=",
                "threshold": 100.0,
            }
        ],
    }
