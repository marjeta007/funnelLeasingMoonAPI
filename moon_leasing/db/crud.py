"""CRUD operations for SatelliteStatusTable"""
import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Union

# from sqlalchemy import update
import dateutil.parser

from sqlalchemy import desc
from sqlalchemy.future import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from moon_leasing.db.config import async_session
from moon_leasing.db.models.satellite import SatelliteStatusTable
from moon_leasing.settings import Settings

logger = Settings.get_logger(__name__)


class SatelliteDB:
    """CRUD operations for SatelliteStatusTable"""

    count = 0

    def __init__(self, db_session: Optional[Session] = None):
        self.db_session = db_session or async_session

    @staticmethod
    def to_naive_datetime(date_str: Union[str, datetime]) -> datetime:
        """Convert given value to naive UTC datetime (time in UTC without timezone info)."""
        if isinstance(date_str, str):
            date_obj = dateutil.parser.parse(date_str)
        elif isinstance(date_str, datetime):
            date_obj = date_str
        else:
            date_obj = datetime(date_str)

        if date_obj.tzinfo:
            # Calling .astimezone on a naive object, assumes it's in current timezone
            return date_obj.astimezone(timezone.utc).replace(tzinfo=None)
        return date_obj

    async def create_entry(
        self, last_updated: Union[str, datetime], altitude: str, **_kwargs
    ):
        """Insert new data record into SatelliteStatusTable."""
        self.__class__.count += 1

        last_updated = self.to_naive_datetime(last_updated)
        os.environ[
            "ins"
        ] = f"{os.environ.get('ins')}\t {last_updated.minute % 10}:{last_updated.second}-{altitude}"
        status = SatelliteStatusTable(
            last_updated=last_updated, altitude=altitude
        )  # , **_kwargs)
        print("----> Creating: ", repr(status))
        try:
            added = self.db_session.add(status)
            print(f"added: {added}")
            flushed = await self.db_session.flush()
            print(f"flushed: {flushed}")
            os.environ["ins"] = f"{os.environ.get('ins')}+"
        except IntegrityError as ex:
            os.environ["ins"] = f"{os.environ.get('ins')}={ex}"
            logger.info(f"Attempted duplicate insert ({ex})")
            # We attempted to insert same altitude reading twice. Ignoring
        except Exception as ex:
            os.environ["ins"] = f"{os.environ.get('ins')}={type(ex)}:{ex}"
            logger.error(f"Error inserting {status} - {type(ex)}:{ex}")
        return status

    async def get_all(self) -> List[SatelliteStatusTable]:
        """Retrieve all records from SatelliteStatusTable."""
        query = await self.db_session.execute(
            select(SatelliteStatusTable).order_by(
                desc(SatelliteStatusTable.last_updated)
            )
        )
        return query.scalars().all()

    async def get_latest(
        self, minutes: Optional[int] = 5
    ) -> List[SatelliteStatusTable]:
        """Retrieve records from the last few minutes (default=5)."""

        if not minutes or minutes < 0:
            return await self.get_all()

        dt_since = datetime.utcnow() - timedelta(minutes=minutes)
        os.environ["get_latest"] = str(dt_since)
        query = await self.db_session.execute(
            select(SatelliteStatusTable)
            .where(SatelliteStatusTable.last_updated >= dt_since)
            .order_by(desc(SatelliteStatusTable.last_updated))
        )
        return query.scalars().all()

    async def get_last_below(
        self, threshold, minutes: Optional[int] = 60 * 24
    ) -> List[SatelliteStatusTable]:
        """Retrieve the latest record with altitude below threshold."""
        minutes = max(minutes, 1)

        dt_since = datetime.utcnow() - timedelta(minutes=minutes)
        os.environ["get_last_below"] = str(dt_since)
        query = await self.db_session.execute(
            select(SatelliteStatusTable)
            .where(
                SatelliteStatusTable.last_updated >= dt_since,
                SatelliteStatusTable.altitude < threshold,
            )
            .order_by(desc(SatelliteStatusTable.last_updated))
        )
        return query.scalars().first()

    async def get_last_above(
        self, threshold, minutes: Optional[int] = 60
    ) -> List[SatelliteStatusTable]:
        """Retrieve the latest record with altitude above threshold."""
        minutes = min(minutes, 1)

        dt_since = datetime.utcnow() - timedelta(minutes=minutes)
        query = await self.db_session.execute(
            select(SatelliteStatusTable)
            .where(
                SatelliteStatusTable.last_updated >= dt_since,
                SatelliteStatusTable.altitude >= threshold,
            )
            .order_by(desc(SatelliteStatusTable.last_updated))
        )
        return query.scalars().first()

    async def get_last_one(self) -> List[SatelliteStatusTable]:
        """Retrieve the most recent record."""
        query = await self.db_session.execute(
            select(SatelliteStatusTable).order_by(
                desc(SatelliteStatusTable.last_updated)
            )
        )
        return query.scalars().first()

    # async def update_entry(self, id: int, last_updated: Union[str, datetime] = "",
    #                        altitude: str = "", **kwargs):
    # """Update..."""
    #     q = update(SatelliteStatusTable).where(SatelliteStatusTable.id == book_id)
    #     if last_updated:
    #         q = q.values(last_updated=last_updated)
    #     if altitude:
    #         q = q.values(altitude=altitude)
    #     q.execution_options(synchronize_session="fetch")
    #     await  self.db_session.execute(q)
