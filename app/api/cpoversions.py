from datetime import datetime, timezone
from fastapi import APIRouter, Request
from app.config import settings
from app.core.utils import get_timestamp, fix_date
router = APIRouter()

@router.get("/versions")
async def get_available_version(request: Request):

    base = settings.BASE_URL.rstrip("/")
    #timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "status_code": 1000,
        "status_message": "Success",
        "timestamp": get_timestamp(),
        "data": [
            {
                "version": settings.OCPI_VERSION,
                "url": f"{base}/ocpi/cpo/{settings.OCPI_VERSION}"
            }
        ]
    }

@router.get("/2.1.1")
async def get_211_version_details(request: Request):
    # We use settings.BASE_URL to build the absolute paths
    base = settings.BASE_URL.rstrip("/")
    #timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "status_code": 1000,
        "status_message": "Success",
        "timestamp": get_timestamp(),
        "data": {
            "version": settings.OCPI_VERSION,
            "endpoints": [
                {
                    "identifier": "credentials",
                    "url": f"{base}/ocpi/cpo/{settings.OCPI_VERSION}/credentials"
                },
                {
                    "identifier": "locations",
                    "url": f"{base}/ocpi/cpo/{settings.OCPI_VERSION}/locations"
                },
                {
                    "identifier": "tariffs",
                    "url": f"{base}/ocpi/cpo/{settings.OCPI_VERSION}/tariffs"
                }
            ]
        }
    }