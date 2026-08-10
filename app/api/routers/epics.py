from fastapi import APIRouter, status

from app.api.deps import AuthenticatedUserId, DbSession
from app.core.responses import success_response
from app.schemas.epic import EpicCreate, EpicResponse, EpicUpdate
from app.services import epics as epics_service


router = APIRouter(tags=["epics"])


@router.get("/projects/{project_id}/epics")
def list_project_epics(project_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    epics = epics_service.list_project_epics(db, project_id, current_user_id)
    return success_response(data=[EpicResponse.model_validate(epic) for epic in epics])


@router.post("/projects/{project_id}/epics", status_code=status.HTTP_201_CREATED)
def create_project_epic(
    project_id: int,
    payload: EpicCreate,
    db: DbSession,
    current_user_id: AuthenticatedUserId,
) -> dict:
    epic = epics_service.create_epic(db, project_id, current_user_id, payload)
    return success_response(data=EpicResponse.model_validate(epic), message="Epic created")


@router.get("/epics/{epic_id}")
def get_epic(epic_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    epic = epics_service.get_epic(db, epic_id, current_user_id)
    return success_response(data=EpicResponse.model_validate(epic))


@router.patch("/epics/{epic_id}")
def update_epic(
    epic_id: int,
    payload: EpicUpdate,
    db: DbSession,
    current_user_id: AuthenticatedUserId,
) -> dict:
    epic = epics_service.update_epic(db, epic_id, current_user_id, payload)
    return success_response(data=EpicResponse.model_validate(epic), message="Epic updated")


@router.delete("/epics/{epic_id}")
def delete_epic(epic_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    epics_service.archive_epic(db, epic_id, current_user_id)
    return success_response(message="Epic deleted")


@router.patch("/epics/{epic_id}/restore")
def restore_epic(epic_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    epic = epics_service.restore_epic(db, epic_id, current_user_id)
    return success_response(data=EpicResponse.model_validate(epic), message="Epic restored")


@router.delete("/epics/{epic_id}/permanent")
def permanently_delete_epic(epic_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    epics_service.permanently_delete_epic(db, epic_id, current_user_id)
    return success_response(message="Epic permanently deleted")
