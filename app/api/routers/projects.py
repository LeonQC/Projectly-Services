from fastapi import APIRouter

from app.api.deps import AuthenticatedUserId, DbSession
from app.core.responses import success_response
from app.schemas.project import ProjectResponse, ProjectUpdate
from app.services import projects as projects_service


router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/{project_id}")
def get_project(project_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    project = projects_service.get_project(db, project_id, current_user_id)
    return success_response(data=ProjectResponse.model_validate(project))


@router.patch("/{project_id}")
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: DbSession,
    current_user_id: AuthenticatedUserId,
) -> dict:
    project = projects_service.update_project(db, project_id, current_user_id, payload)
    return success_response(data=ProjectResponse.model_validate(project), message="Project updated")


@router.delete("/{project_id}")
def delete_project(project_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    projects_service.archive_project(db, project_id, current_user_id)
    return success_response(message="Project deleted")
