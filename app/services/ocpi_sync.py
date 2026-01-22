import httpx
from rich.diagnose import report
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
        report = {
            "cpo": f"{cpo.country_code}-{cpo.party_id}",
            "total_received": 0,
            "success_count": 0,
            "failure_count": 0,
            "errors": []  # List of dicts: {"id": "LOC1", "reason": "...", "type": "..."}
        }

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
                report["total_received"] += len(locations_data)

                # 2. Process each location in the current page
                for loc_raw in locations_data:
                    location_id = loc_raw.get("id")
                    try:
                        if not location_id:
                            print(f"⚠️ Skipping location: Missing ID in raw data.")
                            continue

                        with session.begin_nested():
                            await process_and_save_location(loc_raw, cpo, location_id, session)
                            report["success_count"] += 1

                    except Exception as e:
                        print(f"❌ Error processing location {loc_raw.get('id', 'Unknown')}: {e}")

                        report["failure_count"] += 1
                        report["errors"].append({
                            "location_id": location_id,
                            "error_type": type(e).__name__,
                            "details": str(e)[:200] # Cap the message length
                        })

                        continue

                # 3. Handle OCPI Pagination
                # OCPI uses the 'Link' header for the next page: <url>; rel="next"
                next_url = parse_next_link(response.headers.get("Link"))

                print(f"📥 Page processed. Total so far: {report['total_received']} | "
                      f"Success: {report['success_count']} | "
                      f"Failures: {report['failure_count']}")


                # Commit after every page to keep transactions manageable
                session.commit()

            except httpx.HTTPStatusError as e:
                print(f"HTTP Error for {cpo.party_id}: {e.response.status_code}")
                break
            except Exception as e:
                print(f"Unexpected error syncing {cpo.party_id}: {e}")
                break

        print_sync_summary(self,report)



def parse_next_link(link_header: str):
    """Parses 'Link: <url>; rel="next"' header"""
    if not link_header:
        return None
    parts = link_header.split(",")
    for part in parts:
        if 'rel="next"' in part:
            return part.strip().split(";")[0].strip("<>")
    return None

def print_sync_summary(self, report):
    print("\n" + "="*40)
    print(f"SYNC SUMMARY: {report['cpo']}")
    print(f"Total Processed: {report['total_received']}")
    print(f"✅ Success:      {report['success_count']}")
    print(f"❌ Failed:       {report['failure_count']}")
    print("="*40)

    if report["errors"]:
        print("\nDETAILED ERRORS:")
        for err in report["errors"][:10]: # Show first 10
            print(f"- [{err['location_id']}] {err['error_type']}: {err['details']}")

        if len(report["errors"]) > 10:
            print(f"... and {len(report['errors']) - 10} more errors.")
    print("="*40 + "\n")

async def process_and_save_location(raw_data: dict, cpo: PartnerProfile, loc_id, session: Session):
    # Inject the ownership codes from the Profile
    raw_data["country_code"] = cpo.country_code
    raw_data["party_id"] = cpo.party_id

    process_location(cpo.country_code, cpo.party_id, loc_id, raw_data, session)