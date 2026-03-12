from fastapi import Header, HTTPException, Depends, status
from sqlmodel import select
from app.database import get_session # Adjust to your import path
from app.models import PartnerProfile
from sqlalchemy import or_

async def get_current_partner(
        authorization: str = Header(...),
        session = Depends(get_session)
) -> PartnerProfile:
    # 1. Clean the 'Token ' prefix
    token = authorization.replace("Token ", "").replace("token ", "").strip()

    # 2. Query the DB for a partner matching Token B or Token C
    # (Token B for requests we send to them, Token C for requests they send to us)
    print(f"Checking Token C to find partner: {token}")
    statement = select(PartnerProfile).where(
        or_(
            PartnerProfile.token_c == token,
            PartnerProfile.token_b == token
        )
    )
    result = await session.execute(statement)
    partner = result.scalar_one_or_none()

    # 3. Handle unauthorized access
    if not partner:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status_code": 2001, "status_message": "Invalid or expired token"}
        )
    elif not partner.status == "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status_code": 2001, "status_message": "Invalid or expired token"}
        )

    # 4. Return the partner object for use in the route
    return partner

def validate_role(required_role: str):
    async def role_checker(partner: PartnerProfile = Depends(get_current_partner)):
        print(f"Checking if partner: {partner.country_code}{partner.party_id} with role of {partner.role} matches required role of {required_role}.")
        if partner.role != required_role:
            raise HTTPException(status_code=403, detail="Forbidden: Wrong OCPI Role")
        return partner
    return role_checker