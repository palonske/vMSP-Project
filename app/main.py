from xml.etree.ElementTree import tostring

from fastapi import FastAPI
from datetime import datetime
from zoneinfo import ZoneInfo
from app.models.location import Location

app = FastAPI()


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

def main():
    print("Hello from emspprojectv1!")
    test_location()

def log(string):
    now_utc = datetime.now(ZoneInfo("UTC"))
    logger = now_utc.strftime("%Y-%m-%d %H:%M:%S") + ":  Sending API Response:  " + string
    print(logger)

if __name__ == "__main__":
    main()

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