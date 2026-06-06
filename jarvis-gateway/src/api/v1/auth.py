from fastapi import APIRouter
from src.core.security import create_access_token
from pydantic import BaseModel

router = APIRouter()

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

@router.post("/token", response_model=TokenResponse)
async def login_for_access_token():
    # Mocking login for MVP - assumes single admin user
    access_token = create_access_token(data={"sub": "founder@jarvis.os"})
    return {"access_token": access_token, "token_type": "bearer"}