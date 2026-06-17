# backend/core/security_models.py
"""Pydantic request/response models for auth, user, and admin endpoints."""

from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, Any
import re


# --- Auth ---

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str
    full_name: Optional[str] = None

class FirstRunSetupRequest(BaseModel):
    email: str
    username: str
    password: str
    full_name: Optional[str] = None

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class VerifyEmailRequest(BaseModel):
    token: str

class ResendVerificationRequest(BaseModel):
    email: str


# --- Current User ---

class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None

class UpdateEmailRequest(BaseModel):
    new_email: str
    password: str  # require current password for email change

class UpdateUsernameRequest(BaseModel):
    new_username: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class UpdatePreferencesRequest(BaseModel):
    preferences: dict


# --- User Responses ---

class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: Optional[str] = None
    status: str
    email_verified_at: Optional[str] = None
    avatar_source: str = "none"
    avatar_hash: Optional[str] = None
    created_at: str
    updated_at: str
    last_login_at: Optional[str] = None
    roles: list[str] = []

class UserMeResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: Optional[str] = None
    status: str
    email_verified_at: Optional[str] = None
    pending_email: Optional[str] = None
    avatar_source: str = "none"
    avatar_hash: Optional[str] = None
    preferences: dict = {}
    created_at: str
    updated_at: str
    last_login_at: Optional[str] = None
    roles: list[str] = []


# --- Admin ---

class AdminCreateUserRequest(BaseModel):
    email: str
    username: str
    full_name: Optional[str] = None
    roles: list[str] = ["user"]

class AdminUpdateUserRequest(BaseModel):
    full_name: Optional[str] = None
    status: Optional[str] = None  # active / inactive / blocked

class AdminUserListResponse(BaseModel):
    users: list[UserResponse]
    total: int
    page: int
    page_size: int

class AdminUpdateRolesRequest(BaseModel):
    roles: list[str]


# --- AI Tokens (used by A2 in Phase 4, defined here for shared model) ---

class CreateTokenRequest(BaseModel):
    provider: str
    label: str
    token: str  # plaintext token value
    current_password: str

class UpdateTokenRequest(BaseModel):
    token: str  # plaintext token value
    current_password: str

class RevealTokenRequest(BaseModel):
    current_password: str

class TestTokenRequest(BaseModel):
    current_password: str

class TokenResponse(BaseModel):
    id: int
    provider: str
    label: str
    token_mask: Optional[str] = None
    token_last4: Optional[str] = None
    needs_reentry: bool = False
    is_default: bool = False
    created_at: str
    updated_at: str
    last_used_at: Optional[str] = None
