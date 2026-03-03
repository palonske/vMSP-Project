from datetime import datetime, timezone
from fastapi import APIRouter, Request
from app.config import settings

router = APIRouter()

@router.get("/versions")
async def get_available_version(request: Request):

    base = settings.BASE_URL.rstrip("/")
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "status_code": 1000,
        "status_message": "Success",
        "timestamp": f"{timestamp}",
        "data": [
            {
                "version": "2.1.1",
                "url": f"{base}/ocpi/emsp/2.1.1"
            }
        ]
    }

@router.get("/2.1.1")
async def get_211_version_details(request: Request):
    # We use settings.BASE_URL to build the absolute paths
    base = settings.BASE_URL.rstrip("/")
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "status_code": 1000,
        "status_message": "Success",
        "timestamp": f"{timestamp}",
        "data": {
            "version": "2.1.1",
            "endpoints": [
                {
                    "identifier": "credentials",
                    "url": f"{base}/ocpi/emsp/2.1.1/credentials"
                },
                {
                    "identifier": "locations",
                    "url": f"{base}/ocpi/emsp/2.1.1/locations"
                },
                {
                    "identifier": "tariffs",
                    "url": f"{base}/ocpi/emsp/2.1.1/tariffs"
                }
            ]
        }
    }