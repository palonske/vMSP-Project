from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlmodel import Session, select, and_
from app.core.utils import fix_date, get_timestamp, get_roaming_partners, check_roaming_permission
from app.core.authorization import get_current_partner, validate_role
from app.database import engine, get_session
from app.models import Location, EVSE, Connector, PartnerProfile, RoamingAgreement
from datetime import datetime
from app.api.v2_1_1.schemas import LocationRead, EVSERead, ConnectorRead, EVSEUpdate
from app.models.partner import PartnerRole
from app.models.roaming_agreement import AgreementStatus

emsprouter = APIRouter()
cporouter = APIRouter()

# Helper to fix dates (move this to a utils.py later if you want)
#def fix_date(data_dict):
#    date_str = data_dict.get("last_updated")
#    if date_str and isinstance(date_str, str):
#       data_dict["last_updated"] = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
#    return data_dict

async def process_location(raw_data: dict, cpo: PartnerProfile, session: AsyncSession):
    raw_data["country_code"] = cpo.country_code
    raw_data["party_id"] = cpo.party_id


    try:
        validated_loc = LocationRead.model_validate(raw_data)
        location_id = validated_loc.id
        print(f"Validated Location ID: {location_id}")
    except ValidationError as e:
        print(f"Skipping invalid location data: {e}")
        raise e

    # Await the query
    statement = select(Location).where(
        Location.id == location_id,
        Location.country_code == cpo.country_code,
        Location.party_id == cpo.party_id
    )
    print(f"Running statement to find match: {statement}")
    result = await session.execute(statement)
    existing_loc = result.scalars().first()

    if existing_loc:
        await session.delete(existing_loc)
        await session.flush()
        session.expunge(existing_loc)

    # 2. Re-use your successful "Tree Building" logic
    fix_date(raw_data)
    evses_raw = raw_data.pop("evses", [])
    location_obj = Location(**raw_data)

    for e_raw in evses_raw:
        fix_date(e_raw)
        connectors_raw = e_raw.pop("connectors", [])
        evse_obj = EVSE(**e_raw, location_id=location_obj.id)

        for c_raw in connectors_raw:
            fix_date(c_raw)
            connector_obj = Connector(
                **c_raw,
                evse_uid=evse_obj.uid,
                location_id=location_obj.id
            )
            evse_obj.connectors.append(connector_obj)

        location_obj.evses.append(evse_obj)

    session.add(location_obj)
    await session.flush()
    await session.commit()

    return {"status_code": 1000, "status_message": "Success", "data": f"{[location_obj.id]} stored successfully."}

# --- GET ALL LOCATIONS ---
@emsprouter.get("/", response_model=dict)
@cporouter.get("/", response_model=dict)
async def get_locations(partner: PartnerProfile = Depends(get_current_partner),session: AsyncSession = Depends(get_session)):
    # Select all location records

    print(f"Partner {partner.country_code}{partner.party_id} is requesting locations as {partner.role}.")
    if partner.role == PartnerRole.CPO:
        statement = (
            select(Location)
            .where(
                and_(Location.party_id == partner.party_id,
                   Location.country_code == partner.country_code))
            .options(
                joinedload(Location.evses)
                .joinedload(EVSE.connectors)
            )
        )
    elif partner.role == PartnerRole.EMSP:
        #Check Roaming Partner Permissions
        partners = await get_roaming_partners(partner, session)

        statement = (
            select(Location)
            .join(
                RoamingAgreement,
                and_(
                    Location.country_code == RoamingAgreement.cpo_country_code,
                    Location.party_id == RoamingAgreement.cpo_party_id
                )
            )
            .where(
                # 1. Match the eMSP who is asking
                RoamingAgreement.emsp_country_code == partner.country_code,
                RoamingAgreement.emsp_party_id == partner.party_id,

                # 2. Check that the agreement is active
                RoamingAgreement.status == AgreementStatus.ACTIVE,

                # 3. Check that they are allowed to see locations
                RoamingAgreement.location_enabled == True
            )
            .options(
                selectinload(Location.evses).selectinload(EVSE.connectors)
            )
        )

    print(f"Executing statement: {statement}")
    result = await session.execute(statement)
    locations = result.unique().scalars().all()

    data_as_schema = [LocationRead.model_validate(loc) for loc in locations]

    return {
        "status_code": 1000,
        "status_message": "Success",
        "timestamp": get_timestamp(),
        "data": data_as_schema  # <-- LocationRead will now see 'evses'
    }


