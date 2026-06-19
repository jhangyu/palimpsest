"""AI Provider management endpoints.

Extracted from backend/main.py — all endpoint logic is a verbatim copy.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core.ai_providers import (
    list_user_providers,
    create_provider,
    update_provider,
    delete_provider,
    reorder_providers,
    discover_models,
    test_provider_connection,
    reveal_api_key,
    toggle_provider_enabled,
    get_runtime_status,
    ProviderNotFoundError,
    ProviderRevisionConflictError,
    ProviderLabelConflictError,
    ProviderOwnershipError,
)
from core.auth import verify_password, check_rate_limit, record_attempt
from core.db import get_db, ai_tables, auth_rate_limits

from routers._deps import require_user, require_kek, _csrf_dependency

router = APIRouter(prefix="/settings/ai-providers", tags=["ai-providers"])

# --- AI Provider Request Models ---
class CreateProviderRequest(BaseModel):
    label: str
    protocol: str
    base_url: str
    model: str
    api_key: str
    temperature: float | None = None
    max_tokens: int = 4096
    thinking: bool = False
    effort: str = "low"

class UpdateProviderRequest(BaseModel):
    revision: int
    label: str | None = None
    protocol: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    thinking: bool | None = None
    effort: str | None = None

class DeleteProviderRequest(BaseModel):
    revision: int

class ReorderProvidersRequest(BaseModel):
    ordered_ids: list[int]
    revision: int

class ToggleProviderEnabledRequest(BaseModel):
    enabled: bool

class DiscoverModelsRequest(BaseModel):
    protocol: str
    base_url: str
    api_key: str | None = None
    provider_id: int | None = None

class RevealProviderKeyRequest(BaseModel):
    current_password: str


@router.get("")
async def list_ai_providers(request: Request, current_user: dict = Depends(require_user), db=Depends(get_db)):
    if not request.app.state.llm_profiles_enabled:
        return JSONResponse({"providers": [], "profiles_enabled": False}, status_code=200)
    result = await list_user_providers(db, ai_tables, user_id=current_user["id"])
    return result

@router.get("/runtime-status")
async def get_ai_provider_runtime_status(request: Request, current_user: dict = Depends(require_user), db=Depends(get_db)):
    if not request.app.state.llm_profiles_enabled:
        return JSONResponse({"profiles_enabled": False, "kek_available": False}, status_code=200)
    result = await get_runtime_status(
        db, ai_tables, request.app.state.kek_backend,
        user_id=current_user["id"],
    )
    return result

@router.post("/actions/discover-models", dependencies=[Depends(_csrf_dependency)])
async def discover_ai_models(req: DiscoverModelsRequest, current_user: dict = Depends(require_user), db=Depends(get_db), kek=Depends(require_kek)):
    try:
        result = await discover_models(
            db, ai_tables, kek,
            user_id=current_user["id"],
            protocol=req.protocol,
            base_url=req.base_url,
            api_key=req.api_key,
            provider_id=req.provider_id,
        )
        return result
    except ProviderNotFoundError:
        raise HTTPException(status_code=404, detail="Provider not found")
    except ProviderOwnershipError:
        raise HTTPException(status_code=403, detail="Access denied")

@router.put("/order", dependencies=[Depends(_csrf_dependency)])
async def reorder_ai_providers(req: ReorderProvidersRequest, current_user: dict = Depends(require_user), db=Depends(get_db)):
    try:
        result = await reorder_providers(
            db, ai_tables,
            user_id=current_user["id"],
            ordered_ids=req.ordered_ids,
            revision=req.revision,
        )
        return result
    except ProviderRevisionConflictError:
        raise HTTPException(status_code=409, detail={"code": "revision_conflict", "message": "Provider settings changed; reload and retry."})
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": "invalid_order", "message": str(e)})

@router.post("", dependencies=[Depends(_csrf_dependency)])
async def create_ai_provider(req: CreateProviderRequest, current_user: dict = Depends(require_user), db=Depends(get_db), kek=Depends(require_kek)):
    try:
        result = await create_provider(
            db, ai_tables, kek,
            user_id=current_user["id"],
            label=req.label,
            protocol=req.protocol,
            base_url=req.base_url,
            model=req.model,
            api_key=req.api_key,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            thinking=req.thinking,
            effort=req.effort,
        )
        return Response(
            content=json.dumps(result, default=str),
            status_code=201,
            media_type="application/json",
        )
    except ProviderLabelConflictError:
        raise HTTPException(status_code=409, detail={"code": "label_conflict", "message": "A provider with this label already exists."})

@router.put("/{provider_id}", dependencies=[Depends(_csrf_dependency)])
async def update_ai_provider(provider_id: int, req: UpdateProviderRequest, current_user: dict = Depends(require_user), db=Depends(get_db), kek=Depends(require_kek)):
    kwargs = {}
    for field in ("label", "protocol", "base_url", "model", "temperature", "max_tokens", "thinking", "effort"):
        if field in req.model_fields_set:
            kwargs[field] = getattr(req, field)
    if "api_key" in req.model_fields_set and req.api_key is not None:
        kwargs["api_key"] = req.api_key
    try:
        result = await update_provider(
            db, ai_tables, kek,
            user_id=current_user["id"],
            provider_id=provider_id,
            revision=req.revision,
            **kwargs,
        )
        return result
    except ProviderNotFoundError:
        raise HTTPException(status_code=404, detail="Provider not found")
    except ProviderRevisionConflictError:
        raise HTTPException(status_code=409, detail={"code": "revision_conflict", "message": "Provider settings changed; reload and retry."})
    except ProviderOwnershipError:
        raise HTTPException(status_code=403, detail="Access denied")

@router.delete("/{provider_id}", dependencies=[Depends(_csrf_dependency)])
async def delete_ai_provider(provider_id: int, req: DeleteProviderRequest, current_user: dict = Depends(require_user), db=Depends(get_db)):
    try:
        await delete_provider(
            db, ai_tables,
            user_id=current_user["id"],
            provider_id=provider_id,
            revision=req.revision,
        )
        return Response(status_code=204)
    except ProviderNotFoundError:
        raise HTTPException(status_code=404, detail="Provider not found")
    except ProviderRevisionConflictError:
        raise HTTPException(status_code=409, detail={"code": "revision_conflict", "message": "Provider settings changed; reload and retry."})
    except ProviderOwnershipError:
        raise HTTPException(status_code=403, detail="Access denied")

@router.post("/{provider_id}/test", dependencies=[Depends(_csrf_dependency)])
async def test_ai_provider(provider_id: int, current_user: dict = Depends(require_user), db=Depends(get_db), kek=Depends(require_kek)):
    try:
        result = await test_provider_connection(
            db, ai_tables, kek,
            user_id=current_user["id"],
            provider_id=provider_id,
        )
        return result
    except ProviderNotFoundError:
        raise HTTPException(status_code=404, detail="Provider not found")
    except ProviderOwnershipError:
        raise HTTPException(status_code=403, detail="Access denied")

@router.post("/{provider_id}/reveal", dependencies=[Depends(_csrf_dependency)])
async def reveal_ai_provider_key(provider_id: int, req: RevealProviderKeyRequest, current_user: dict = Depends(require_user), db=Depends(get_db), kek=Depends(require_kek)):
    # Rate limit check
    rate_key = f"reveal_provider:{current_user['id']}"
    allowed, retry_after = await check_rate_limit(db, auth_rate_limits, "reveal_provider", rate_key)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Too many reveal attempts. Try again in {retry_after} seconds.")
    if not await verify_password(req.current_password, current_user["password_hash"]):
        await record_attempt(db, auth_rate_limits, "reveal_provider", rate_key)
        raise HTTPException(status_code=403, detail={"code": "invalid_password", "message": "Invalid password."})
    try:
        api_key = await reveal_api_key(
            db, ai_tables, kek,
            user_id=current_user["id"],
            provider_id=provider_id,
        )
        return Response(
            content=json.dumps({"api_key": api_key}),
            status_code=200,
            media_type="application/json",
            headers={"Cache-Control": "no-store, private", "Pragma": "no-cache"},
        )
    except ProviderNotFoundError:
        raise HTTPException(status_code=404, detail="Provider not found")
    except ProviderOwnershipError:
        raise HTTPException(status_code=403, detail="Access denied")

@router.put("/{provider_id}/enabled", dependencies=[Depends(_csrf_dependency)])
async def toggle_ai_provider_enabled(provider_id: int, req: ToggleProviderEnabledRequest, current_user: dict = Depends(require_user), db=Depends(get_db)):
    try:
        result = await toggle_provider_enabled(
            db, ai_tables,
            user_id=current_user["id"],
            provider_id=provider_id,
            enabled=req.enabled,
        )
        return result
    except ProviderNotFoundError:
        raise HTTPException(status_code=404, detail="Provider not found")
    except ProviderOwnershipError:
        raise HTTPException(status_code=403, detail="Access denied")
