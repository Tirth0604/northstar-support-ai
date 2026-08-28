import time

import structlog
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Citation, Conversation, Message
from app.providers.llm import LLMProvider
from app.rag.embeddings import EmbeddingProvider
from app.rag.prompts import REFUSAL, build_grounded_prompt
from app.rag.vector_store import LocalVectorStore
from app.schemas import ChatRequest, ChatResponse, CitationOut

logger = structlog.get_logger(__name__)


class ChatService:
    def __init__(self, settings: Settings, embeddings: EmbeddingProvider, vectors: LocalVectorStore, llm: LLMProvider):
        self.settings = settings
        self.embeddings = embeddings
        self.vectors = vectors
        self.llm = llm

    async def answer(self, request: ChatRequest, db: Session) -> ChatResponse:
        started = time.perf_counter()
        conversation = db.get(Conversation, request.conversation_id) if request.conversation_id else None
        if not conversation:
            conversation = Conversation(title=request.question[:72])
            db.add(conversation)
            db.flush()
        db.add(Message(conversation_id=conversation.id, role="user", content=request.question))
        query = self.embeddings.embed([request.question])[0]
        results = self.vectors.search(
            query,
            request.top_k or self.settings.retrieval_top_k,
            self.settings.similarity_threshold
            if request.similarity_threshold is None
            else request.similarity_threshold,
            request.document_ids,
        )
        grounded = len(results) >= self.settings.minimum_evidence
        prompt = build_grounded_prompt(
            request.question,
            [
                (index, result.chunk.document_name, result.chunk.text, result.chunk.page_number)
                for index, result in enumerate(results, 1)
            ],
        )
        answer = await self.llm.generate(request.question, prompt, results) if grounded else REFUSAL
        grounded = grounded and answer.strip() != REFUSAL
        elapsed = round((time.perf_counter() - started) * 1000)
        message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=answer,
            latency_ms=elapsed,
            grounding_status="grounded" if grounded else "insufficient_evidence",
            retrieved_sources=[{"chunk_id": result.chunk.id, "score": result.score} for result in results],
        )
        db.add(message)
        db.flush()
        citations = []
        for result in results:
            citation = Citation(
                message_id=message.id,
                document_id=result.chunk.document_id,
                document_name=result.chunk.document_name,
                chunk_id=result.chunk.id,
                page_number=result.chunk.page_number,
                excerpt=result.chunk.text[:420],
                relevance_score=result.score,
            )
            db.add(citation)
            citations.append(citation)
        db.commit()
        logger.info(
            "rag_answer",
            conversation_id=conversation.id,
            message_id=message.id,
            chunk_ids=[result.chunk.id for result in results],
            grounded=grounded,
            latency_ms=elapsed,
        )
        output = [CitationOut.model_validate(item) for item in citations]
        confidence = round(sum(result.score for result in results) / len(results), 3) if results else 0.0
        return ChatResponse(
            answer=answer,
            citations=output,
            retrieved_sources=output,
            grounding_status=message.grounding_status or "insufficient_evidence",
            confidence=max(0.0, min(1.0, confidence)),
            conversation_id=conversation.id,
            message_id=message.id,
            response_time_ms=elapsed,
        )
