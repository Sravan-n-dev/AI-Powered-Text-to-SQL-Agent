import logging

from fastapi import FastAPI

from app.api.routes import router
from app.config import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="AI-Powered Text-to-SQL Agent",
    description="Multi-agent natural language to SQL system running entirely on local, free infrastructure.",
    version="0.1.0",
)

app.include_router(router)


@app.get("/")
def root():
    return {
        "message": "Text-to-SQL Agent API is running.",
        "docs": "/docs",
        "try": "POST /ask with {\"question\": \"...\"}",
    }
