from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.api.routes import router
from app.core.config import settings
from scripts.rebuild_station_index import rebuild_station_index

app = FastAPI(title=settings.app_name, version="1.0.0")


@app.on_event("startup")
def startup_event() -> None:
    rebuild_station_index()


app.include_router(router, prefix="/api")
app.mount("/static", StaticFiles(directory=str(Path(__file__).resolve().parent / "static")), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(Path(__file__).resolve().parent / "templates" / "index.html")
