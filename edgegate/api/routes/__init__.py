"""
API routes package.
"""

from edgegate.api.routes.auth import router as auth_router
from edgegate.api.routes.workspaces import router as workspaces_router
from edgegate.api.routes.integrations import router as integrations_router
from edgegate.api.routes.capabilities import router as capabilities_router
from edgegate.api.routes.promptpacks import router as promptpacks_router
from edgegate.api.routes.pipelines import router as pipelines_router
from edgegate.api.routes.runs import router as runs_router
from edgegate.api.routes.artifacts import router as artifacts_router
from edgegate.api.routes.ci import router as ci_router
from edgegate.api.routes.health import router as health_router

__all__ = [
    "auth_router",
    "workspaces_router",
    "integrations_router",
    "capabilities_router",
    "promptpacks_router",
    "pipelines_router",
    "runs_router",
    "artifacts_router",
    "ci_router",
    "health_router",
]
