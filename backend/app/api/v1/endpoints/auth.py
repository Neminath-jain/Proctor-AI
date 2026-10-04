import uuid
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user, get_db, require_roles
from app.core.rate_limit import (
    check_login_backoff,
    check_rate_limit,
    clear_login_failures,
    get_client_ip,
    record_login_failure,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User, UserRole
from app.schemas.token import RefreshTokenRequest, Token
from app.schemas.user import UserChangePassword, UserCreate, UserLogin, UserResponse, UserUpdate

router = APIRouter(prefix="/auth", tags=["Authentication & RBAC"])


@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def signup(
    user_in: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Create a new user with email, password, and designated role."""
    client_ip = get_client_ip(request)
    check_rate_limit(
        key=client_ip,
        action="auth_signup_ip",
        max_requests=settings.RATE_LIMIT_SIGNUP_PER_IP_MAX,
        window_seconds=settings.RATE_LIMIT_SIGNUP_PER_IP_WINDOW_SECONDS,
        error_message="Too many account registrations from this network. Please wait before retrying.",
    )

    # Verify email is not already taken
    stmt = select(User).where(User.email == user_in.email)
    existing_user = (await db.execute(stmt)).scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )

    # Hash password and persist user
    new_user = User(
        email=user_in.email,
        name=user_in.name,
        role=user_in.role.value if isinstance(user_in.role, UserRole) else str(user_in.role),
        password_hash=hash_password(user_in.password),
        is_active=True,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@router.post(
    "/login",
    response_model=Token,
    summary="Authenticate user and issue access/refresh tokens",
)
async def login(
    credentials: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Validate credentials and return JWT access and refresh token pair."""
    client_ip = get_client_ip(request)

    # 1. Enforce IP-level rate limit against credential stuffing
    check_rate_limit(
        key=client_ip,
        action="auth_login_ip",
        max_requests=settings.RATE_LIMIT_LOGIN_PER_IP_MAX,
        window_seconds=settings.RATE_LIMIT_LOGIN_PER_IP_WINDOW_SECONDS,
        error_message="Too many login attempts from this network. Please wait before retrying.",
    )

    # 2. Enforce per-account exponential backoff on repeated failures
    check_login_backoff(credentials.email)

    stmt = select(User).where(User.email == credentials.email)
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.password_hash):
        # Record failed attempt to trigger exponential backoff after threshold
        record_login_failure(credentials.email, client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is deactivated.",
        )

    # Clear failure counters on successful login so legitimate candidate is not delayed
    clear_login_failures(credentials.email, client_ip)

    access_token = create_access_token(
        subject=user.id,
        email=user.email,
        role=user.role,
    )
    refresh_token = create_refresh_token(
        subject=user.id,
    )

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post(
    "/refresh",
    response_model=Token,
    summary="Refresh access token using valid refresh token",
)
async def refresh_token(
    refresh_in: RefreshTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Exchange a valid refresh token for a newly rotated access and refresh token pair."""
    client_ip = get_client_ip(request)
    check_rate_limit(
        key=client_ip,
        action="auth_refresh_ip",
        max_requests=settings.RATE_LIMIT_AUTH_REFRESH_PER_IP_MAX,
        window_seconds=settings.RATE_LIMIT_AUTH_REFRESH_WINDOW_SECONDS,
        error_message="Too many token refresh requests. Please wait before retrying.",
    )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(refresh_in.refresh_token)
        if payload.get("type") != "refresh":
            raise credentials_exception
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise credentials_exception
        user_id = uuid.UUID(user_id_str)
    except (jwt.PyJWTError, ValueError):
        raise credentials_exception

    stmt = select(User).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user or not user.is_active:
        raise credentials_exception

    new_access_token = create_access_token(
        subject=user.id,
        email=user.email,
        role=user.role,
    )
    new_refresh_token = create_refresh_token(
        subject=user.id,
    )

    return Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Retrieve profile of the currently authenticated user",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> User:
    """Return the profile and role details of the bearer token owner."""
    return current_user


@router.put(
    "/me",
    response_model=UserResponse,
    summary="Update current user profile (e.g. name)",
)
async def update_me(
    user_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Update profile details for the authenticated user."""
    if user_in.name is not None:
        current_user.name = user_in.name
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.post(
    "/change-password",
    summary="Change user password after verifying current password",
)
async def change_password(
    payload: UserChangePassword,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Verify current password and update to new password adhering to strength rules."""
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password.",
        )

    current_user.password_hash = hash_password(payload.new_password)
    db.add(current_user)
    await db.commit()
    return {"message": "Password updated successfully."}



# RBAC Verification Endpoints
@router.get(
    "/admin-only",
    summary="RBAC Test: Admin / Invigilator only route",
)
async def admin_only_endpoint(
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Restricted to admin users only."""
    return {
        "message": "Access granted to admin area.",
        "user_id": str(current_user.id),
        "role": current_user.role,
    }


@router.get(
    "/grader-only",
    summary="RBAC Test: Grader and Admin route",
)
async def grader_only_endpoint(
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.GRADER)),
):
    """Restricted to graders and admins."""
    return {
        "message": "Access granted to grading area.",
        "user_id": str(current_user.id),
        "role": current_user.role,
    }
