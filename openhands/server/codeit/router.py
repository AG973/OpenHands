"""CODEIT main router — aggregates all CODEIT sub-routers and initializes the database."""

from fastapi import APIRouter

from openhands.core.logger import openhands_logger as logger
from openhands.server.codeit.database import init_db
from openhands.server.codeit.auth import get_or_create_default_user

from openhands.server.codeit.routes_auth import router as auth_router
from openhands.server.codeit.routes_skills import router as skills_router
from openhands.server.codeit.routes_knowledge import router as knowledge_router
from openhands.server.codeit.routes_prompts import router as prompts_router
from openhands.server.codeit.routes_connectors import router as connectors_router
from openhands.server.codeit.routes_deploy import router as deploy_router
from openhands.server.codeit.routes_uploads import router as uploads_router
from openhands.server.codeit.routes_health import router as health_router
from openhands.server.codeit.routes_models import router as models_router


def get_codeit_routers() -> list[APIRouter]:
    """Initialize CODEIT database and return all routers to be included in the app."""
    try:
        init_db()
        get_or_create_default_user()
        logger.info("CODEIT: Backend initialized — database ready, default user ensured")
    except Exception as e:
        logger.error(f"CODEIT: Failed to initialize database: {e}")

    return [
        auth_router,
        skills_router,
        knowledge_router,
        prompts_router,
        connectors_router,
        deploy_router,
        uploads_router,
        health_router,
        models_router,
    ]
