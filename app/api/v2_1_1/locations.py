from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import joinedload
from sqlmodel import Session, select
from app.database import engine, get_session
from app.models import Location, EVSE, Connector
from datetime import datetime
from app.api.v2_1_1.schemas import LocationRead, EVSERead, ConnectorRead, EVSEUpdate

router = APIRouter()

# Helper to fix dates (move this to a utils.py later if you want)
def fix_date(data_dict):
    date_str = data_dict.get("last_updated")
    if date_str and isinstance(date_str, str):
        data_dict["last_updated"] = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    return data_dict

# --- GET ALL LOCATIONS ---
@router.get("/", response_model=dict)
async def get_locations(session: Session = Depends(get_session)):
    # Select all location records
    statement = (
        select(Location)
        .options(
            joinedload(Location.evses)
            .joinedload(EVSE.connectors)
        )
    )
    locations = session.exec(statement).unique().all()

    data_as_schema = [LocationRead.model_validate(loc) for loc in locations]

    return {
        "status_code": 1000,
        "status_message": "Success",
        "data": data_as_schema  # <-- LocationRead will now see 'evses'
    }


# --- GET SPECIFIC LOCATION ---
@router.get("/{country_code}/{party_id}/{location_id}", response_model=dict)
async def get_location(
        country_code: str,
        party_id: str,
        location_id: str,
        session: Session = Depends(get_session)
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

    location = session.exec(statement).unique().first()

    print(f"DEBUG: Found Location {location.id}")
    print(f"DEBUG: Number of EVSEs found: {len(location.evses)}")
    for e in location.evses:
        print(f"DEBUG: EVSE {e.uid} has {len(e.connectors)} connectors")

    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    # We return the OCPI wrapper.
    # FastAPI will use 'LocationRead' logic to fill the 'data' field.

    data_as_schema = LocationRead.model_validate(location)

    return {
        "status_code": 1000,
        "status_message": "Success",
        "data": data_as_schema  # <-- LocationRead will now see 'evses'
    }

# --- GET SPECIFIC LOCATION ---
@router.get("/{country_code}/{party_id}/{location_id}/{evse_uid}", response_model=dict)
async def get_evse(
        country_code: str,
        party_id: str,
        location_id: str,
        evse_uid: str,
        session: Session = Depends(get_session)
):
    # Use joinedload to ensure the data is fetched from the DB
    statement = (
        select(EVSE)
        .where(EVSE.uid == evse_uid)
        .where(EVSE.location_id == location_id)
        .options(
            joinedload(EVSE.connectors)
        )
    )

    evse = session.exec(statement).unique().first()

    print(f"DEBUG: Found EVSE {evse.uid}")

    if not evse:
        raise HTTPException(status_code=404, detail="Location not found")

    # We return the OCPI wrapper.
    # FastAPI will use 'LocationRead' logic to fill the 'data' field.

    data_as_schema = EVSERead.model_validate(evse)

    return {
        "status_code": 1000,
        "status_message": "Success",
        "data": data_as_schema  # <-- LocationRead will now see 'evses'
    }

@router.put("/{country_code}/{party_id}/{location_id}")
async def put_location(
        country_code: str,
        party_id: str,
        location_id: str,
        raw_data: dict,
        session: Session = Depends(get_session)
):

    # 0. Inject the country_code and party_id into the dictionary.
    raw_data["country_code"] = country_code
    raw_data["party_id"] = party_id

    # 1. Clean up existing data (Standard OCPI PUT replaces the resource)
    existing_loc = session.get(Location, location_id)
    if existing_loc:
        session.delete(existing_loc)
        session.commit()

    # 2. Re-use your successful "Tree Building" logic
    try:
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
        session.commit()
        session.refresh(location_obj)

        return {"status_code": 1000, "status_message": "Success", "data": [location_obj.id]}

    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{country_code}/{party_id}/{location_id}")
async def patch_location(
        country_code: str,
        party_id: str,
        location_id: str,
        patch_data: dict,
        session: Session = Depends(get_session)
):
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
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    # 4. Save changes
    session.add(db_location)
    session.commit()
    session.refresh(db_location)

    return {
        "status_code": 1000,
        "status_message": "Location patched successfully",
        "data": [db_location.id]
    }

@router.patch("/{country_code}/{party_id}/{location_id}/{evse_uid}")
async def patch_evse(
        country_code: str,
        party_id: str,
        location_id: str,
        evse_uid: str,
        patch_data: dict,
        session: Session = Depends(get_session)
):
    # 1. Fetch the specific EVSE and verify it belongs to the Location
    statement = select(EVSE).where(EVSE.uid == evse_uid, EVSE.location_id == location_id)
    db_evse = session.exec(statement).first()

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
        session.rollback()
        # This will now catch the Enum error from the EVSEUpdate schema
        raise HTTPException(status_code=400, detail=f"Validation Error: {str(e)}")

    # 4. Cascade 'last_updated' to the Parent Location
    db_evse.location.last_updated = datetime.now()

    session.add(db_evse)
    session.commit()
    session.refresh(db_evse)

    data_as_schema = EVSERead.model_validate(db_evse)

    return {
        "status_code": 1000,
        "status_message": "EVSE updated successfully",
        "data": [data_as_schema]
    }