from fastapi import APIRouter, Depends, Header, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
from sqlmodel import select, delete
from typing import Optional, List
from app.api.v2_1_1.schemas import PartnerSchema, InternalRegister
from app.config import settings
import secrets
from app.database import get_session
from app.models.partner import PartnerProfile, Endpoint
from app.core.utils import get_timestamp, fix_date


router = APIRouter()


@router.post("/manual_register")
async def manual_register_api(
        token_b: str = Body(...),
        token_c: str = Body(...),
        country_code: str = Body(...),
        party_id: str = Body(...),
        role: str = Body(...),
        registered_version: str = Body(...),
        status: str = Body(...),
        versions_url: str = Body(...),
        session: AsyncSession = Depends(get_session),
        endpoints: List[Endpoint] = List[Body(None)],
        token_a: str | None = Body(None),
        authorization: str = Header(None)

):
    new_partner = PartnerProfile(token_a=token_a, token_b=token_b, token_c=token_c,
                                 country_code=country_code, party_id=party_id, versions_url=versions_url,
                                 registered_version=registered_version,
                                 status=status, endpoints=endpoints, role=role)

    registration_success = await manual_registration(session, new_partner, endpoints)

    if registration_success:
        return {
            "status_code": 1000,
            "status_message": "Success",
            "data": {
                f"{new_partner}"
            }
        }
    else:
        return {
            "status_code": 4000,
            "status_message": "ERROR",
            "data": {
                "A Processing Error has Occurred."
            }
        }

@router.post("/internal_msp_register")
async def create_token_a(
        authorization: str = Header(None),
        session: AsyncSession = Depends(get_session)
):
    token_a = secrets.token_hex(16)
    base = settings.BASE_URL.rstrip("/")

    partner = PartnerProfile(
        token_a=token_a,
        country_code="TB",
        party_id="000",
        role="EMSP",
        status="REGISTERED",
        versions_url="www.tbd.com",
        registered_version="T.B.D"
    )

    while await is_partner_registered(session,partner.country_code, partner.party_id, partner.role):
        old_party_id = int(partner.party_id)
        new_party_id = str(old_party_id + 1).zfill(3)
        partner.party_id = new_party_id

    print(f"Creating Token A {partner.token_a}, for temporary partner {partner.party_id}")

    session.add(partner)
    await session.commit()

    return {
        "status_code": 1000,
        "status_message": "Success",
        "data": {
            "Token A": f"{partner.token_a}",
            "Versions URL": f"{base}/ocpi/cpo/2.1.1"
        }
    }

@router.post("/internal_cpo_register")
async def credentials_handshake(
        token_a: str,
        versions_url: str,
        authorization: str = Header(None),
        session: AsyncSession = Depends(get_session)
):
    # 1. Verify Authorization (The temporary TOKEN_A)
    # In a real app, you'd check this against a 'Registration' table
    #if not authorization or "Token" not in authorization:
    # raise HTTPException(status_code=401, detail="Missing Token A")
    creds_in = InternalRegister(token_a=token_a, versions_url=versions_url)
    #1. Call CPO Version Endpoint
    print(f"Calling versions url: {versions_url} with token {token_a}.")
    versions = await fetch_cpo_versions(creds_in.versions_url, creds_in.token_a)
    creds_in = await select_cpo_version(creds_in, versions)

    if creds_in.version_detail_url:
        credentials_url = await fetch_credentials_details(creds_in)
    else:
        return {
            "status_code": 400,
            "status_message": "No Matching Versions"
        }

    # 2. Perform Registration
    partner = await perform_registration(session, credentials_url, creds_in)

    # 3. Create the Database record



    # 4. Respond with your details
    if partner:
        return {
            "status_code": 1000,
            "status_message": "Success",
            "timestamp": get_timestamp(),
            "data": {
                f"{partner}"
            }
        }
    else:
        return {
            "status_code": 4000,
            "status_message": "ERROR",
            "data": {
                "A Processing Error has Occurred."
            }
        }


