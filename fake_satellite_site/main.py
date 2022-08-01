import random
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "/api/satellite/data</a>"}


@app.get("/api/satellite/move/{direction}")
async def move_satellite(direction):
    """Change satellite's altitude by a specific value"""
    if str(direction).lower() == "up":
        direction = 15
    elif str(direction).lower() == "down":
        direction = -15
    return make_new_data(direction=direction, sigma=0)


@app.get("/api/satellite/up")
async def nudge_satellite_upwards():
    return make_new_data(direction=10)


@app.get("/api/satellite/down")
async def nudge_satellite_downwards():
    return make_new_data(direction=-10)


@app.get("/api/satellite/data/{date_str}/{altitude}")
async def move_satellite_to_altitude(date_str: str, altitude: int):
    return make_new_data(now_str=date_str, altitude=altitude)


@app.get("/api/satellite/data")
async def fake_satellite_data():
    return make_new_data()


def make_new_data(now_str="", altitude=None, direction: float = 0, sigma=20):
    """Generate new date_string and altitude."""
    filename = Path(__file__).resolve().parent / "tmp_last_date.txt"
    log_filename = Path(__file__).resolve().parent / "tmp_last_date_log.txt"
    action = "given"
    if altitude is None:
        altitude = 213.001
        action = "default"

        if filename.exists():
            action = "calc"
            with filename.open() as fp:
                now_str, altitude, *_rest = fp.read().split()
                if direction or random.randint(0, 100) < 95:
                    action = f"direction:{direction}"
                    altitude = float(altitude) + float(direction)
                    if sigma:
                        altitude = random.gauss(mu=altitude, sigma=sigma)

    if not now_str or now_str.lower() in ["now", "0"]:
        now = datetime.utcnow()
        now_str = now.isoformat(sep="T") + "Z"

    with filename.open("w") as fp:
        fp.write(f"{now_str} {altitude} {action}")
    with log_filename.open("a") as fp:
        fp.write(f"{now_str} {float(altitude):012.8f} {action}\n")
    # sample_datetime = "2017-04-07T02:53:10.000Z"

    return {
        "last_updated": now_str,
        "altitude": f"{altitude}",
        "": action,
    }
    # return {
    #     "last_updated": "2017-04-07T02:53:10.000Z",
    #     "altitude": "213.001"
    # }
