"""DB table to keep Satellite's altitude updates."""
from datetime import datetime

from sqlalchemy import Column, Integer, DateTime, Float

from moon_leasing.db.config import Base


class SatelliteStatusTable(Base):
    __tablename__ = "satellite_status"

    id = Column(Integer, primary_key=True)
    last_updated = Column(DateTime, nullable=False, index=True, unique=True)
    altitude = Column(Float, nullable=False)
    # retrieved = Column(DateTime(timezone=False), onupdate=func.now())
    # retrieved = Column(DateTime(timezone=False), onupdate=func.current_timestamp())
    retrieved = Column(DateTime(timezone=False), default=datetime.utcnow())

    def __repr__(self):
        return str(self.__dict__)

    def __str__(self):
        since = datetime.utcnow() - self.last_updated
        return (
            f"dt: {self.last_updated} alt:{repr(self.altitude)} (rtr: {self.retrieved})"
            + (
                f"----> (Updated {since.total_seconds()//60}:{since.total_seconds()%60:5.2f} ago)"
            )
        )
