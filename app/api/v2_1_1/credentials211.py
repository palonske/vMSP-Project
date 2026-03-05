from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Body, status
from fastapi.security import APIKeyHeader
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
from sqlmodel import select, delete
from typing import Optional, List
from app.api.v2_1_1.schemas import PartnerSchema, InternalRegister
from app.config import settings
import secrets
from app.database import get_session
from app.models.partner import PartnerProfile, Endpoint, PartnerRole

cporouter = APIRouter()
emsprouter = APIRouter()
header_scheme = APIKeyHeader(name="Authorization", auto_error=False)

async def preregistered_emsp(token, session) -> PartnerProfile:
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

    preregistered_partner = await preregistered_emsp(token_a, session)

    if preregistered_partner and preregistered_partner.status == "REGISTERED":
        token_c = secrets.token_hex(16)

        new_partner = PartnerProfile(token_b=token, token_c=token_c, token_a = token_a,
                                     country_code=country_code, party_id=party_id, versions_url=url,
                                     registered_version="2.1.1",
                                     business_details=business_details,
                                     status="ACTIVE", role=PartnerRole.EMSP)

        print(f"Registering new EMSP: {new_partner.country_code}{new_partner.party_id} with Token C: {token_c} as {preregistered_partner.party_id}")

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
        except Exception as e:
            await session.rollback()
            raise HTTPException(status_code=400, detail=str(e))

        await session.commit()
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        return {
            "status_code": 1000,
            "status_message": "Success",
            "timestamp": f"{timestamp}",
            "data":
                {
                    "url": f"{settings.BASE_URL}/ocpi/versions",
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
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        print("Token A already registered. Returning Error Response")

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status_code": 3001, # OCPI Client Error: Invalid input
                    "status_message": "Token A Already Registered",
                    "timestamp": f"{timestamp}"
                }
            )
    else:

        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status_code": 2001, # OCPI Client Error: Invalid input
                "status_message": "Invalid Token A: Partner not found",
                "timestamp": f"{timestamp}"
            }
        )
