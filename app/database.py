import asyncio
from sqlalchemy.testing import future
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
import os

# 1. IMPORT EVERYTHING
# This registers the tables in SQLModel's metadata registry
from app.models.location import Location
from app.models.evse import EVSE
from app.models.connector import Connector

# 2. SETUP ENGINE
sqlite_file_name = "database.db"
sqlite_url = f"sqlite+aiosqlite:////Users/ericpalonsky/IdeaProjects/emspProjectv1/app/{sqlite_file_name}"

# echo=True prints the SQL to your terminal so you can see the tables being created
engine = create_async_engine(sqlite_url, echo=False, future=True)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def create_db_and_tables():
    print("Creating database and tables...")

    # 1. Handle File Cleanup (Optional)
    if os.path.exists(sqlite_file_name):
        os.remove(sqlite_file_name)
        print(f"Deleted old {sqlite_file_name}")

    # 2. Use the Async Engine to run the sync metadata create
    async with engine.begin() as conn:
        print("Creating fresh tables...")
        # run_sync takes the function name, then the arguments
        await conn.run_sync(SQLModel.metadata.create_all)

    print("Done!")

async def get_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session

if __name__ == "__main__":
    asyncio.run(create_db_and_tables())