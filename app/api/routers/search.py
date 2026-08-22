from fastapi import APIRouter, Query

from app.api.deps import AuthenticatedUserId, DbSession
from app.services.search import (
    get_accessible_project_ids,
    get_accessible_workspace_ids,
    search_cards,
    search_workspace,
)
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
    workspace_id: int | None = None,
    q: str = Query(min_length=1),
    limit: int = Query(default=10, ge=1, le=50),
    scope: str = Query(default="workspace", pattern="^(workspace|all)$"),
    include_archived: bool = Query(default=False),
):
    if scope == "all":
        workspace_ids = get_accessible_workspace_ids(
            db,
            current_user_id,
            include_archived=include_archived,
        )
        project_ids = get_accessible_project_ids(
            db,
            current_user_id,
            workspace_ids,
            include_archived=include_archived,
        )
        if not workspace_ids and not project_ids:
            return {
                "projects": [],
                "cards": [],
                "comments": [],
                "github_events": [],
                "items": [],
                "count": 0,
            }
        search_workspace_id: int | list[int] = workspace_ids
        search_project_ids = project_ids
    else:
        if workspace_id is None:
            return {
                "projects": [],
                "cards": [],
                "comments": [],
                "github_events": [],
                "items": [],
                "count": 0,
            }
        if include_archived:
            accessible_workspace_ids = get_accessible_workspace_ids(
                db,
                current_user_id,
                include_archived=True,
            )
            if workspace_id not in accessible_workspace_ids:
                return {
                    "projects": [],
                    "cards": [],
                    "comments": [],
                    "github_events": [],
                    "items": [],
                    "count": 0,
                }
        else:
            ensure_workspace_access(
                db,
                current_user_id,
                workspace_id,
            )
        search_workspace_id = workspace_id
        search_project_ids = get_accessible_project_ids(
            db,
            current_user_id,
            [workspace_id],
            include_archived=include_archived,
        )

    results = search_workspace(
        workspace_id=search_workspace_id,
        project_ids=search_project_ids,
        include_archived=include_archived,
        query=q,
        limit=limit,
    )

    count = len(results["items"])

    return {
        **results,
        "count": count,
    }
