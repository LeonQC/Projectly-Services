from fastapi import HTTPException, status
from sqlalchemy import delete, exists, func, or_, select
from sqlalchemy.orm import Session

from app.models.notification import Invitation
from app.models.project import Project
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


def user_can_admin_workspace(db: Session, user_id: int, workspace_id: int) -> bool:
    workspace = get_workspace_or_404(db, workspace_id)
    if workspace.owner_id == user_id:
        return True

    statement = select(
        exists().where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.role.in_(("admin", "owner")),
        )
    )
    return bool(db.scalar(statement))


def ensure_workspace_admin(db: Session, user_id: int, workspace_id: int) -> Workspace:
    workspace = ensure_workspace_access(db, user_id, workspace_id)
    if not user_can_admin_workspace(db, user_id, workspace_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace admin access required")
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


def user_has_workspace_name_conflict(
    db: Session,
    current_user_id: int,
    name: str,
    *,
    exclude_workspace_id: int | None = None,
) -> bool:
    normalized_name = name.strip().lower()
    member_workspace_ids = select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == current_user_id)
    statement = select(
        exists().where(
            Workspace.archived.is_(False),
            func.lower(Workspace.name) == normalized_name,
            or_(
                Workspace.owner_id == current_user_id,
                Workspace.id.in_(member_workspace_ids),
            ),
        )
    )
    if exclude_workspace_id is not None:
        statement = select(
            exists().where(
                Workspace.archived.is_(False),
                Workspace.id != exclude_workspace_id,
                func.lower(Workspace.name) == normalized_name,
                or_(
                    Workspace.owner_id == current_user_id,
                    Workspace.id.in_(member_workspace_ids),
                ),
            )
        )
    return bool(db.scalar(statement))


def ensure_workspace_name_available(
    db: Session,
    current_user_id: int,
    name: str,
    *,
    exclude_workspace_id: int | None = None,
) -> None:
    if user_has_workspace_name_conflict(db, current_user_id, name, exclude_workspace_id=exclude_workspace_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workspace name already exists")


def create_workspace(db: Session, current_user_id: int, payload: WorkspaceCreate) -> Workspace:
    get_user_or_404(db, current_user_id)
    ensure_workspace_name_available(db, current_user_id, payload.name)
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
    if "name" in update_data:
        ensure_workspace_name_available(db, current_user_id, update_data["name"], exclude_workspace_id=workspace_id)
    for field, value in update_data.items():
        setattr(workspace, field, value)

    db.commit()
    db.refresh(workspace)
    return workspace


def archive_workspace(db: Session, workspace_id: int, current_user_id: int) -> None:
    workspace = ensure_workspace_owner(db, current_user_id, workspace_id)
    workspace.archived = True
    db.commit()


def list_deleted_workspaces(db: Session, current_user_id: int) -> list[Workspace]:
    get_user_or_404(db, current_user_id)
    member_workspace_ids = select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == current_user_id)
    statement = (
        select(Workspace)
        .where(
            Workspace.archived.is_(True),
            or_(
                Workspace.owner_id == current_user_id,
                Workspace.id.in_(member_workspace_ids),
            ),
        )
        .order_by(Workspace.updated_at.desc(), Workspace.id.desc())
    )
    return list(db.scalars(statement).all())


def restore_workspace(db: Session, workspace_id: int, current_user_id: int) -> Workspace:
    workspace = db.get(Workspace, workspace_id)
    if workspace is None or workspace.owner_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    ensure_workspace_name_available(db, current_user_id, workspace.name, exclude_workspace_id=workspace_id)
    workspace.archived = False
    db.commit()
    db.refresh(workspace)
    return workspace


def permanently_delete_workspace(db: Session, workspace_id: int, current_user_id: int) -> None:
    from app.services.projects import permanently_delete_project_records

    workspace = db.get(Workspace, workspace_id)
    if workspace is None or workspace.owner_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    project_ids = list(db.scalars(select(Project.id).where(Project.workspace_id == workspace_id)).all())
    for project_id in project_ids:
        permanently_delete_project_records(db, project_id)

    db.execute(delete(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id))
    db.execute(delete(Invitation).where(Invitation.target_type == "workspace", Invitation.target_id == workspace_id))
    db.execute(delete(Workspace).where(Workspace.id == workspace_id))
    db.commit()
