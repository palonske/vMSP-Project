import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session, create_engine, select
from app.database import engine, get_session  # Import your existing engine
from app.models.partner import PartnerProfile, PartnerRole
from app.services.ocpi_sync import OCPISyncService

async def check_database_health():
        print(f"Engine URL: {engine.url}")

        async with engine.connect() as conn:
            tables = await conn.run_sync(
                    lambda sync_conn: inspect(sync_conn).get_table_names()
            )
            print(f"Tables found in DB: {tables}")

async def test_sync():
    # 1. Open a database session
    async with AsyncSession(engine, expire_on_commit=False) as session:
        # 2. Check if you actually have a CPO in the database to test with
        statement = select(PartnerProfile).where(PartnerProfile.role == PartnerRole.CPO)
        result = await session.execute(statement)
        cpo = result.scalars().first()

        if not cpo:
            print("❌ No CPO found in database. Please add a PartnerProfile first.")
            return

        print(f"🚀 Starting test sync for {cpo.party_id} ({cpo.country_code})")

        # 3. Initialize and run the service
        service = OCPISyncService(session)
        await service.sync_all_cpos()

        print("✅ Sync process completed.")

async def main():
    await check_database_health()
    await test_sync()

if __name__ == "__main__":
    from sqlalchemy import inspect

    # Start the async event loop
    asyncio.run(main())