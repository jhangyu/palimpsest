# backend/core/security_models.py
"""
---
name: security_models
description: "Pydantic request/response models for auth, user profile, and admin endpoints (21 models total)"
type: core
target:
  layer: backend
  domain: auth
spec_doc: null
test_file: tests/stage1/test_auth.py
functions:
  - name: LoginRequest
    line: 9
    purpose: "Request model: email + password login"
  - name: RegisterRequest
    line: 13
    purpose: "Request model: new user registration"
  - name: ForgotPasswordRequest
    line: 25
    purpose: "Request model: initiate password reset by email"
  - name: ResetPasswordRequest
    line: 28
    purpose: "Request model: complete password reset with token"
  - name: VerifyEmailRequest
    line: 32
    purpose: "Request model: verify email with token"
  - name: UpdateProfileRequest
    line: 41
    purpose: "Request model: update full_name"
  - name: UpdateEmailRequest
    line: 44
    purpose: "Request model: change email (requires current password)"
  - name: ChangePasswordRequest
    line: 51
    purpose: "Request model: change password with current + new"
  - name: UserResponse
    line: 61
    purpose: "Response model: public user fields for admin list views"
  - name: UserMeResponse
    line: 75
    purpose: "Response model: full user profile including preferences and pending_email"
  - name: AdminCreateUserRequest
    line: 94
    purpose: "Request model: admin creates new user with roles"
  - name: AdminUserListResponse
    line: 104
    purpose: "Response model: paginated user list for admin"
  # Total: 21 Pydantic models; main API models listed above
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
"""

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
