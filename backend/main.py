from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.database import create_db_and_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(title="Gaindalf", lifespan=lifespan)

# Serve frontend static files
app.mount("/static", StaticFiles(directory="frontend", html=True), name="static")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(_: str):
    return FileResponse("frontend/index.html")
