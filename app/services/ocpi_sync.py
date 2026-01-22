import httpx
from sqlalchemy.orm import Session
from sqlmodel import select
from app.models.partner import PartnerProfile, PartnerRole
from app.models.location import Location
from app.api.v2_1_1.locations import process_location

class OCPISyncService:
    def __init__(self, session: Session):
        self.session = session

    async def sync_all_cpos(self):
        # 1. Find all active CPOs
        statement = select(PartnerProfile).where(PartnerProfile.role == PartnerRole.CPO)
        cpos = self.session.exec(statement).all()

        async with httpx.AsyncClient() as client:
            for cpo in cpos:
                print(f"Starting sync for: {cpo.party_id}")
                await self.sync_single_cpo(client, cpo)

    async def sync_single_cpo(self, client: httpx.AsyncClient, cpo: PartnerProfile):
        # 2. Get the Locations endpoint (In a real app, you'd fetch this from the Versions URL)
        # For now, let's assume you've stored the specific locations_url in the profile
        locations_url = f"{cpo.versions_url}/locations"

        headers = {
            "Authorization": f"Token {cpo.token_c}",
            "Content-Type": "application/json"
        }

        try:
            response = await client.get(locations_url, headers=headers)
            response.raise_for_status()
            payload = response.json()

            # OCPI data is usually in the 'data' field
            locations_data = payload.get("data", [])

            for loc_raw in locations_data:
                # 3. Use the logic we built earlier to inject country/party and save
                # We pass the session and the raw data to your processing function
                await self.process_and_save_location(loc_raw, cpo, self.session)

            print(f"Successfully synced {len(locations_data)} locations for {cpo.party_id}")

        except Exception as e:
            print(f"Failed to sync {cpo.party_id}: {str(e)}")

    async def process_and_save_location(self, raw_data: dict, cpo: PartnerProfile, session: Session):
        # Inject the ownership codes from the Profile
        raw_data["country_code"] = cpo.country_code
        raw_data["party_id"] = cpo.party_id

        loc_id = raw_data.get("id")

        process_location(cpo.country_code, cpo.party_id, loc_id, raw_data, session)