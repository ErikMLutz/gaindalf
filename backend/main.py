from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import backend.models as _models  # noqa: F401 — registers tables with SQLModel metadata
from backend.database import create_db_and_tables
from backend.routers import analytics, lifts, muscle_groups, sets, settings, workouts


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(title="Gaindalf", lifespan=lifespan)

app.include_router(muscle_groups.router, prefix="/api/muscle-groups", tags=["muscle-groups"])
app.include_router(lifts.router, prefix="/api/lifts", tags=["lifts"])
app.include_router(workouts.router, prefix="/api/workouts", tags=["workouts"])
app.include_router(sets.router, prefix="/api", tags=["sets"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])

# Serve frontend static files
app.mount("/static", StaticFiles(directory="frontend", html=True), name="static")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(_: str):
    return FileResponse("frontend/index.html")
