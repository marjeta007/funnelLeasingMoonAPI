from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from moon_leasing.settings import Settings

logger = Settings.get_logger(__name__)

engine = create_async_engine(Settings.DATABASE_URL, future=True, echo=True)

async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

Base = declarative_base()

# def get_db():
#     """
#     Get the database session
#     Yields:
#         Session: The database session
#     """
#     db = async_session
#     try:
#         yield db
#     finally:
#         db.close()
