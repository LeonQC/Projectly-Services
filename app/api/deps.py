from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db


DbSession = Annotated[Session, Depends(get_db)]


def get_current_user_id(
    authorization: Annotated[Optional[str], Header(alias="Authorization")] = None,
    x_user_id: Annotated[Optional[int], Header(alias="X-User-Id")] = None,
) -> int:
    if authorization:
        token_type, _, token = authorization.partition(" ")
        if token_type.lower() != "bearer" or not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")

        payload = decode_access_token(token)
        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject.isdigit():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")
        return int(subject)

    return x_user_id or 1


CurrentUserId = Annotated[int, Depends(get_current_user_id)]
