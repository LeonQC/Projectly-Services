from fastapi import HTTPException, status
from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session

from app.models.notification import Invitation
from app.models.project import (
    Card,
    CardActivity,
    CardAttachment,
    CardComment,
    CardGitHubLink,
    CardLabel,
    CardLink,
    CardMember,
    Epic,
    Project,
    ProjectGuest,
    Sprint,
)
from app.models.workspace import Workspace
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.access import get_user_or_404
from app.services.search_events import publish_search_event
from app.services.workspaces import ensure_workspace_access, ensure_workspace_admin, user_can_access_workspace, user_can_admin_workspace


def get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def ensure_project_access(db: Session, user_id: int, project_id: int) -> Project:
    get_user_or_404(db, user_id)
    project = get_project_or_404(db, project_id)
    if not user_can_access_project(db, user_id, project):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def user_can_access_project(db: Session, user_id: int, project: Project) -> bool:
    if user_can_access_workspace(db, user_id, project.workspace_id):
        return True

    statement = select(
        exists().where(
            ProjectGuest.project_id == project.id,
            ProjectGuest.user_id == user_id,
        )
    )
    return bool(db.scalar(statement))


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
    ensure_workspace_admin(db, current_user_id, workspace_id)
    project = Project(
        workspace_id=workspace_id,
        name=payload.name,
        description=payload.description,
        position=payload.position,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    publish_search_event("project.created", {"project_id": project.id})
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
    ensure_workspace_admin(db, current_user_id, project.workspace_id)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)
    publish_search_event("project.updated", {"project_id": project.id})
    return project


def archive_project(db: Session, project_id: int, current_user_id: int) -> None:
    project = ensure_project_access(db, current_user_id, project_id)
    ensure_workspace_admin(db, current_user_id, project.workspace_id)
    project.archived = True
    db.commit()
    publish_search_event("project.archived", {"project_id": project.id})


def list_deleted_projects(db: Session, current_user_id: int) -> list[Project]:
    get_user_or_404(db, current_user_id)
    statement = (
        select(Project)
        .where(Project.archived.is_(True))
        .order_by(Project.updated_at.desc(), Project.id.desc())
    )
    projects = []
    for project in db.scalars(statement).all():
        try:
            if user_can_admin_workspace(db, current_user_id, project.workspace_id):
                projects.append(project)
        except HTTPException:
            continue
    return projects


def list_guest_projects(db: Session, current_user_id: int) -> list[tuple[Project, str]]:
    get_user_or_404(db, current_user_id)
    statement = (
        select(Project, Workspace.name)
        .join(ProjectGuest, ProjectGuest.project_id == Project.id)
        .join(Workspace, Workspace.id == Project.workspace_id)
        .where(
            ProjectGuest.user_id == current_user_id,
            Project.archived.is_(False),
            Workspace.archived.is_(False),
        )
        .order_by(Workspace.name.asc(), Project.position.asc(), Project.created_at.asc(), Project.id.asc())
    )
    rows = db.execute(statement).all()
    return [
        (project, workspace_name)
        for project, workspace_name in rows
        if not user_can_access_workspace(db, current_user_id, project.workspace_id)
    ]


def restore_project(db: Session, project_id: int, current_user_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    ensure_workspace_admin(db, current_user_id, project.workspace_id)
    project.archived = False
    db.commit()
    db.refresh(project)
    publish_search_event("project.restored", {"project_id": project.id})
    return project


def permanently_delete_project_records(db: Session, project_id: int) -> None:
    card_ids = list(db.scalars(select(Card.id).where(Card.project_id == project_id)).all())
    if card_ids:
        db.execute(delete(CardAttachment).where(CardAttachment.card_id.in_(card_ids)))
        db.execute(delete(CardComment).where(CardComment.card_id.in_(card_ids)))
        db.execute(delete(CardLabel).where(CardLabel.card_id.in_(card_ids)))
        db.execute(delete(CardMember).where(CardMember.card_id.in_(card_ids)))
        db.execute(delete(CardGitHubLink).where(CardGitHubLink.card_id.in_(card_ids)))
        db.execute(
            delete(CardLink).where(
                (CardLink.source_card_id.in_(card_ids)) | (CardLink.target_card_id.in_(card_ids))
            )
        )
        db.execute(delete(CardActivity).where(CardActivity.card_id.in_(card_ids)))
        db.execute(delete(Card).where(Card.id.in_(card_ids)))
    epic_ids = list(db.scalars(select(Epic.id).where(Epic.project_id == project_id)).all())
    if epic_ids:
        db.execute(delete(Sprint).where(Sprint.epic_id.in_(epic_ids)))
        db.execute(delete(Epic).where(Epic.id.in_(epic_ids)))

    db.execute(delete(ProjectGuest).where(ProjectGuest.project_id == project_id))
    db.execute(delete(Invitation).where(Invitation.target_type == "project", Invitation.target_id == project_id))
    db.execute(delete(Project).where(Project.id == project_id))
    publish_search_event("project.deleted", {"project_id": project_id})


def permanently_delete_project(db: Session, project_id: int, current_user_id: int) -> None:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    ensure_workspace_admin(db, current_user_id, project.workspace_id)
    permanently_delete_project_records(db, project_id)
    db.commit()
