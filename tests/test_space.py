"""Tests for space.py"""
# pylint: disable=missing-function-docstring,missing-class-docstring,wrong-import-position,protected-access

import os
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import dateutil
import pandas as pd

os.environ.update(  # Setup env before importing moon_leasing
    dict(
        TEST_DATABASE_URL="sqlite+aiosqlite:///./temp_test_satellite.db",
        TEST_SATELLITE_REALTIME_URL="https://foo.bar/api/data",
        TEST="true",
    )
)

from moon_leasing.db.config import (
    async_session,
    Base,
    engine,
)
from moon_leasing.db.crud import SatelliteDB
from moon_leasing.settings import Settings
from moon_leasing.space import SatelliteData

logger = Settings.get_logger(__name__)

test_dir = Path(__file__).resolve().parent


df = pd.read_csv(test_dir / "good_data.csv")
good_data = df.to_dict(orient="records")


class MockResponse:  # pylint: disable=too-few-public-methods
    """For simulating HTTP request response."""

    def __init__(
        self, json_data=None, status_code=200, last_updated=None, altitude=None
    ):
        json_data = json_data or {}
        if isinstance(last_updated, datetime):
            last_updated = last_updated.isoformat(sep="T") + "Z"
        json_data["last_updated"] = last_updated or json_data["last_updated"]
        json_data["altitude"] = altitude or json_data["altitude"]
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data


