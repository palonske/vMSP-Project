from xml.etree.ElementTree import tostring

from fastapi import FastAPI
from datetime import datetime
from zoneinfo import ZoneInfo
from app.models.location import Location
from app.models.evse import EVSE
from app.models.connector import Connector
from app.database import engine, create_db_and_tables
from sqlmodel import Session
from app.api.v2_1_1 import locations, tariffs, credentials211
from app.api import emspversions, credentials, cpoversions
from app.core.middleware import OCPILoggingMiddleware, setup_logging

app = FastAPI(title="OCPI Platform")

# Set up logging
setup_logging()

# Add logging middleware
app.add_middleware(OCPILoggingMiddleware)

app.include_router(
    credentials211.cporouter,
    prefix="/ocpi/cpo/2.1.1/credentials",
    tags=["CPO Credentials v2.1.1"]
)
app.include_router(
    credentials211.emsprouter,
    prefix="/ocpi/emsp/2.1.1/credentials",
    tags=["EMSP Credentials v2.1.1"]
)
app.include_router(
    locations.emsprouter,
    prefix="/ocpi/emsp/2.1.1/locations",
    tags=["Locations v2.1.1"]
)
app.include_router(
    locations.cporouter,
    prefix="/ocpi/cpo/2.1.1/locations",
    tags=["Locations v2.1.1"]
)
app.include_router(
    tariffs.emsprouter,
    prefix="/ocpi/emsp/2.1.1/tariffs",
    tags=["Tariffs v2.1.1"]
)
app.include_router(
    tariffs.cporouter,
    prefix="/ocpi/cpo/2.1.1/tariffs",
    tags=["Tariffs v2.1.1"]
)
app.include_router(
   emspversions.router,
    prefix="/ocpi/emsp",
    tags=["EMSP Versions"]
)
app.include_router(
    cpoversions.router,
    prefix="/ocpi/cpo",
    tags=["CPO Versions"]
)
app.include_router(
    credentials.router,
    prefix="/ocpi",
    tags=["credentials"]
)

@app.get("/")
async def root():
    message = "Hello World"
    log(message)
    return {"message": message}

@app.get("/testLocation")
async def root():
    test_location()
    message = "testLocationCompleted"
    log(message)
    return {"message": message}

@app.get("/testLocationdb")
async def root():
    test_location_db()
    message = "Test Location stored in Database"
    log(message)
    return {"message": message}

def main():
    print("Hello from emspprojectv1!")
    test_location()

def log(string):
    now_utc = datetime.now(ZoneInfo("UTC"))
    logger = now_utc.strftime("%Y-%m-%d %H:%M:%S") + ":  Sending API Response:  " + string
    print(logger)

if __name__ == "__main__":
    main()

def fix_date(data_dict):
    """Helper to convert OCPI date strings to Python datetime objects."""
    date_str = data_dict.get("last_updated")
    if date_str and isinstance(date_str, str):
        # Replace 'Z' with UTC offset so fromisoformat works
        data_dict["last_updated"] = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    return data_dict

