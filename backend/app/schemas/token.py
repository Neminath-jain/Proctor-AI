from typing import Optional
from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="JWT refresh token to exchange for a new access token")


class TokenPayload(BaseModel):
    sub: str = Field(..., description="Subject identifier (User UUID)")
    email: Optional[str] = Field(default=None, description="User email address")
    role: Optional[str] = Field(default=None, description="User role")
    type: str = Field(..., description="Token type: 'access' or 'refresh'")
    exp: Optional[int] = Field(default=None, description="Expiration UNIX timestamp")
