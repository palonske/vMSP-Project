from datetime import datetime, timezone
from fastapi import APIRouter, Request
from app.config import settings
from app.core.utils import get_timestamp

router = APIRouter()

@router.get("/versions")
async def get_available_versions(request: Request):
    """Return all supported OCPI versions."""
    base = settings.BASE_URL.rstrip("/")

    return {
        "status_code": 1000,
        "status_message": "Success",
        "timestamp": get_timestamp(),
        "data": [
            {"version": version, "url": f"{base}/ocpi/emsp/{version}"}
            for version in settings.SUPPORTED_OCPI_VERSIONS
        ]
    }

@router.get("/{version}")
async def get_version_details(request: Request, version: str):
    """Return endpoints for a specific OCPI version."""
    if version not in settings.SUPPORTED_OCPI_VERSIONS:
        return {
            "status_code": 3000,
            "status_message": f"Unsupported version: {version}",
            "timestamp": get_timestamp(),
            "data": None
        }

    base = settings.BASE_URL.rstrip("/")

    return {
        "status_code": 1000,
        "status_message": "Success",
        "timestamp": get_timestamp(),
        "data": {
            "version": version,
            "endpoints": [
                {
                    "identifier": "credentials",
                    "url": f"{base}/ocpi/emsp/{version}/credentials"
                },
                {
                    "identifier": "locations",
                    "url": f"{base}/ocpi/emsp/{version}/locations"
                },
                {
                    "identifier": "tariffs",
                    "url": f"{base}/ocpi/emsp/{version}/tariffs"
                }
            ]
        }
    }