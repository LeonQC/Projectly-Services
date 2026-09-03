from fastapi import APIRouter

from app.api.deps import AuthenticatedUserId, DbSession
from app.core.responses import success_response
from app.schemas.rag import RagRetrieveRequest
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