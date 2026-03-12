from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Body, status
from fastapi.security import APIKeyHeader
from sqlalchemy import update, or_
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
from sqlmodel import select, delete
from typing import Optional, List
from app.api.v2_1_1.schemas import PartnerSchema, InternalRegister
from app.config import settings
import secrets
from app.database import get_session
from app.models.partner import PartnerProfile, Endpoint, PartnerRole
from app.core.utils import get_timestamp

cporouter = APIRouter()
emsprouter = APIRouter()
header_scheme = APIKeyHeader(name="Authorization", auto_error=False)

async def find_preregistered_emsp(token, session) -> PartnerProfile:
    print(f"Checking if Token A {token} exists in database")
    statement = select(PartnerProfile).where(
        PartnerProfile.token_a == token
    )
    result = await session.execute(statement)
    partner = result.scalar_one_or_none()

    print(f"Found pre-registration: {partner}")

    return partner

@cporouter.post("/")
async def register_emsp(
        token: str = Body(...),
        url: str = Body(...),
        business_details: dict = Body(...),
        party_id: str = Body(...),
        country_code: str = Body(...),
        Authorization: str = Header(header_scheme),
        session: AsyncSession = Depends(get_session)
):
    #1. Find the Token A and validate that it is allowed to onboard.
    if not Authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization Header")

    # Strip the prefix
    token_a = Authorization.replace("Token ", "").replace("token ", "").strip()

    preregistered_partner = await find_preregistered_emsp(token_a, session)

    if preregistered_partner and preregistered_partner.status == "REGISTERED":
        token_c = secrets.token_hex(16)

        new_partner = PartnerProfile(token_b=token, token_c=token_c, token_a = token_a,
                                     country_code=country_code, party_id=party_id, versions_url=url,
                                     registered_version="2.1.1",
                                     business_details=business_details,
                                     status="ACTIVE", role=PartnerRole.EMSP)

        print(f"Registering new EMSP: {new_partner.country_code}{new_partner.party_id} with Token C: {token_c} as {preregistered_partner.party_id}")

        versions = await fetch_partner_versions(new_partner.versions_url, new_partner.token_b)
        new_partner = await select_partner_version(new_partner, versions)
        endpoints = await fetch_version_details(new_partner, new_partner.token_b)

        statement = update(PartnerProfile).where(
            PartnerProfile.party_id == preregistered_partner.party_id,
            PartnerProfile.country_code == preregistered_partner.country_code,
            PartnerProfile.token_a == preregistered_partner.token_a
        ).values(
            **new_partner.model_dump(exclude_unset=True)
        )
        try:
            print(f"Attempting Update: {statement}")
            await session.execute(statement)
            await save_module_urls(session, new_partner, endpoints, new_partner.registered_version, new_partner.role)

        except Exception as e:
            await session.rollback()
            raise HTTPException(status_code=400, detail=str(e))

        await session.commit()

        return {
            "status_code": 1000,
            "status_message": "Success",
            "timestamp": get_timestamp(),
            "data":
                {
                    "url": f"{settings.BASE_URL}/ocpi/cpo/versions",
                    "token": f"{token_c}",
                    "party_id": "EPS",
                    "country_code": "US",
                    "business_details": {
                        "name": "Eric's vMSP",
                        "logo": {
                            "url": "https://example.com/img/logo.jpg",
                            "thumbnail": "https://example.com/img/logo_thumb.jpg",
                            "category": "OPERATOR",
                            "type": "jpeg",
                            "width": 512,
                            "height": 512
                        },
                        "website": "http://example.com"
                    }
                }
        }
    elif preregistered_partner and preregistered_partner.status not in "REGISTERED":
        #timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        print("Token A already registered. Returning Error Response")

        raise HTTPException(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
                detail={
                    "status_code": 3001, # OCPI Client Error: Invalid input
                    "status_message": "Token A Already Registered",
                    "timestamp": get_timestamp()
                }
            )
    else:

        #timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status_code": 2001, # OCPI Client Error: Invalid input
                "status_message": "Invalid Token A: Partner not found",
                "timestamp": get_timestamp()
            }
        )


async def find_registered_partner(token, session):
    print(f"Checking if Token  {token} exists in database")
    statement = select(PartnerProfile).where(
        or_(
            PartnerProfile.token_b == token,
            PartnerProfile.token_c == token
        )
    )
    result = await session.execute(statement)
    partner = result.scalar_one_or_none()

    print(f"Found registration: {partner}")

    return partner


