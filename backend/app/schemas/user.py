from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
import re

from app.models.user import UserRole


class UserBase(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    name: str = Field(..., min_length=1, max_length=100, description="Full name of user")
    role: UserRole = Field(default=UserRole.CANDIDATE, description="User role: candidate, admin, or grader")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Name cannot be empty or only whitespace")
        return trimmed


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128, description="Plain text password")

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Password must contain at least one alphabetic letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one numeric digit")
        return v


class UserLogin(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, max_length=128, description="Plain text password")


class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("Name cannot be empty or only whitespace")
            return trimmed
        return v


class UserChangePassword(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128, description="Current account password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Password must contain at least one alphabetic letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one numeric digit")
        return v



class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_active: bool
    created_at: datetime
