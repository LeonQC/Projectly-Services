from fastapi import APIRouter

from app.api.deps import AuthenticatedUserId, DbSession
from app.core.responses import success_response
from app.schemas.rag import RagAskRequest, RagRetrieveRequest
from app.services.rag_answering import answer_rag_question
from app.services.rag_retrieval import retrieve_attachment_chunks

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/retrieve")
def retrieve_rag_context(
    payload: RagRetrieveRequest,
    db: DbSession,
    current_user_id: AuthenticatedUserId,
) -> dict:
    result = retrieve_attachment_chunks(db, current_user_id, payload)
    return success_response(data=result.model_dump())

@router.post("/ask")
def ask_rag_question(
    payload: RagAskRequest,
    db: DbSession,
    current_user_id: AuthenticatedUserId,
) -> dict:
    result = answer_rag_question(db, current_user_id, payload)
    return success_response(data=result.model_dump())