async def fetch_cpo_versions(versions_url: str, token_a: str) -> List[dict]:
    """
    Calls the CPO's Versions endpoint to see what they support.
    """
    headers = {
        "Authorization": f"Token {token_a}",
        "Content-Type": "application/json",
    }

    print(f"Calling Versions: {versions_url}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(versions_url, headers=headers)
            response.raise_for_status()

            payload = response.json()

            # OCPI 2.1.1 standard response wrapper check
            if payload.get("status_code") == 1000:
                versions = payload.get("data", [])
                return versions
            else:
                print(f"OCPI Error: {payload.get('status_message')}")
                return []

        except httpx.HTTPStatusError as e:
            print(f"HTTP Error {e.response.status_code} while fetching versions")
            return []
        except Exception as e:
            print(f"Unexpected error: {e}")
            return []


async def select_cpo_version(creds_in: InternalRegister,versions: List[dict]) -> Optional[InternalRegister]:
    print(f"Finding Version Match from: {versions}")
    for v in versions:
        if v.get("version") == "2.1.1":
            creds_in.version_detail_url = v.get("url")
            creds_in.registered_version = "2.1.1"
            return creds_in
    return None

async def fetch_credentials_details(creds_in: InternalRegister) -> Optional[str]:
    """
    Fetches the module list for a specific version and returns the Credentials endpoint.
    """
    headers = {"Authorization": f"Token {creds_in.token_a}"}

    async with httpx.AsyncClient() as client:
        response = await client.get(creds_in.version_detail_url, headers=headers)

        raw_payload = response.json()
        data = raw_payload.get("data")
        print(f"Found data {data}")

        if isinstance(data, list):
            # If data is a list, the CPO might be sending the endpoints directly
            # (Non-standard but happens) or this is actually the Versions list.
            print("Data is list")
            endpoints = data
        elif isinstance(data, dict):
            # Standard OCPI 2.1.1 Version Details structure
            print("Data is dict")
            endpoints = data.get("endpoints", [])
        else:
            endpoints = []

        #data = response.json().get("data", {})

        #endpoints = data.get("endpoints", [])

        print(f"Found endpoints: {endpoints}")

        for ep in endpoints:
            if ep.get("identifier") == "credentials":
                print(f"Found credentials url: {ep.get("url")}")
                return ep.get("url")
    return None

async def perform_registration(session: AsyncSession, cpo_credentials_url: str, creds_in: InternalRegister) -> Optional[PartnerProfile]:
    # 1. Generate YOUR permanent Token B (16-byte hex is standard)
    token_b = secrets.token_hex(16)

    # 2. Prepare the Registration Body (Your eMSP Details)
    # This is what the CPO stores in THEIR database
    registration_data = {
        "token": token_b,
        "url": f"{settings.BASE_URL}/ocpi/versions",
        "business_details": {
            "name": "Eric's EMSP",
            "website": "https://www.test.com"
        },
        "party_id": "EPS",
        "country_code": "US"
    }

    headers = {
        "Authorization": f"Token {creds_in.token_a}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            creds_in.version_detail_url,
            headers=headers
        )
        if response.status_code not in [200, 201]:
            print(f"Registration Failed: {response.status_code} - {response.text}")
            return None

        data = response.json().get("data", {})
        endpoints = data.get("endpoints", [])

    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f"Sending Registration to: {cpo_credentials_url}")
        response = await client.post(
            cpo_credentials_url,
            json=registration_data,
            headers=headers
        )

        if response.status_code not in [200, 201]:
            print(f"Registration Failed: {response.status_code} - {response.text}")
            return None

        result = response.json()

        # 3. Extract Token B from the response
        # The CPO returns their details, including the token you must use from now on.
        cpo_data = result.get("data", {})
        token_c = cpo_data.get("token")

        print(f"✅ Handshake successful! Received Token C: {token_c}")
        partner = PartnerProfile(
            token_b=token_b,
            token_c=token_c,
            token_a=creds_in.token_a,
            versions_url=creds_in.versions_url,
            business_details=cpo_data.get("business_details"),
            country_code=cpo_data.get("country_code"),
            party_id=cpo_data.get("party_id"),
            role="CPO",
            status="ACTIVE",
            registered_version=creds_in.registered_version
        )

        already_exists = await is_partner_registered(session, partner.country_code, partner.party_id, "CPO")

        if not already_exists:
            session.add(partner)
            await session.commit()

            await save_module_urls(session, partner, endpoints, "2.1.1", "CPO")

            return partner

        elif already_exists:
            print("Partner Already Exists")
            return None
        else:
            return None


