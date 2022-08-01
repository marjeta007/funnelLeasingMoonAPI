"""FastAPI app which provides endpoints for the Satellite stats and health."""
from typing import Dict

from fastapi import FastAPI  # , BackgroundTasks
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi.responses import RedirectResponse

from moon_leasing.db.config import Base, engine
from moon_leasing.settings import Settings
from moon_leasing.space import SatelliteData

logger = Settings.get_logger(__name__)

app = FastAPI()


@app.on_event("startup")
async def startup():
    """At server startup: create db tables if needed."""
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all)
        # print("dropped")
        await conn.run_sync(Base.metadata.create_all)
        print("DB table created")


@app.get("/")
async def root():
    return RedirectResponse(url="/docs")


@app.get("/stats")
async def get_stats() -> Dict[str, str]:
    """Returns the minimum, maximum and average altitude for the last 5 minutes."""
    data = await SatelliteData.stats()
    return {"data": data}


@app.get("/health")
async def get_health() -> Dict[str, str]:
    """Returns the health based on altitude 160."""
    data = await SatelliteData.health()
    return {"data": data}


app.scheduler = AsyncIOScheduler()
app.scheduler.add_job(SatelliteData.refresh, "interval", seconds=15)
app.scheduler.start()
