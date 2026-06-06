from fastapi import APIRouter
from pydantic import BaseModel
from src.core.dsa import router as fast_router

router = APIRouter()

class IntentRequest(BaseModel):
    query: str

@router.post("/")
async def handle_intent(req: IntentRequest):
    action = fast_router.search(req.query)
    if action:
        return {"fast_path": True, "action": action, "status": "executed"}
    
    # Hand-off to Module 2 (LangGraph Brain)
    return {"fast_path": False, "status": "routed_to_brain"}