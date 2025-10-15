# app/main.py
import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import module routers
from .plm_leaderboard import router as plm_router
from .plm_leaderboard import init_plm_leaderboard_dependencies

from .utils import str2bool, Constants


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    USE_BACKUP_DATA = False
    backup_data_path = Path("data/leaderboard-backup-24-03-2025.yml") if USE_BACKUP_DATA else None

    # Initialize PLM Leaderboard module
    #init_plm_leaderboard_dependencies(backup_data=backup_data_path)

    yield

    # Shutdown - cleanup if needed
    pass


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    app = FastAPI(
        title="Biocentral Public Hub Services",
        description="API for biocentral services",
        version="1.0.1",
        lifespan=lifespan
    )

    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include module routers
    app.include_router(plm_router, prefix="/api/v1")

    # Health check
    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}

    return app

app = create_app()


def run_server():
    """Run the server"""
    debug = str2bool(str(os.environ.get('SERVER_DEBUG', 'True')))

    import uvicorn

    if debug:
        # For development with reload - must use string
        uvicorn.run(
            "public_hub_services.main:app",
            host="0.0.0.0",
            port=Constants.SERVER_DEFAULT_PORT,
            reload=True,
            log_level="info"
        )
    else:
        # For production
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=Constants.SERVER_DEFAULT_PORT,
            log_level="info"
        )


if __name__ == "__main__":
    run_server()