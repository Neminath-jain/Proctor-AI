import uuid
from typing import AsyncGenerator, List, Union
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import decode_token
from app.models.user import User, UserRole

# Reusable HTTP Bearer token extractor
security = HTTPBearer(auto_error=True)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an asynchronous database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency to extract and validate the authenticated user from JWT Bearer token."""
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
        token_type = payload.get("type")
        if token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type: expected access token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception

        user_id = uuid.UUID(user_id_str)
    except (jwt.PyJWTError, ValueError):
        raise credentials_exception

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account",
        )

    return user


def require_roles(*roles: Union[UserRole, str]):
    """Role-Based Access Control (RBAC) dependency factory.
    
    Usage:
        @router.get("/admin/exams", dependencies=[Depends(require_roles(UserRole.ADMIN))])
    """
    allowed_roles = [r.value if isinstance(r, UserRole) else str(r) for r in roles]

    def role_verifier(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Requires one of the following roles: {allowed_roles}",
            )
        return current_user

    return role_verifier


get_current_admin = require_roles(UserRole.ADMIN)
