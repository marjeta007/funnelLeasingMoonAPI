from datetime import datetime

from pydantic import BaseModel


class AltitudeData(BaseModel):  # pylint: disable=too-few-public-methods
    last_updated: datetime
    altitude: float