class TestSatellite(unittest.IsolatedAsyncioTestCase):
    mock_requests = None

    @classmethod
    def setUpClass(cls) -> None:
        os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./tmp_test_satellite.db"
        os.environ["SATELLITE_REALTIME_URL"] = "https://foo.baz/api/data"

    def setUp(self) -> None:
        requests_patcher = mock.patch("moon_leasing.space.requests")
        self.mock_requests = requests_patcher.start()
        self.addCleanup(requests_patcher.stop)

        self.mock_requests.get.return_value = MockResponse(
            last_updated="2022-07-27T04:49:37.681136Z", altitude=213
        )

    @staticmethod
    async def reset_db() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
            print("DB table created")
        SatelliteData._last_retrieved = None

    async def test_get_last_update(self):
        sample_data = {"last_updated": "2017-04-07T02:53:10.000Z", "altitude": "200"}
        self.mock_requests.get.return_value = MockResponse(
            json_data=sample_data, status_code=200
        )

        returned_data = await SatelliteData._get_last_update()

        self.assertEqual(sample_data, returned_data)

    # @mock.patch("moon_leasing.space.requests")
    async def test_health_empty(self):
        db = await self.reset_db()
        print(db)
        async with async_session() as session:
            async with session.begin():
                db = SatelliteDB(db_session=session)
                print(db)
                for idx in range(3):
                    self.mock_requests.get.return_value = MockResponse(
                        last_updated="2022-07-27T04:49:37.681136Z", altitude=213
                    )
                    with self.subTest(f"db-empty-{idx}"):
                        health = await SatelliteData.health()
                        print(health)
                        logger.error(health)
                        self.assertEqual(
                            health, "WARNING: No altitude information available"
                        )

                    with self.subTest(f"all-{idx}"):
                        all_data = await db.get_all()
                        logger.error(repr(all_data))
                        self.assertEqual(len(all_data), 1)
                    with self.subTest(f"latest5-{idx}"):
                        latest_data = await db.get_latest(minutes=5)
                        logger.error(latest_data)
                        self.assertEqual(len(latest_data), 0)

    async def test_health(self):
        ok_msg = "Altitude is A-OK"
        warn_msg = "Sustained Low Earth Orbit Resumed"
        critical_msg = "WARNING: RAPID ORBITAL DECAY IMMINENT"
        examples = [
            SimpleNamespace(secs=[0], alts=[160], health=ok_msg),
            SimpleNamespace(
                secs=[0, 5, 20, 50, 100, 300],
                alts=[160, 200, 160.001, 300, 160],
                health=ok_msg,
            ),
            SimpleNamespace(
                secs=[0, 5, 20, 50, 61, 120.1],
                alts=[160, 200, 160.001, 300, 160, 19],
                health=ok_msg,
            ),
            SimpleNamespace(
                secs=[0, 5, 20, 50, 61, 119],
                alts=[160, 200, 160.001, 300, 160, 159.99],
                health=warn_msg,
            ),
            SimpleNamespace(
                secs=[0, 5, 20, 50, 60.001, 62],
                alts=[160, 200, 160.001, 300, 159.99, 300],
                health=warn_msg,
            ),
            SimpleNamespace(
                secs=[0, 5, 20, 50, 59, 62],
                alts=[160, 200, 160.001, 300, 159.99, 300],
                health=critical_msg,
            ),
        ]
        for case in examples:
            print("case -", case)
            case_data = []
            await self.reset_db()
            print(SatelliteData._last_retrieved)
            with self.subTest(f"{case.health[:3]}-{case.alts}-{case.secs}"):
                async with async_session() as session:
                    async with session.begin():
                        db = SatelliteDB(db_session=session)
                        now = datetime.utcnow()
                        for seconds, altitude in zip(case.secs, case.alts):
                            print("---", seconds, altitude)
                            case_data.append(
                                f"==={float(altitude):8.3f} - {now - timedelta(seconds=seconds)}"
                            )
                            await db.create_entry(
                                last_updated=now - timedelta(seconds=seconds),
                                altitude=altitude,
                            )

                        records = await db.get_all()
                        print(records)
                        print("Done Inserting")

                health = await SatelliteData.health()

                logger.debug(health)
                logger.debug(case.health)
                logger.debug(f"1 minute ago: {now - timedelta(minutes=1)}")
                logger.debug("\n".join([repr(item) for item in case_data]))
                if health != case.health:
                    print("!!!!!")
                self.assertEqual(health, case.health)

    async def test_stats(self):  # pylint: disable=line-too-long
        await self.reset_db()
        now = datetime.utcnow()
        for idx, record in enumerate(good_data):
            os.environ["record_row"] = record["row"]
            minutes = record["minutes"]
            last_updated = now - timedelta(minutes=minutes, seconds=record["seconds"])
            os.environ[
                "last_upd"
            ] = f"{os.environ.get('last_upd')}, {last_updated.minute%10}:{last_updated.second}-{record['altitude']}"
            self.mock_requests.get.return_value = MockResponse(
                json_data={
                    "last_updated": last_updated.isoformat(sep="T") + "Z",
                    "altitude": str(record["altitude"]),
                    "idx": idx,
                    "row": str(record["row"]),
                },
                status_code=200,
            )
            await SatelliteData.refresh()
            stats = await SatelliteData.stats()
            name = f"{idx:2}-[{record.get('row')}]-{record.get('minutes')}:{record.get('seconds')}"
            with self.subTest(f"min-{name}"):
                if record["min"] != stats["minimum"]:
                    logger.error(f"\nStats:{repr(stats)}\nrecord:{repr(record)}")
                self.assertAlmostEqual(record["min"], stats["minimum"], 2)
            with self.subTest(f"max-{name}"):
                if record["max"] != stats["maximum"]:
                    logger.error(f"\nStats:{repr(stats)}\nrecord:{repr(record)}")
                self.assertAlmostEqual(record["max"], stats["maximum"], 2)
            with self.subTest(f"avg-{name}"):
                if record["avg"] != stats["average"]:
                    logger.error(f"\nStats:{repr(stats)}\nrecord:{repr(record)}")
                self.assertAlmostEqual(record["avg"], stats["average"], 2)

            async with async_session() as session:
                async with session.begin():
                    db = SatelliteDB(db_session=session)
                    all_data = await db.get_all()
                    latest_data = await db.get_latest(minutes=5)
                    logger.error(f"\nStats:{repr(stats)}\nrecord:{repr(record)}")
                    logger.error(
                        f"\nall data:{repr(all_data)}\nlatest data:{repr(latest_data)}"
                    )

            with self.subTest(f"all-{name}"):
                if record["all"] != len(all_data):
                    print("all data:", "\n".join([str(item) for item in all_data]))
                    print("=====================")
                    logger.error(
                        f"\nStats:{repr(stats)}\nrecord:{repr(record)}\nall data:{repr(all_data)}"
                    )
                self.assertEqual(record["all"], len(all_data))
            if minutes > 4:
                count = 0
            else:
                count = record["count"]
            with self.subTest(f"count-{name}"):
                if count != len(latest_data):
                    logger.error(
                        f"\nStats:{repr(stats)}\nrecord:{repr(record)}\nlatest data:{repr(latest_data)}"
                    )
                self.assertEqual(count, len(latest_data))

        # s = SatelliteData()
        # data = s.latest_data
        # print(data)
        # self.assertEqual(data, [42])

    def test_d(self):
        naive = datetime(2022, 7, 27, 4, 49, 37, 681136)
        utc = datetime(2022, 7, 27, 4, 49, 37, 681136, tzinfo=timezone.utc)

        naive_str = "2022-07-27T04:49:37.681136"
        z_str = "2022-07-27T04:49:37.681136Z"
        utc_str = "2022-07-27T04:49:37.681136+00:00"
        utc_1 = "2022-07-27T05:49:37.681136+01:00"
        utc_2 = "2022-07-27T06:49:37.681136+02:00"
        utc_3 = "2022-07-27T01:49:37.681136-03:00"

        # noinspection PyUnresolvedReferences
        for name, date_in in [
            ("naive", naive),
            ("utc", utc),
            ("naive str", dateutil.parser.parse(naive_str)),
            ("utc str", dateutil.parser.parse(utc_str)),
            ("z str", dateutil.parser.parse(z_str)),
            ("utc +1", dateutil.parser.parse(utc_1)),
            ("utc +2", dateutil.parser.parse(utc_2)),
            ("utc -3", dateutil.parser.parse(utc_3)),
        ]:
            with self.subTest(name):
                print(name, "...", date_in)
                date_obj = SatelliteDB.to_naive_datetime(date_in)
                print(name, "...", date_in, date_obj)
                if date_obj != naive:
                    print("---")
                    print("in :", repr(date_in), "\t", str(date_in))
                    print("obj:", repr(date_obj), "\t", str(date_obj))
                    print("niv:", repr(naive), "\t", str(naive))
                    print("===")
                # self.assertEqual(date_obj, naive)
                self.assertEqual(date_obj.isoformat(), naive_str)


if __name__ == "__main__":
    unittest.main()
