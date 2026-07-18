from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.db.session import get_db


DbSession = Annotated[Session, Depends(get_db)]


def get_current_user_id(x_user_id: Annotated[int, Header(alias="X-User-Id")] = 1) -> int:
    return x_user_id


CurrentUserId = Annotated[int, Depends(get_current_user_id)]
