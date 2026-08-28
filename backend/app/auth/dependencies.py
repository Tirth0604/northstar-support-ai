from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.service import decode_access_token
from app.db.session import get_db
from app.models import CustomerProfile, User

bearer = HTTPBearer(auto_error=False)


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    try:
        claims = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    user = db.get(User, claims["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive or unknown user.")
    return user


def require_roles(*roles: str) -> Callable:
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Role is not permitted for this operation.")
        return user

    return dependency


def current_customer(user: User = Depends(require_roles("customer")), db: Session = Depends(get_db)) -> CustomerProfile:
    profile = db.query(CustomerProfile).filter(CustomerProfile.user_id == user.id).one_or_none()
    if not profile:
        raise HTTPException(status_code=403, detail="Verified customer profile required.")
    return profile
