import hashlib
import hmac
import secrets
import time
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from .config import Settings

security = HTTPBasic(auto_error=False)
settings = Settings()


def _sign_session(username: str) -> str:
    ts = str(int(time.time()))
    payload = f"{username}:{ts}"
    sig = hmac.new(settings.resolved_session_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def _verify_session(token: str, max_age: int = 7 * 24 * 3600) -> Optional[str]:
    parts = token.split(":")
    if len(parts) != 3:
        return None
    username, ts_str, sig = parts
    payload = f"{username}:{ts_str}"
    expected = hmac.new(settings.resolved_session_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    try:
        ts = int(ts_str)
    except ValueError:
        return None
    if time.time() - ts > max_age:
        return None
    return username


def verify_credentials(credentials: Optional[HTTPBasicCredentials]) -> Optional[str]:
    if not credentials:
        return None
    correct_username = secrets.compare_digest(credentials.username, settings.admin_username)
    correct_password = secrets.compare_digest(credentials.password, settings.admin_password)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def get_current_user(request: Request, credentials: Optional[HTTPBasicCredentials] = Depends(security)) -> str:
    # 1) Cookie-based session
    session_token = request.cookies.get(settings.session_cookie_name)
    if session_token:
        user = _verify_session(session_token)
        if user:
            return user
    # 2) HTTP Basic fallback
    user = verify_credentials(credentials)
    if user:
        return user
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Basic"},
    )


def make_login_response(response, username: str, remember_seconds: int = 7 * 24 * 3600):
    token = _sign_session(username)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=remember_seconds,
        httponly=True,
        samesite="lax",
    )
    return response


def make_logout_response(response):
    response.delete_cookie(settings.session_cookie_name)
    return response
