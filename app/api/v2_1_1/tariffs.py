from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlmodel import Session, select
from app.database import engine, get_session
from app.models import Tariff, PartnerProfile, TariffType, TariffElement, TariffRestriction, PriceComponent
from datetime import datetime
from app.api.v2_1_1.schemas import TariffRead

router = APIRouter()

def fix_date(data_dict):
    date_str = data_dict.get("last_updated")
    if date_str and isinstance(date_str, str):
        data_dict["last_updated"] = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    return data_dict

async def process_tariff(raw_data: dict, cpo: PartnerProfile, session: AsyncSession):
    # Validation is CPU-bound, so no await needed here
    validated_tariff = TariffRead.model_validate(raw_data)
    tariff_id = validated_tariff.id

    # 2. Cleanup existing
    # session.exec() is a database call, so it MUST be awaited
    result = await session.execute(
        select(Tariff).where(
            Tariff.id == tariff_id,
            Tariff.country_code == cpo.country_code,
            Tariff.party_id == cpo.party_id
        )
    )
    existing = result.first()

    if existing:
        await session.delete(existing)  # Staging delete is sync
        await session.flush()    # Executing delete in DB is async
        session.expunge(existing)

    # Assuming fix_date is a local helper, no await needed
    await fix_date(raw_data)

    # 3. Build the Tree (All memory operations, no awaits needed)
    new_tariff = Tariff(
        id=validated_tariff.id,
        country_code=cpo.country_code,
        party_id=cpo.party_id,
        currency=validated_tariff.currency,
        type=validated_tariff.type,
        last_updated=validated_tariff.last_updated
    )

    for el_read in validated_tariff.elements:
        element_obj = TariffElement()

        if el_read.restrictions:
            res_data = el_read.restrictions.model_dump()
            element_obj.restrictions = TariffRestriction(**res_data)

        for pc_read in el_read.price_components:
            pc_obj = PriceComponent(**pc_read.model_dump())
            element_obj.price_components.append(pc_obj)

        new_tariff.elements.append(element_obj)

    # 4. Save the whole tree
    session.add(new_tariff)
    await session.flush() # Await the final insert

    return new_tariff

@router.put("/{country_code}/{party_id}/{tariff_id}", response_model=dict)
async def put_tariff(
        country_code: str,
        party_id: str,
        tariff_id: str,
        tariff_data: TariffRead, # Pydantic validates the body automatically
        session: AsyncSession = Depends(get_session)
):
    try:
        # Use our existing logic to wipe the old and save the new
        # We convert the Pydantic model back to a dict for the processor
        cpo_profile = PartnerProfile(country_code=country_code, party_id=party_id)
        await process_tariff(tariff_data.model_dump(), cpo_profile, session)

        return {
            "status_code": 1000,
            "status_message": "Tariff successfully updated/created",
            "timestamp": datetime.now()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process Tariff: {str(e)}")