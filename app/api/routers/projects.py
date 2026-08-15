from fastapi import APIRouter, status

from app.api.deps import AuthenticatedUserId, DbSession
from app.core.responses import success_response
from app.schemas.member import ProjectMemberResponse
from app.schemas.project import GuestProjectResponse, ProjectResponse, ProjectUpdate
from app.services import members as members_service
from app.services import projects as projects_service


router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/deleted")
def list_deleted_projects(db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    projects = projects_service.list_deleted_projects(db, current_user_id)
    return success_response(data=[ProjectResponse.model_validate(project) for project in projects])


@router.get("/guest")
def list_guest_projects(db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    projects = projects_service.list_guest_projects(db, current_user_id)
    return success_response(
        data=[
            GuestProjectResponse.model_validate(
                {
                    **ProjectResponse.model_validate(project).model_dump(),
                    "workspace_name": workspace_name,
                }
            )
            for project, workspace_name in projects
        ]
    )


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


@router.patch("/{project_id}/restore")
def restore_project(project_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    project = projects_service.restore_project(db, project_id, current_user_id)
    return success_response(data=ProjectResponse.model_validate(project), message="Project restored")


@router.delete("/{project_id}/permanent")
def permanently_delete_project(project_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    projects_service.permanently_delete_project(db, project_id, current_user_id)
    return success_response(message="Project permanently deleted")


@router.get("/{project_id}/members")
def list_project_members(project_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    members = members_service.list_project_members(db, project_id, current_user_id)
    return success_response(data=[ProjectMemberResponse.model_validate(member) for member in members])


@router.delete("/members/{member_id}")
def delete_project_member(member_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    members_service.delete_project_member(db, member_id, current_user_id)
    return success_response(message="Project member removed")
