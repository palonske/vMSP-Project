from fastapi import APIRouter, Depends, HTTPException

router = APIRouter()

@router.get(path="/")
async def get_211_versions():
    return {
        ""
    }