# --- GET SPECIFIC LOCATION ---
@cporouter.get("/{location_id}", response_model=dict)
@emsprouter.get("/{location_id}", response_model=dict)
async def get_location(
        location_id: str,
        partner: PartnerProfile = Depends(get_current_partner),
        session: AsyncSession = Depends(get_session)
):
    # Use joinedload to ensure the data is fetched from the DB
    statement = (
        select(Location)
        .where(Location.id == location_id)
        .options(
            joinedload(Location.evses)
            .joinedload(EVSE.connectors)
        )
    )

    result = await session.execute(statement)
    location = result.unique().scalars().first()

    print(f"DEBUG: Found Location {location.id}")
    print(f"DEBUG: Number of EVSEs found: {len(location.evses)}")
    for e in location.evses:
        print(f"DEBUG: EVSE {e.uid} has {len(e.connectors)} connectors")

    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    if partner.role == PartnerRole.EMSP and not (await check_roaming_permission(session, location.party_id, location.country_code, partner.party_id, partner.country_code)):
        raise HTTPException(status_code=404, detail="Location not found")
    if partner.role == PartnerRole.CPO and location.party_id != partner.party_id:
        raise HTTPException(status_code=404, detail="Location not found")

    # We return the OCPI wrapper.
    # FastAPI will use 'LocationRead' logic to fill the 'data' field.

    data_as_schema = LocationRead.model_validate(location)

    return {
        "status_code": 1000,
        "status_message": "Success",
        "data": data_as_schema  # <-- LocationRead will now see 'evses'
    }

# --- GET SPECIFIC EVSE ---
@cporouter.get("/{location_id}/{evse_uid}", response_model=dict)
@emsprouter.get("/{location_id}/{evse_uid}", response_model=dict)
async def get_evse(
        location_id: str,
        evse_uid: str,
        partner: PartnerProfile = Depends(get_current_partner),
        session: AsyncSession = Depends(get_session)
):
    # Use joinedload to ensure the data is fetched from the DB
    try:
        statement = (
            select(EVSE)
            .join(Location, EVSE.location_id == Location.id) # 1. The Join for filtering/logic
            .where(EVSE.uid == evse_uid)
            .where(EVSE.location_id == location_id)
            .options(
                joinedload(EVSE.location),    # 2. Load the Location object into evse.location
                joinedload(EVSE.connectors)   # Keep your existing connector loading
            )
        )

        result = await session.execute(statement)
        evse = result.unique().scalars().first()

        print(f"DEBUG: Found EVSE {evse.uid}")

        if not evse:
            raise HTTPException(status_code=404, detail="Location not found")

        if partner.role == PartnerRole.EMSP and not (await check_roaming_permission(session, location.party_id, location.country_code, partner.party_id, partner.country_code)):
            raise HTTPException(status_code=404, detail="Location not found")
        if partner.role == PartnerRole.CPO and evse.location.party_id != partner.party_id:
            raise HTTPException(status_code=404, detail="Location not found")
    except:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bad Request")

    # We return the OCPI wrapper.
    # FastAPI will use 'LocationRead' logic to fill the 'data' field.

    data_as_schema = EVSERead.model_validate(evse)

    return {
        "status_code": 1000,
        "status_message": "Success",
        "timestamp": get_timestamp(),
        "data": data_as_schema  # <-- LocationRead will now see 'evses'
    }

