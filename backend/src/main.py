"""Contract Review Tool - FastAPI backend entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.config import get_log_level
from src.services.db_service import close_db_pool

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(level=get_log_level(), format=LOG_FORMAT)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    logger.info("[MAIN] Starting Contract Review Tool...")
    yield
    await close_db_pool()
    logger.info("[MAIN] Shutting down...")


app = FastAPI(
    title="Contract Review Tool",
    description="Local AI-powered contract review with Ollama (Qwen3:8b)",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Contract Review Tool",
        "version": "0.1.0",
        "description": "Local AI-powered contract review with Ollama (Qwen3:8b)",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=get_log_level().lower(),
    )
