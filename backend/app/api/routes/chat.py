from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Conversation
from app.schemas import ChatRequest, ChatResponse
from app.services.container import services

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    if request.conversation_id and not db.get(Conversation, request.conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return await services()[1].answer(request, db)