@emsprouter.put("/{country_code}/{party_id}/{location_id}")
async def put_location(
        country_code: str,
        party_id: str,
        location_id: str,
        raw_data: dict,
        partner = Depends(validate_role(PartnerRole.CPO)),
        session: AsyncSession = Depends(get_session)
):

    #Checking to see if Partner matches path parameters:
    if not party_id == partner.party_id and country_code == partner.country_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path parameters do not match registered partner.")


    try:
        #cpo = PartnerProfile(country_code=country_code, party_id=party_id)
        cpo = partner
        response_json =    await process_location(raw_data, cpo, session)
        return response_json
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@cporouter.patch("/{country_code}/{party_id}/{location_id}")
async def patch_location(
        country_code: str,
        party_id: str,
        location_id: str,
        patch_data: dict,
        partner = Depends(validate_role(PartnerRole.CPO)),
        session: AsyncSession = Depends(get_session)
):
    #Checking to see if Partner matches path parameters:
    if not party_id == partner.party_id and country_code == partner.country_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path parameters do not match registered partner.")


    # 1. Get the existing location
    db_location = session.get(Location, location_id)
    if not db_location:
        raise HTTPException(status_code=404, detail="Location not found")

    # 2. Update top-level Location fields
    # We exclude 'evses' for now to handle them separately
    for key, value in patch_data.items():
        if key == "evses":
            continue
        if key == "last_updated":
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))

        setattr(db_location, key, value)

    # 3. Handle Nested EVSE Patches (if provided)
    try:
        if "evses" in patch_data:
            for e_patch in patch_data["evses"]:
                e_uid = e_patch.get("uid")
                # Find the specific EVSE within this location
                db_evse = next((e for e in db_location.evses if e.uid == e_uid), None)

                if db_evse:
                    # Update EVSE fields
                    for e_key, e_value in e_patch.items():
                        if e_key == "connectors":
                            continue # Connectors can be handled in a third loop if needed
                        if e_key == "last_updated":
                            e_value = datetime.fromisoformat(e_value.replace("Z", "+00:00"))
                        setattr(db_evse, e_key, e_value)

                        if "connectors" in e_patch:
                            for c_patch in e_patch["connectors"]:
                                c_id = c_patch.get("id")
                                # Find connector by ID within THIS specific EVSE
                                db_conn = next((c for c in db_evse.connectors if c.id == c_id), None)

                                if db_conn:
                                    for c_key, c_value in c_patch.items():
                                        if c_key == "id": continue
                                        if c_key == "last_updated":
                                            c_value = datetime.fromisoformat(c_value.replace("Z", "+00:00"))
                                        setattr(db_conn, c_key, c_value)
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    # 4. Save changes
    session.add(db_location)
    await session.commit()
    await session.refresh(db_location)

    return {
        "status_code": 1000,
        "status_message": "Location patched successfully",
        "timestamp": get_timestamp(),
        "data": [db_location.id]
    }

@emsprouter.patch("/{country_code}/{party_id}/{location_id}/{evse_uid}")
async def patch_evse(
        country_code: str,
        party_id: str,
        location_id: str,
        evse_uid: str,
        patch_data: dict,
        partner = Depends(validate_role(PartnerRole.CPO)),
        session: AsyncSession = Depends(get_session)
):

    #Checking to see if Partner matches path parameters:
    if not party_id == partner.party_id and country_code == partner.country_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path parameters do not match registered partner.")

    # 1. Fetch the specific EVSE and verify it belongs to the Location
    statement = select(EVSE).where(EVSE.uid == evse_uid, EVSE.location_id == location_id)
    db_evse = session.execute(statement).first()

    if not db_evse:
        raise HTTPException(status_code=404, detail="EVSE not found for this location")

    try:
        EVSEUpdate.model_validate(patch_data)
        # 2. Update EVSE top-level fields
        for key, value in patch_data.items():
            if key in ["connectors", "uid"]: continue
            if key == "last_updated":
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            setattr(db_evse, key, value)

        # 3. Handle Connector updates within this EVSE
        if "connectors" in patch_data:
            for c_patch in patch_data["connectors"]:
                c_id = c_patch.get("id")
                db_conn = next((c for c in db_evse.connectors if c.id == c_id), None)

                if db_conn:
                    for c_key, c_value in c_patch.items():
                        if c_key == "id": continue
                        if c_key == "last_updated":
                            c_value = datetime.fromisoformat(c_value.replace("Z", "+00:00"))
                        setattr(db_conn, c_key, c_value)
    except Exception as e:
        await session.rollback()
        # This will now catch the Enum error from the EVSEUpdate schema
        raise HTTPException(status_code=400, detail=f"Validation Error: {str(e)}")

    # 4. Cascade 'last_updated' to the Parent Location
    db_evse.location.last_updated = datetime.now()

    session.add(db_evse)
    await session.commit()
    await session.refresh(db_evse)

    data_as_schema = EVSERead.model_validate(db_evse)

    return {
        "status_code": 1000,
        "status_message": "EVSE updated successfully",
        "timestamp": get_timestamp(),
        "data": [data_as_schema]
    }