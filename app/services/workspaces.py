from fastapi import HTTPException, status
from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from app.models.workspace import Workspace, WorkspaceMember
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate
from app.services.access import get_user_or_404


def user_can_access_workspace(db: Session, user_id: int, workspace_id: int) -> bool:
    statement = select(
        exists().where(
            Workspace.id == workspace_id,
            Workspace.archived.is_(False),
            or_(
                Workspace.owner_id == user_id,
                exists().where(
                    WorkspaceMember.workspace_id == Workspace.id,
                    WorkspaceMember.user_id == user_id,
                ),
            ),
        )
    )
    return bool(db.scalar(statement))


def get_workspace_or_404(db: Session, workspace_id: int) -> Workspace:
    workspace = db.get(Workspace, workspace_id)
    if workspace is None or workspace.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return workspace


def ensure_workspace_access(db: Session, user_id: int, workspace_id: int) -> Workspace:
    get_user_or_404(db, user_id)
    workspace = get_workspace_or_404(db, workspace_id)
    if not user_can_access_workspace(db, user_id, workspace_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return workspace


def ensure_workspace_owner(db: Session, user_id: int, workspace_id: int) -> Workspace:
    workspace = ensure_workspace_access(db, user_id, workspace_id)
    if workspace.owner_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace owner access required")
    return workspace


def list_workspaces(db: Session, current_user_id: int) -> list[Workspace]:
    get_user_or_404(db, current_user_id)
    member_workspace_ids = select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == current_user_id)
    statement = (
        select(Workspace)
        .where(
            Workspace.archived.is_(False),
            or_(
                Workspace.owner_id == current_user_id,
                Workspace.id.in_(member_workspace_ids),
            ),
        )
        .order_by(Workspace.created_at.asc(), Workspace.id.asc())
    )
    return list(db.scalars(statement).all())


def create_workspace(db: Session, current_user_id: int, payload: WorkspaceCreate) -> Workspace:
    get_user_or_404(db, current_user_id)
    workspace = Workspace(name=payload.name, owner_id=current_user_id)
    db.add(workspace)
    db.flush()

    owner_member = WorkspaceMember(workspace_id=workspace.id, user_id=current_user_id, role="owner")
    db.add(owner_member)
    db.commit()
    db.refresh(workspace)
    return workspace


def update_workspace(
    db: Session,
    workspace_id: int,
    current_user_id: int,
    payload: WorkspaceUpdate,
) -> Workspace:
    workspace = ensure_workspace_owner(db, current_user_id, workspace_id)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(workspace, field, value)

    db.commit()
    db.refresh(workspace)
    return workspace


def archive_workspace(db: Session, workspace_id: int, current_user_id: int) -> None:
    workspace = ensure_workspace_owner(db, current_user_id, workspace_id)
    workspace.archived = True
    db.commit()
