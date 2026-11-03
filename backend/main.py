"""Front door of the API (same role as app.py in the Flask example).

Each ribbon tab has ONE routes file in routes/ (a "blueprint").
To add a tab: create routes/<tab>_routes.py + services/<tab>_service.py,
then register the router in the list below.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from routes.analysis_routes import analysis_router
from routes.file_routes import file_router
from routes.terrain_editing_routes import terrain_editing_router
from routes.terrain_mosaic_routes import terrain_mosaic_router
from routes.tools_routes import tools_router
from routes.view_routes import view_router
from shared.errors import register_error_handlers
from shared.jobs import jobs
from shared.logging import setup_logging

log = logging.getLogger("terrain")

# (name, router) - the order here is the order shown in /docs
BLUEPRINTS = [
    ("file", file_router),
    ("view", view_router),
    ("analysis", analysis_router),
    ("tools", tools_router),
    ("terrain_editing", terrain_editing_router),
    ("terrain_mosaic", terrain_mosaic_router),
]


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        settings.ensure_dirs()
        log.info("%s %s ready - blueprints: %s", settings.app_name, settings.app_version,
                 ", ".join(app.state.modules))
        yield

    app = FastAPI(title=settings.app_name, version=settings.app_version, debug=settings.debug,
                  lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_methods=["*"], allow_headers=["*"])
    register_error_handlers(app)

    for _, router in BLUEPRINTS:                      # register_blueprint equivalent
        app.include_router(router, prefix=settings.api_prefix)
    app.state.modules = [name for name, _ in BLUEPRINTS]

    def _health():
        return {"status": "ok", "version": settings.app_version, "modules": app.state.modules}

    # /health kept for terrain_client; /api/v1/health matches the supervisor's example
    app.add_api_route("/health", _health, methods=["GET"], tags=["System"])
    app.add_api_route(f"{settings.api_prefix}/health", _health, methods=["GET"], tags=["System"])

    @app.get(f"{settings.api_prefix}/jobs", tags=["System"])
    def list_jobs():
        return [j.to_dict() for j in jobs.list()]

    @app.get(f"{settings.api_prefix}/jobs/{{job_id}}", tags=["System"])
    def get_job(job_id: str):
        return jobs.get(job_id).to_dict()

    return app


app = create_app()
