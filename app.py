# -*- coding: utf-8 -*-
"""
Main FastAPI WebApp Backend Entrypoint for UNO.
Provides REST APIs and WebSockets for modes, decks, gameplay, and leaderboards.
"""

import os
import shutil
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

class CachedStaticFiles(StaticFiles):
    """Static file handler that adds Cache-Control headers for optimal session caching."""
    async def get_response(self, path: str, scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "public, max-age=86400"
        return response

from db.mongo_client import get_database, close_database
from api.modes_api import router as modes_router
from api.deck_api import router as deck_router
from api.leaderboard_api import router as leaderboard_router
from api.game_api import router as game_router
from api.websocket_api import router as ws_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("uno_webapp")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan handler for initializing DB connections, assets sync, and cleanup."""
    logger.info("Initializing UNO WebApp backend...")
    
    # Sync static images to front-end/public/images for local frontend serving
    try:
        src_images = "images"
        dest_images = os.path.join("front-end", "public", "images")
        if os.path.exists(src_images):
            shutil.copytree(
                src_images,
                dest_images,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(
                    "*.py",
                    "*.pyc",
                    "*.sh",
                    "__pycache__",
                ),
            )
            # Remove source scripts copied by older startup versions.
            for root, _, files in os.walk(dest_images):
                for filename in files:
                    if filename.endswith((".py", ".pyc", ".sh")):
                        try:
                            os.remove(os.path.join(root, filename))
                        except OSError:
                            logger.debug("Could not remove stale synced file: %s", filename)
            logger.info("Synced static images to front-end/public/images")
    except Exception as e:
        logger.warning("Failed to sync images to front-end/public/images: %s", e)

    db = get_database()
    if db is not None:
        logger.info("MongoDB client connected successfully.")
    else:
        logger.warning("MongoDB client unavailable; check environment configuration.")
    yield
    logger.info("Shutting down UNO WebApp backend...")
    await close_database()
    logger.info("Cleanup completed.")


app = FastAPI(
    title="UNO WebApp Backend API",
    description="REST & WebSocket API Backend for UNO Web Application",
    version="2.0.0",
    lifespan=lifespan,
)

# Enable CORS for cross-origin frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("UNO_ALLOWED_ORIGINS", "http://localhost:8080").split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# Mount Static Files for Card Images with Cache-Control headers
app.mount("/images", CachedStaticFiles(directory="images"), name="images")

# Include Routers
app.include_router(modes_router)
app.include_router(deck_router)
app.include_router(leaderboard_router)
app.include_router(game_router)
app.include_router(ws_router)
app.mount("/static", StaticFiles(directory="front-end"), name="frontend-static")


@app.get("/")
async def root():
    index_path = os.path.join("front-end", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "online", "service": "UNO WebApp Backend Engine", "docs": "/docs"}


@app.get("/health")
async def health_check():
    db = get_database()
    return {
        "status": "healthy",
        "database": "connected" if db is not None else "disconnected",
    }


@app.get("/app.js", include_in_schema=False)
async def frontend_script():
    return FileResponse(os.path.join("front-end", "app.js"), media_type="application/javascript")


@app.get("/styles.css", include_in_schema=False)
async def frontend_styles():
    return FileResponse(os.path.join("front-end", "styles.css"), media_type="text/css")


@app.get("/favicon.svg", include_in_schema=False)
async def frontend_favicon():
    return FileResponse(os.path.join("front-end", "favicon.svg"), media_type="image/svg+xml")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(os.path.join("front-end", "favicon.svg"), media_type="image/svg+xml")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["front-end"],
    )
