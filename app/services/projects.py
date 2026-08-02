from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.workspaces import ensure_workspace_access


def get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def ensure_project_access(db: Session, user_id: int, project_id: int) -> Project:
    project = get_project_or_404(db, project_id)
    ensure_workspace_access(db, user_id, project.workspace_id)
    return project


def list_workspace_projects(db: Session, workspace_id: int, current_user_id: int) -> list[Project]:
    ensure_workspace_access(db, current_user_id, workspace_id)
    statement = (
        select(Project)
        .where(Project.workspace_id == workspace_id, Project.archived.is_(False))
        .order_by(Project.position.asc(), Project.created_at.asc(), Project.id.asc())
    )
    return list(db.scalars(statement).all())


def create_project(
    db: Session,
    workspace_id: int,
    current_user_id: int,
    payload: ProjectCreate,
) -> Project:
    ensure_workspace_access(db, current_user_id, workspace_id)
    project = Project(
        workspace_id=workspace_id,
        name=payload.name,
        description=payload.description,
        position=payload.position,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def get_project(db: Session, project_id: int, current_user_id: int) -> Project:
    return ensure_project_access(db, current_user_id, project_id)


def update_project(
    db: Session,
    project_id: int,
    current_user_id: int,
    payload: ProjectUpdate,
) -> Project:
    project = ensure_project_access(db, current_user_id, project_id)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)
    return project


def archive_project(db: Session, project_id: int, current_user_id: int) -> None:
    project = ensure_project_access(db, current_user_id, project_id)
    project.archived = True
    db.commit()
