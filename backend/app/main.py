"""
FastAPI entrypoint.

Users and shops are persisted in a real MySQL database — see
backend/db/projectwork_en_v2.sql for the schema+seed data and
app/db/engine.py for the connection. Run with:

    uvicorn app.main:app --reload   (run from inside backend/)

then open http://127.0.0.1:8000/docs for interactive Swagger docs.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from . import storage
from .db.engine import engine
from .routers import admin, auth, boxes, cart, notifications, orders, shops, users

logger = logging.getLogger("toogood.startup")

logger = logging.getLogger("toogood.startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast with a clear message rather than a cryptic error on the
    # first request if the DB isn't reachable/provisioned.
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError as exc:
        logger.error(
            "Could not connect to the database (%s). Is MySQL/MariaDB running, and has "
            "backend/db/projectwork_en_v2.sql been imported? See backend/README.md.",
            exc,
        )
        raise
    yield


app = FastAPI(title="Gran Consiglio / TooGood API", version="0.1.0", lifespan=lifespan)

# Dev-friendly CORS so the Expo app (web / iOS / Android simulator) can call
# the API from any origin during development. Restrict allow_origins before
# deploying to production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(shops.router)
app.include_router(boxes.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(notifications.router)
app.include_router(admin.router)

# Serves uploaded vendor licenses at real, working URLs (see storage.py) —
# the same path this API itself builds StoredFile.url from
# (storage.UPLOAD_URL_PATH), so the two must stay in sync.
app.mount(storage.UPLOAD_URL_PATH, StaticFiles(directory=storage.UPLOAD_DIR), name="license-uploads")


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}
