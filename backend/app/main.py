"""
FastAPI entrypoint.

There is no real database yet: app.database.db is an in-memory store seeded
with a few fictitious demo accounts (seed_fake_data()) so the whole API is
exercisable end-to-end without any external service. Run with:

    uvicorn app.main:app --reload   (run from inside backend/)

then open http://127.0.0.1:8000/docs for interactive Swagger docs.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import seed_fake_data
from .routers import admin, auth, shops, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_fake_data()
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
app.include_router(admin.router)


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}
