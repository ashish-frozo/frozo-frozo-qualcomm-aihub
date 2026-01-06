"""
Pytest configuration and fixtures for all tests.
"""

import os
import sys
from pathlib import Path

import pytest


# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "aihub: marks tests requiring AI Hub credentials"
    )
    config.addinivalue_line(
        "markers", "integration: marks integration tests"
    )
    config.addinivalue_line(
        "markers", "security: marks security-focused tests"
    )


def pytest_collection_modifyitems(config, items):
    """Skip AI Hub tests if credentials are not available."""
    skip_aihub = pytest.mark.skip(
        reason="QAIHUB_API_TOKEN not set - skipping AI Hub integration tests"
    )

    for item in items:
        if "aihub" in item.keywords:
            if not os.environ.get("QAIHUB_API_TOKEN"):
                item.add_marker(skip_aihub)


@pytest.fixture
def project_root():
    """Return project root path."""
    return PROJECT_ROOT


@pytest.fixture
def schemas_dir(project_root):
    """Return schemas directory path."""
    return project_root / "schemas"


@pytest.fixture
def probe_models_dir(project_root):
    """Return probe_models directory path."""
    return project_root / "edgegate" / "probe_models"
