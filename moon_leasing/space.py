import os
import sys
from datetime import datetime, timezone
from typing import Optional

import requests
from dotenv import dotenv_values, find_dotenv, load_dotenv

from moon_leasing.db.config import async_session
from moon_leasing.db.crud import SatelliteDB
from moon_leasing.settings import Settings

my_env = find_dotenv(raise_error_if_not_found=False)
ENV = load_dotenv()

values = dotenv_values()

logger = Settings.main_logger.getChild("space")


class SatelliteData:
    # SATELLITE_REALTIME_URL = "https://nestio.space/api/satellite/data"
    SATELLITE_REALTIME_URL = Settings.SATELLITE_REALTIME_URL
    # os.environ.get("SATELLITE_REALTIME_URL")
    CRITICAL_ALTITUDE = os.environ.get("CRITICAL_ALTITUDE") or 160
    _latest_data = None
    _last_retrieved: Optional[datetime] = None
    db = SatelliteDB()

    messages = {
        "missing": "WARNING: No altitude information available",
        "critical": "WARNING: RAPID ORBITAL DECAY IMMINENT",
        "warning": "Sustained Low Earth Orbit Resumed",
        "ok": "Altitude is A-OK",
    }

    # def __str__(self):
    #     return f"{self.latest_data} (retrieved: {self._last_retrieved})"
    #
    # def __init__(self):
    #     latest_data = self._get_latest_data_list()
    #
    # @property
    # def latest_data(self):
    #     if not self._latest_data:
    #         self.__class__._latest_data = self._get_latest_data_list()
    #         self.__class__._last_retrieved = datetime.utcnow()
    #     return self._latest_data

    @classmethod
    async def stats(cls):
        data = await cls._get_latest_data_list(minutes=5)
        altitudes = [float(item.altitude) for item in data]
        if not altitudes:
            new_entry = await cls.refresh()
            altitudes = [new_entry.altitude]
            print(repr(altitudes))
            # return dict(error="Data not available")
        print(altitudes)
        response = dict(
            minimum=min(altitudes),
            maximum=max(altitudes),
            average=sum(altitudes) / len(altitudes),
            altitudes=altitudes,
            dlen=len(data),
        )
        print(response)
        return response

    @classmethod
    async def health(cls):
        message = cls.messages["ok"]

        data = await cls._get_latest_data_list(minutes=1)
        print(f"HEALTH - Data received: {data}")
        altitudes = [item.altitude for item in data]
        print(f"HEALTH - Altitudes: {altitudes}")
        if not altitudes:
            message = cls.messages["missing"]
        elif min(altitudes) < cls.CRITICAL_ALTITUDE:
            message = cls.messages["critical"]
        else:
            async with async_session() as session:
                async with session.begin():
                    db = SatelliteDB(db_session=session)
                    latest_critical = await db.get_last_below(
                        threshold=cls.CRITICAL_ALTITUDE, minutes=2
                    )
                    logger.debug(f"HEALTH - latest critical: {latest_critical}")
                    if latest_critical:
                        message = cls.messages["warning"]
        logger.debug(f"HEALTH - message: {message}")
        return message

    @classmethod
    async def _get_latest_data_list(cls, **kwargs):
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        if (
            not cls._last_retrieved
            or (datetime.utcnow() - cls._last_retrieved).total_seconds() > 20
        ):
            new_entry = await cls.refresh()
            print(new_entry)
        try:
            async with async_session() as session:
                async with session.begin():
                    db = SatelliteDB(db_session=session)
                    return await db.get_latest(**kwargs)
        except Exception:
            msg = "Can't get data_list!!!"
            logger.exception(msg)
            return []

    @classmethod
    async def refresh(cls):
        data = await cls._get_last_update()

        try:
            async with async_session() as session:
                async with session.begin():
                    db = SatelliteDB(db_session=session)

                    print(f"REFRESH Creating from {repr(data)}")
                    new_entry = await db.create_entry(**data)
                    print(new_entry)
                    cls._last_retrieved = datetime.utcnow()
                    return new_entry

        except Exception as ex:
            logger.exception(f"{type(ex)}: {ex}", exc_info=ex)
            raise

    @classmethod
    async def _get_last_update(cls):
        response = requests.get(cls.SATELLITE_REALTIME_URL)
        data = response.json()
        if data:
            data["last_updated"] = SatelliteDB.to_naive_datetime(data["last_updated"])
            data["altitude"] = float(data["altitude"])
            return data
        return None


if __name__ == "__main__":
    print(SatelliteData.SATELLITE_REALTIME_URL)
