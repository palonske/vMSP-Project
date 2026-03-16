from fastapi import APIRouter, Depends, HTTPException, Body, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlmodel import Session, select

from app.core.authorization import get_current_partner, validate_role
from app.database import engine, get_session
from app.models import Tariff, PartnerProfile, TariffType, TariffElement, TariffRestriction, PriceComponent, PartnerRole
from datetime import datetime, timezone
from app.api.v2_1_1.schemas import TariffRead
from app.core.utils import get_timestamp, fix_date

emsprouter = APIRouter()
cporouter = APIRouter()

# Helper shared with locations to handle OCPI date formats
#def fix_date(data_dict):
#    date_str = data_dict.get("last_updated")
#    if date_str and isinstance(date_str, str):
#        data_dict["last_updated"] = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
#    return data_dict

async def process_tariff(raw_data: dict, cpo: PartnerProfile, session: AsyncSession):
    # 0. Inject ownership metadata
    raw_data["country_code"] = cpo.country_code
    raw_data["party_id"] = cpo.party_id

    # 1. Validate against Schema
    try:
        validated_tariff = TariffRead.model_validate(raw_data)
        tariff_id = validated_tariff.id
    except ValidationError as e:
        print(f"Skipping invalid location data: {e}")
        raise e

    # 2. Clean up existing data (standard OCPI PUT replacement)
    statement = select(Tariff).where(
        Tariff.id == tariff_id,
        Tariff.country_code == cpo.country_code,
        Tariff.party_id == cpo.party_id
    )
    result = await session.execute(statement)
    existing_tariff = result.scalars().first()

    if existing_tariff:
        await session.delete(existing_tariff)
        await session.flush() # Ensure deletion is staged before re-adding
        session.expunge(existing_tariff)

    # 3. Tree Building Logic
    fix_date(raw_data)
    elements_raw = raw_data.pop("elements", [])

    # Handle the JSON fields (energy_mix) handled by sa_column=Column(JSON)
    tariff_obj = Tariff(**raw_data)

    for el_raw in elements_raw:
        # Price Components
        price_components_raw = el_raw.pop("price_components", [])

        # Restrictions
        restrictions_raw = el_raw.pop("restrictions", None)

        element_obj = TariffElement(**el_raw, tariff_id=tariff_obj.id)

        # Process Price Components (Required by OCPI)
        for pc_raw in price_components_raw:
            pc_obj = PriceComponent(**pc_raw)
            element_obj.price_components.append(pc_obj)

        # Process Restrictions (Optional)
        if restrictions_raw:
            # day_of_week is handled as JSON list in your model
            res_obj = TariffRestriction(**restrictions_raw)
            element_obj.restrictions = res_obj

        tariff_obj.elements.append(element_obj)

    session.add(tariff_obj)
    await session.flush()
    return tariff_obj

@emsprouter.put("/{country_code}/{party_id}/{tariff_id}")
async def put_tariff(
        country_code: str,
        party_id: str,
        tariff_id: str,
        tariff_data: dict, # Pydantic validates the body automatically
        partner = Depends(validate_role(PartnerRole.CPO)),
        session: AsyncSession = Depends(get_session)
):
    #Checking to see if Partner matches path parameters:
    if not party_id == partner.party_id and country_code == partner.country_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path parameters do not match registered partner.")

    try:
        # Use our existing logic to wipe the old and save the new
        # We convert the Pydantic model back to a dict for the processor

        tariff_data["id"] = tariff_id

        #cpo_profile = PartnerProfile(country_code=country_code, party_id=party_id)

        async with session.begin_nested():
            await process_tariff(tariff_data, partner, session)

        await session.commit()
        #timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        return {
            "status_code": 1000,
            "status_message": "Tariff successfully updated/created",
            "timestamp": get_timestamp()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process Tariff: {str(e)}")

@emsprouter.patch("/{country_code}/{party_id}/{tariff_id}")
async def patch_tariff(
        country_code: str,
        party_id: str,
        tariff_id: str,
        patch_data: dict,
        partner = Depends(validate_role(PartnerRole.CPO)),
        session: AsyncSession = Depends(get_session)
):
    # 1. Fetch the existing tariff with all nested data loaded

    #Checking to see if Partner matches path parameters:
    if not party_id == partner.party_id and country_code == partner.country_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path parameters do not match registered partner.")

    statement = (
        select(Tariff)
        .where(
            Tariff.id == tariff_id,
            Tariff.country_code == country_code,
            Tariff.party_id == party_id
        )
        .options(
            selectinload(Tariff.elements).selectinload(TariffElement.price_components),
            selectinload(Tariff.elements).selectinload(TariffElement.restrictions)
        )
    )
    result = await session.execute(statement)
    existing_tariff = result.scalars().first()

    if not existing_tariff:
        raise HTTPException(status_code=404, detail="Tariff not found")

    # 2. Convert existing DB object to a dictionary
    # We use TariffRead to ensure the data is in a clean format
    current_data = TariffRead.model_validate(existing_tariff).model_dump()

    # 3. Merge the patch_data into the current_data
    # This ensures fields not present in the PATCH remain unchanged
    updated_full_data = {**current_data, **patch_data}

    # 4. Reuse your process_tariff logic
    # Since process_tariff handles the delete-and-recreate (idempotency),
    # it works perfectly for the "final state" of a PATCH
    #cpo_profile = PartnerProfile(country_code=country_code, party_id=party_id)

    async with session.begin_nested():
        tariff_obj = await process_tariff(updated_full_data, partner, session)

    await session.commit()
    #timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


    return {
        "status_code": 1000,
        "status_message": "Tariff patched successfully",
        "timestamp": get_timestamp(),
        "data": [tariff_obj]
    }

@emsprouter.get("/", response_model=dict)
@cporouter.get("/", response_model=dict)
async def get_tariffs(partner: PartnerProfile = Depends(get_current_partner),session: AsyncSession = Depends(get_session)):
    # 1. Fetch tariffs with their nested elements
    statement = (
        select(Tariff)
        .options(
            selectinload(Tariff.elements).selectinload(TariffElement.price_components),
            selectinload(Tariff.elements).selectinload(TariffElement.restrictions)
        )
    )
    result = await session.execute(statement)
    tariffs = result.scalars().all()

    return {
        "status_code": 1000,
        "status_message": "Success",
        "timestamp": get_timestamp(),
        "data": [TariffRead.model_validate(t) for t in tariffs]
    }

@emsprouter.get("/{country_code}/{party_id}/{tariff_id}")
@cporouter.get("/{country_code}/{party_id}/{tariff_id}")
async def get_tariff(
        country_code: str,
        party_id: str,
        tariff_id: str,
        partner: PartnerProfile = Depends(get_current_partner),
        session: AsyncSession = Depends(get_session)
):
    statement = (
        select(Tariff)
        .where(Tariff.id == tariff_id)
        .options(
            selectinload(Tariff.elements).selectinload(TariffElement.price_components),
            selectinload(Tariff.elements).selectinload(TariffElement.restrictions)
        )
    )
    result = await session.execute(statement)
    tariff = result.scalars().first()

    if not tariff:
        raise HTTPException(status_code=404, detail="Tariff not found")

    return {
        "status_code": 1000,
        "status_message": "Success",
        "timestamp": get_timestamp(),
        "data": [TariffRead.model_validate(tariff)]
    }