@cporouter.put("/")
@emsprouter.put("/")
async def update_partner(
        token: str = Body(...),
        url: str = Body(...),
        business_details: dict = Body(...),
        party_id: str = Body(...),
        country_code: str = Body(...),
        Authorization: str = Header(header_scheme),
        session: AsyncSession = Depends(get_session)
):
    global updated_partner
    if not Authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization Header")

    # Strip the prefix


    token_bc = Authorization.replace("Token ", "").replace("token ", "").strip()
    #timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    if await find_preregistered_emsp(token_bc, session):
        raise HTTPException(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            detail={
                "status_code": 3001, # OCPI Client Error: Invalid input
                "status_message": "Partner is not registered.",
                "timestamp": get_timestamp()
            }
        )
    elif not await find_registered_partner(token_bc, session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status_code": 3001, # OCPI Client Error: Invalid input
                "status_message": "Unauthorized",
                "timestamp": get_timestamp()
            }
        )
    else:
        partner = await find_registered_partner(token_bc, session)

        new_token = secrets.token_hex(16)

        print(f"Updating Partner: {partner.country_code}{partner.party_id} with new token {new_token}.")

        if partner.role == PartnerRole.CPO:
            print(f"Partner {partner.country_code}{partner.party_id} is a CPO")
            updated_partner = PartnerProfile(token_b=new_token, token_c=token,
                                         country_code=country_code, party_id=party_id, versions_url=url,
                                         registered_version="2.1.1",
                                         business_details=business_details,
                                         status="ACTIVE", role=PartnerRole.CPO)
        elif partner.role == PartnerRole.EMSP:
            print(f"Partner {partner.country_code}{partner.party_id} is an EMSP")
            updated_partner = PartnerProfile(token_b=token, token_c=new_token,
                                             country_code=country_code, party_id=party_id, versions_url=url,
                                             registered_version="2.1.1",
                                             business_details=business_details,
                                             status="ACTIVE", role=PartnerRole.EMSP)

        versions = await fetch_partner_versions(updated_partner.versions_url, token_bc)
        updated_partner = await select_partner_version(updated_partner, versions)
        endpoints = await fetch_version_details(updated_partner, token_bc)

        statement = update(PartnerProfile).where(
            PartnerProfile.party_id == partner.party_id,
            PartnerProfile.country_code == partner.country_code,
            PartnerProfile.role == partner.role
        ).values(
            **updated_partner.model_dump(exclude_unset=True)
        )
        try:
            print(f"Attempting Update: {statement}")
            await session.execute(statement)
            await save_module_urls(session, updated_partner, endpoints, updated_partner.registered_version, updated_partner.role)

        except Exception as e:
            await session.rollback()
            raise HTTPException(status_code=400, detail=str(e))

        await session.commit()

        return {
            "status_code": 1000,
            "status_message": "Success",
            "timestamp": get_timestamp(),
            "data":
                {
                    "url": f"{settings.BASE_URL}/ocpi/cpo/versions",
                    "token": f"{new_token}",
                    "party_id": "EPS",
                    "country_code": "US",
                    "business_details": {
                        "name": "Eric's vMSP",
                        "logo": {
                            "url": "https://example.com/img/logo.jpg",
                            "thumbnail": "https://example.com/img/logo_thumb.jpg",
                            "category": "OPERATOR",
                            "type": "jpeg",
                            "width": 512,
                            "height": 512
                        },
                        "website": "http://example.com"
                    }
                }
        }


async def fetch_partner_versions(versions_url: str, token: str) -> List[dict]:
    """
    Calls the Partners's Versions endpoint to see what they support.
    """
    headers = {
        "Authorization": f"Token {token}",
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


async def select_partner_version(partner: PartnerProfile,versions: List[dict]) -> Optional[PartnerProfile]:
    print(f"Finding Version Match from: {versions}")
    for v in versions:
        if v.get("version") == "2.1.1":
            partner.version_detail_url = v.get("url")
            partner.registered_version = "2.1.1"
            return partner
    return None

async def fetch_version_details(partner: PartnerProfile, token) -> Optional[List[Endpoint]]:
    """
    Fetches the module list for a specific version and returns the Credentials endpoint.
    """
    headers = {"Authorization": f"Token {token}"}

    async with httpx.AsyncClient() as client:
        response = await client.get(partner.version_detail_url, headers=headers)

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

        endpoint_objects = [
            Endpoint(
                version="2.1.1",
                country_code=partner.country_code,
                party_id=partner.party_id,
                role=partner.role,
                url=ep.get("url"),
                identifier=ep.get("identifier")
            )
            for ep in endpoints
        ]

        if endpoint_objects:
            return endpoint_objects
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
            identifier=ep.identifier,
            version=version,
            country_code=partner.country_code,
            party_id=partner.party_id,
            url=ep.url,
            role=ep.role
        )
        print(f"Storing Module: {module_url.identifier}")
        session.add(module_url)
    print(f"✅ Stored Endpoints Successfully!")
    # 3. Flush to the database (session.commit() usually happens in the main caller)
    await session.flush()
    await session.commit()