# backend/core/security_models.py
"""Pydantic request/response models for auth, user, and admin endpoints."""

from pydantic import BaseModel


# --- Auth ---

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str
    full_name: str | None = None

class FirstRunSetupRequest(BaseModel):
    email: str
    username: str
    password: str
    full_name: str | None = None

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
    full_name: str | None = None

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
    full_name: str | None = None
    status: str
    email_verified_at: str | None = None
    avatar_source: str = "none"
    avatar_hash: str | None = None
    created_at: str
    updated_at: str
    last_login_at: str | None = None
    roles: list[str] = []

class UserMeResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: str | None = None
    status: str
    email_verified_at: str | None = None
    pending_email: str | None = None
    avatar_source: str = "none"
    avatar_hash: str | None = None
    preferences: dict = {}
    created_at: str
    updated_at: str
    last_login_at: str | None = None
    roles: list[str] = []


# --- Admin ---

class AdminCreateUserRequest(BaseModel):
    email: str
    username: str
    full_name: str | None = None
    roles: list[str] = ["user"]

class AdminUpdateUserRequest(BaseModel):
    full_name: str | None = None
    status: str | None = None  # active / inactive / blocked

class AdminUserListResponse(BaseModel):
    users: list[UserResponse]
    total: int
    page: int
    page_size: int

class AdminUpdateRolesRequest(BaseModel):
    roles: list[str]


# --- AI Provider migration ---
# TODO: Remove after migration to unified AI provider backend is complete.

class LegacyProviderMigrationRequest(BaseModel):
    token_id: int
    current_password: str


class LegacyProviderMigrationItemResponse(BaseModel):
    token_id: int
    status: str
    provider_id: int | None = None


class LegacyProviderMigrationResponse(BaseModel):
    items: list[LegacyProviderMigrationItemResponse]