async def save_module_urls(
        session: AsyncSession,
        partner: PartnerProfile,
        endpoints: list,
        version: str,
        role: str
):
    """
    Saves or updates the list of module endpoints for a specific partner and version.
    """
    # 1. Clear existing endpoints for this version/partner to avoid duplicates
    # This is safer than trying to match individual IDs
    delete_stmt = delete(Endpoint).where(
        Endpoint.country_code == partner.country_code,
        Endpoint.party_id == partner.party_id,
        Endpoint.version == version
    )
    await session.execute(delete_stmt)
    print(f"Storing these endpoints: {endpoints}")
    # 2. Iterate through the OCPI endpoints list
    for ep in endpoints:
        module_url = Endpoint(
            identifier=ep.get("identifier"),
            version=version,
            country_code=partner.country_code,
            party_id=partner.party_id,
            url=ep.get("url"),
            role="CPO"
        )
        print(f"Storing Module: {module_url.identifier}")
        session.add(module_url)
    print(f"✅ Stored Endpoints Successfully!")
    # 3. Flush to the database (session.commit() usually happens in the main caller)
    await session.flush()
    await session.commit()

async def is_partner_registered(session: AsyncSession, country_code: str, party_id: str, role: str) -> bool:
    """
    Checks the database to see if a partner with this ID already exists.
    """
    print(f"Checking if Party {party_id}, and Country {country_code} exists as {role} in database")
    statement = select(PartnerProfile).where(
        PartnerProfile.country_code == country_code,
        PartnerProfile.party_id == party_id,
        PartnerProfile.role== role
    )
    result = await session.execute(statement)
    partner = result.scalar_one_or_none()

    print(f"Found result: {partner}")

    return partner is not None

async def manual_registration(session: AsyncSession, partner: PartnerProfile, endpoints: List[Endpoint]) -> bool:
    already_exists = await is_partner_registered(session, partner.country_code, partner.party_id, partner.role)

    if not already_exists:
        session.add(partner)
        await session.flush()

        # 1. Clear existing endpoints for this version/partner to avoid duplicates
        # This is safer than trying to match individual IDs
        delete_stmt = delete(Endpoint).where(
            Endpoint.country_code == partner.country_code,
            Endpoint.party_id == partner.party_id,
            Endpoint.version == partner.registered_version,
            Endpoint.role == partner.role
        )
        await session.execute(
            delete_stmt,
            execution_options={"synchronize_session": "fetch"}
        )
        await session.flush()

        print(f"Storing these endpoints: {endpoints}")

        # 2. Iterate through the OCPI endpoints list
        for ep in endpoints:
            new_module = Endpoint(
                identifier=ep.identifier,
                version=ep.version,
                country_code=partner.country_code,
                party_id=partner.party_id,
                role=partner.role,
                url=ep.url
            )
            print(f"Storing Module: {new_module.identifier}")
            session.add(new_module)

        await session.commit()
        print(f"✅ Stored Endpoints Successfully!")

        return True

    elif already_exists:
        print("Partner Already Exists")
        return False
    else:
        return False