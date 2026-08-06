from fastapi import APIRouter, status

from app.api.deps import AuthenticatedUserId, DbSession
from app.core.responses import success_response
from app.schemas.member import MemberInviteRequest, ProjectMemberResponse
from app.schemas.project import ProjectResponse, ProjectUpdate
from app.services import members as members_service
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


@router.get("/{project_id}/members")
def list_project_members(project_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    members = members_service.list_project_members(db, project_id, current_user_id)
    return success_response(data=[ProjectMemberResponse.model_validate(member) for member in members])


@router.post("/{project_id}/members", status_code=status.HTTP_201_CREATED)
def invite_project_member(
    project_id: int,
    payload: MemberInviteRequest,
    db: DbSession,
    current_user_id: AuthenticatedUserId,
) -> dict:
    member = members_service.create_project_member(db, project_id, current_user_id, payload)
    return success_response(data=ProjectMemberResponse.model_validate(member), message="Project member invited")


@router.delete("/members/{member_id}")
def delete_project_member(member_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    members_service.delete_project_member(db, member_id, current_user_id)
    return success_response(message="Project member removed")
