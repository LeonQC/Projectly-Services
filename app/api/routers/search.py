from fastapi import APIRouter, Query

from app.api.deps import AuthenticatedUserId, DbSession
from app.services.search import search_cards, search_workspace
from app.services.workspaces import ensure_workspace_access


router = APIRouter(
    prefix="/search",
    tags=["search"],
)


@router.get("/cards")
def search_card_endpoint(
    db: DbSession,
    current_user_id: AuthenticatedUserId,
    workspace_id: int,
    q: str = Query(min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    ensure_workspace_access(
        db,
        current_user_id,
        workspace_id,
    )

    results = search_cards(
        workspace_id=workspace_id,
        query=q,
        limit=limit,
    )

    return {
        "items": results,
        "count": len(results),
    }


@router.get("")
def search_workspace_endpoint(
    db: DbSession,
    current_user_id: AuthenticatedUserId,
    workspace_id: int,
    q: str = Query(min_length=1),
    limit: int = Query(default=10, ge=1, le=50),
):
    ensure_workspace_access(
        db,
        current_user_id,
        workspace_id,
    )

    results = search_workspace(
        workspace_id=workspace_id,
        query=q,
        limit=limit,
    )

    count = sum(len(items) for items in results.values())

    return {
        **results,
        "count": count,
    }
