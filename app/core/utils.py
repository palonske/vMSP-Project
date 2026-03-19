from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import exists
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session, select, and_

from app.models import PartnerProfile, PartnerRole, RoamingAgreement
from app.models.roaming_agreement import AgreementStatus


def fix_date(data_dict):
    date_str = data_dict.get("last_updated")
    if date_str and isinstance(date_str, str):
        data_dict["last_updated"] = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    return data_dict

def get_timestamp():
    timestamp = datetime.now(timezone.utc).isoformat(timespec='seconds').replace("+00:00", "Z")
    return timestamp

async def get_roaming_partners(partner: PartnerProfile, session: AsyncSession) -> Optional[List[PartnerProfile]]:
    print(f"Finding Roaming Partners for {partner.country_code}{partner.party_id} as {partner.role}.")
    #WORK IN PROGRESS ON THE SELECT STATEMENT BELOW.
    #MUST MAKE IT SO THAT WE ARE LOOKING AT THE CORRECT TABLE.
    #MUST ALSO ADD IN THE IF EMSP OR CPO TO DETERMINE PROPER COLUMN TO CHECK.
    if partner.role == PartnerRole.CPO:
        statement = (
            select(PartnerProfile)
            .join(
                RoamingAgreement,
                and_(
                    PartnerProfile.party_id == RoamingAgreement.emsp_party_id,
                    PartnerProfile.country_code == RoamingAgreement.emsp_country_code
                )
            )
            .where(
                RoamingAgreement.emsp_party_id == partner.party_id,
                RoamingAgreement.emsp_country_code == partner.country_code
            )
        )
    elif partner.role == PartnerRole.EMSP:
        statement = (
            select(PartnerProfile)
            .join(
                RoamingAgreement,
                and_(
                    PartnerProfile.party_id == RoamingAgreement.cpo_party_id,
                    PartnerProfile.country_code == RoamingAgreement.cpo_country_code
                )
            )
            .where(
                RoamingAgreement.emsp_party_id == partner.party_id,
                RoamingAgreement.emsp_country_code == partner.country_code
            )
        )

    results = await session.execute(statement)
    partners = results.scalars().all()

    if not partners:
        print("Found no partners, returning None.")
        return None
    else:
        formatted_partners = [f"{p.country_code}{p.party_id}" for p in partners]
        print(f"Found {len(partners)} Roaming Agreements: {formatted_partners}")
        return partners

async def check_roaming_permission(session: AsyncSession, cpo_id, cpo_cc, emsp_id, emsp_cc) -> bool:
    # 1. Create a subquery that looks for the agreement

    print(f"Checking if roaming agreement exists between CPO: {cpo_cc}{cpo_id} and EMSP: {emsp_cc}{emsp_id}")
    subquery = select(RoamingAgreement).where(
        and_(
            RoamingAgreement.emsp_country_code == emsp_cc,
            RoamingAgreement.emsp_party_id == emsp_id,
            RoamingAgreement.cpo_country_code == cpo_cc,
            RoamingAgreement.cpo_party_id == cpo_id,
            RoamingAgreement.status == AgreementStatus.ACTIVE,
            RoamingAgreement.location_enabled == True  # Or whichever permission you are checking
        )
    )

    # 2. Wrap it in exists()
    statement = select(exists(subquery))

    # 3. Execute and get the scalar (True/False)
    result = await session.execute(statement)
    print(f"Result is: {result}")
    return result.scalar() or False