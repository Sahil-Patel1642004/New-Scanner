from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.admin import router as admin_router
from app.api.v1.download import router as download_router
from app.api.v1.customers import router as customers_router
from app.api.v1.email import router as email_router
from app.api.v1.licences import router as licences_router
from app.api.v1.products import router as products_router
from app.core.config import settings
import app.database as database
from app.db.init_db import ensure_admin_user, initialize_database


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if settings.environment.casefold() != "production":
        initialize_database()
    db = database.SessionLocal()
    try:
        ensure_admin_user(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="Prakshal-Scanora Licensing API",
    version="0.1.0",
    description="Secure backend for admin authentication and licensing management.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_router, prefix="/api/v1")
app.include_router(customers_router, prefix="/api/v1")
app.include_router(licences_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.include_router(email_router, prefix="/api/v1")
app.include_router(download_router, prefix="/api/v1")


@app.get("/health")
def health_check() -> dict[str, str]:
    with database.engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok"}
