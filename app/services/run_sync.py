import asyncio
from sqlmodel import Session, create_engine, select
from app.database import engine, get_session  # Import your existing engine
from app.models.partner import PartnerProfile, PartnerRole
from app.services.ocpi_sync import OCPISyncService

async def test_sync():
    # 1. Open a database session
    with Session(engine) as session:
        # 2. Check if you actually have a CPO in the database to test with
        statement = select(PartnerProfile).where(PartnerProfile.role == PartnerRole.CPO)
        cpo = session.exec(statement).first()

        if not cpo:
            print("❌ No CPO found in database. Please add a PartnerProfile first.")
            return

        print(f"🚀 Starting test sync for {cpo.party_id} ({cpo.country_code})")

        # 3. Initialize and run the service
        service = OCPISyncService(session)
        await service.sync_all_cpos()

        print("✅ Sync process completed.")

if __name__ == "__main__":
    from sqlalchemy import inspect

    inspector = inspect(engine)
    print(f"Engine URL:  {engine.url}")
    print(f"Tables found in DB: {inspector.get_table_names()}")

    # Start the async event loop
    asyncio.run(test_sync())