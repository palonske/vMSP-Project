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

        async with httpx.AsyncClient(timeout=60.0) as client:
            for cpo in cpos:
                print(f"Starting sync for: {cpo.party_id}")
                await self.sync_single_cpo(client, cpo, self.session)

    async def sync_single_cpo(self, client: httpx.AsyncClient, cpo: PartnerProfile, session: Session):
        # 1. Start with the base locations URL from the profile
        # Note: OCPI paths usually end in /locations
        print(f"Calling CPO with versions_url base:  {cpo.versions_url}")
        next_url = f"{cpo.versions_url.rstrip('/')}/locations"

        headers = {
            "Authorization": f"Token {cpo.token_c}",
            "Content-Type": "application/json"
        }

        while next_url:
            print(f"Fetching: {next_url}")
            try:
                response = await client.get(next_url, headers=headers)
                response.raise_for_status()

                payload = response.json()
                locations_data = payload.get("data", [])

                # 2. Process each location in the current page
                for loc_raw in locations_data:
                    location_id = loc_raw.get("id")
                    if not location_id:
                        continue

                    await process_and_save_location(loc_raw, cpo, location_id, session)

                # 3. Handle OCPI Pagination
                # OCPI uses the 'Link' header for the next page: <url>; rel="next"
                next_url = parse_next_link(response.headers.get("Link"))

                # Commit after every page to keep transactions manageable
                session.commit()

            except httpx.HTTPStatusError as e:
                print(f"HTTP Error for {cpo.party_id}: {e.response.status_code}")
                break
            except Exception as e:
                print(f"Unexpected error syncing {cpo.party_id}: {e}")
                break

def parse_next_link(link_header: str):
    """Parses 'Link: <url>; rel="next"' header"""
    if not link_header:
        return None
    parts = link_header.split(",")
    for part in parts:
        if 'rel="next"' in part:
            return part.strip().split(";")[0].strip("<>")
    return None

async def process_and_save_location(raw_data: dict, cpo: PartnerProfile, loc_id, session: Session):
    # Inject the ownership codes from the Profile
    raw_data["country_code"] = cpo.country_code
    raw_data["party_id"] = cpo.party_id

    process_location(cpo.country_code, cpo.party_id, loc_id, raw_data, session)