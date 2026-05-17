"""Authentication middleware — minimal token-based auth."""

import os
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
ALGORITHM = "HS256"
security = HTTPBearer(auto_error=False)


def create_access_token(user_email: str) -> str:
    return jwt.encode({"sub": user_email}, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = None,
) -> str:
    """FastAPI dependency — extracts user from Bearer token.

    In development (no token), returns a default user.
    In production, requires valid JWT.
    """
    # Dev mode: allow unauthenticated access
    env = os.environ.get("ENVIRONMENT", "development")
    if env == "development":
        return "dev@example.com"

    if credentials is None:
        raise HTTPException(401, "Missing authorization header")

    email = verify_token(credentials.credentials)
    if email is None:
        raise HTTPException(401, "Invalid or expired token")
    return email