def test_location_db():
    raw_data = {
        "id": "LOC1",
        "type": "ON_STREET",
        "name": "Gent Zuid",
        "address": "F.Rooseveltlaan 3A",
        "city": "Gent",
        "postal_code": "9000",
        "country": "BEL",
        "coordinates": {
            "latitude": "51.047599",
            "longitude": "3.729944"
        },
        "evses": [{
            "uid": "3256",
            "evse_id": "BE-BEC-E041503001",
            "status": "AVAILABLE",
            "status_schedule": [],
            "capabilities": [
                "RESERVABLE"
            ],
            "connectors": [{
                "id": "1",
                "standard": "IEC_62196_T2",
                "format": "CABLE",
                "power_type": "AC_3_PHASE",
                "voltage": 220,
                "amperage": 16,
                "tariff_id": "11",
                "last_updated": "2015-03-16T10:10:02Z"
            }, {
                "id": "2",
                "standard": "IEC_62196_T2",
                "format": "SOCKET",
                "power_type": "AC_3_PHASE",
                "voltage": 220,
                "amperage": 16,
                "tariff_id": "11",
                "last_updated": "2015-03-18T08:12:01Z"
            }],
            "physical_reference": "1",
            "floor_level": "-1",
            "last_updated": "2015-06-28T08:12:01Z"
        }, {
            "uid": "3257",
            "evse_id": "BE-BEC-E041503002",
            "status": "RESERVED",
            "capabilities": [
                "RESERVABLE"
            ],
            "connectors": [{
                "id": "1",
                "standard": "IEC_62196_T2",
                "format": "SOCKET",
                "power_type": "AC_3_PHASE",
                "voltage": 220,
                "amperage": 16,
                "tariff_id": "12",
                "last_updated": "2015-06-29T20:39:09Z"
            }],
            "physical_reference": "2",
            "floor_level": "-2",
            "last_updated": "2015-06-29T20:39:09Z"
        }],
        "operator": {
            "name": "BeCharged"
        },
        "last_updated": "2015-06-29T20:39:09Z"
    }

    fix_date(raw_data)
    evses_raw = raw_data.pop("evses", [])

    location_obj = Location(**raw_data)

    for e_raw in evses_raw:
        # Remove connectors from the EVSE dict before creating the object
        fix_date(e_raw)
        connectors_raw = e_raw.pop("connectors", [])

        # Create the EVSE object (it now has NO connectors attached)
        evse_obj = EVSE(**e_raw, location_id=location_obj.id)

        for c_raw in connectors_raw:
            # Create the Connector object
            fix_date(c_raw)
            connector_obj = Connector(**c_raw, evse_uid=evse_obj.uid, location_id=location_obj.id)
            # Link Connector -> EVSE (Using objects, not dicts!)
            evse_obj.connectors.append(connector_obj)

        # Link EVSE -> Location (Using objects, not dicts!)
        location_obj.evses.append(evse_obj)

    # Persist it to the database
    with Session(engine) as session:
        session.add(location_obj)  # Stage the object
        session.commit()          # Write to disk
        session.refresh(location_obj) # Get the DB-generated 'id' back into the object

    log(f"Location saved with ID: {location_obj.id}")


def test_location():
    raw_data = {
        "id": "LOC1",
        "type": "ON_STREET",
        "name": "Gent Zuid",
        "address": "F.Rooseveltlaan 3A",
        "city": "Gent",
        "postal_code": "9000",
        "country": "BEL",
        "coordinates": {
            "latitude": "51.047599",
            "longitude": "3.729944"
        },
        "evses": [{
            "uid": "3256",
            "evse_id": "BE-BEC-E041503001",
            "status": "AVAILABLE",
            "status_schedule": [],
            "capabilities": [
                "RESERVABLE"
            ],
            "connectors": [{
                "id": "1",
                "standard": "IEC_62196_T2",
                "format": "CABLE",
                "power_type": "AC_3_PHASE",
                "voltage": 220,
                "amperage": 16,
                "tariff_id": "11",
                "last_updated": "2015-03-16T10:10:02Z"
            }, {
                "id": "2",
                "standard": "IEC_62196_T2",
                "format": "SOCKET",
                "power_type": "AC_3_PHASE",
                "voltage": 220,
                "amperage": 16,
                "tariff_id": "11",
                "last_updated": "2015-03-18T08:12:01Z"
            }],
            "physical_reference": "1",
            "floor_level": "-1",
            "last_updated": "2015-06-28T08:12:01Z"
        }, {
            "uid": "3257",
            "evse_id": "BE-BEC-E041503002",
            "status": "RESERVED",
            "capabilities": [
                "RESERVABLE"
            ],
            "connectors": [{
                "id": "1",
                "standard": "IEC_62196_T2",
                "format": "SOCKET",
                "power_type": "AC_3_PHASE",
                "voltage": 220,
                "amperage": 16,
                "tariff_id": "12",
                "last_updated": "2015-06-29T20:39:09Z"
            }],
            "physical_reference": "2",
            "floor_level": "-2",
            "last_updated": "2015-06-29T20:39:09Z"
        }],
        "operator": {
            "name": "BeCharged"
        },
        "last_updated": "2015-06-29T20:39:09Z"
    }

    location_obj = Location(**raw_data)

    print(location_obj.evses[0].status)
    print(location_obj.last_updated)
    print(location_obj.model_dump_json())