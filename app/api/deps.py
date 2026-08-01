from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db


DbSession = Annotated[Session, Depends(get_db)]
bearer_scheme = HTTPBearer(auto_error=False)


def get_bearer_user_id(credentials: Optional[HTTPAuthorizationCredentials]) -> int:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header is required")

    if credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")

    payload = decode_access_token(credentials.credentials)
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.isdigit():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")
    return int(subject)


def get_current_user_id(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)] = None,
    x_user_id: Annotated[Optional[int], Header(alias="X-User-Id")] = None,
) -> int:
    if credentials is not None:
        return get_bearer_user_id(credentials)

    return x_user_id or 1


def get_authenticated_user_id(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)] = None,
) -> int:
    return get_bearer_user_id(credentials)


CurrentUserId = Annotated[int, Depends(get_current_user_id)]
AuthenticatedUserId = Annotated[int, Depends(get_authenticated_user_id)]
