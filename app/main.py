# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .config import config
from .logger import get_logger
from .api.routes import router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info(f"Starting {config.app_name} v{config.app_version}")
    logger.info(f"Environment: {config.environment}")
    logger.info(f"LLM Provider: {config.llm_provider}")
    logger.info(f"Debug mode: {config.debug}")
    yield
    logger.info("Shutting down application")


# Create FastAPI app
app = FastAPI(
    title=config.app_name,
    version=config.app_version,
    lifespan=lifespan,
    docs_url="/docs" if config.debug else None,
    redoc_url="/redoc" if config.debug else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
    )