from pydantic import BaseModel
from datetime import datetime


class AltitudeData(BaseModel):
    last_updated: datetime
    altitude: float
