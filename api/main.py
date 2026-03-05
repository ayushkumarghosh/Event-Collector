from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from storage.database import init_db
from storage.graph import init_graph
from api.routes import events, stats


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_graph()
    yield


app = FastAPI(title="India Event Collector", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(events.router, prefix="/api/v1")
app.include_router(stats.router, prefix="/api/v1")

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
