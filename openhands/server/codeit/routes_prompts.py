"""CODEIT Prompts CRUD routes — backend-persisted custom system prompts."""

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from openhands.server.codeit.database import get_db
from openhands.server.codeit.routes_auth import TokenPayload, require_auth

router = APIRouter(prefix="/api/codeit/prompts", tags=["codeit-prompts"])


class PromptCreate(BaseModel):
    name: str
    content: str = ""
    active: bool = False


class PromptUpdate(BaseModel):
    name: Optional[str] = None
    content: Optional[str] = None
    active: Optional[bool] = None


@router.get("")
async def list_prompts(user: TokenPayload = Depends(require_auth)) -> JSONResponse:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, name, content, active, created_at, updated_at "
            "FROM prompts WHERE user_id = ? ORDER BY created_at DESC",
            (user.user_id,),
        ).fetchall()
    items = [
        {
            "id": r["id"],
            "name": r["name"],
            "content": r["content"],
            "active": bool(r["active"]),
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]
    return JSONResponse(content={"items": items})


@router.post("")
async def create_prompt(
    body: PromptCreate, user: TokenPayload = Depends(require_auth)
) -> JSONResponse:
    prompt_id = str(uuid.uuid4())
    with get_db() as conn:
        # If setting as active, deactivate all others first
        if body.active:
            conn.execute(
                "UPDATE prompts SET active = 0 WHERE user_id = ?", (user.user_id,)
            )
        conn.execute(
            "INSERT INTO prompts (id, user_id, name, content, active) VALUES (?, ?, ?, ?, ?)",
            (prompt_id, user.user_id, body.name, body.content, int(body.active)),
        )
    return JSONResponse(
        status_code=201,
        content={"id": prompt_id, "name": body.name, "content": body.content, "active": body.active},
    )


@router.put("/{prompt_id}")
async def update_prompt(
    prompt_id: str, body: PromptUpdate, user: TokenPayload = Depends(require_auth)
) -> JSONResponse:
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM prompts WHERE id = ? AND user_id = ?", (prompt_id, user.user_id)
        ).fetchone()
        if not existing:
            return JSONResponse(status_code=404, content={"error": "Prompt not found"})

        # If setting as active, deactivate all others first
        if body.active is True:
            conn.execute(
                "UPDATE prompts SET active = 0 WHERE user_id = ?", (user.user_id,)
            )

        updates = []
        params = []
        if body.name is not None:
            updates.append("name = ?")
            params.append(body.name)
        if body.content is not None:
            updates.append("content = ?")
            params.append(body.content)
        if body.active is not None:
            updates.append("active = ?")
            params.append(int(body.active))
        if updates:
            updates.append("updated_at = datetime('now')")
            params.append(prompt_id)
            params.append(user.user_id)
            conn.execute(
                f"UPDATE prompts SET {', '.join(updates)} WHERE id = ? AND user_id = ?",
                params,
            )

        row = conn.execute(
            "SELECT id, name, content, active, updated_at FROM prompts WHERE id = ?",
            (prompt_id,),
        ).fetchone()
    return JSONResponse(content={
        "id": row["id"],
        "name": row["name"],
        "content": row["content"],
        "active": bool(row["active"]),
        "updated_at": row["updated_at"],
    })


@router.post("/{prompt_id}/activate")
async def activate_prompt(
    prompt_id: str, user: TokenPayload = Depends(require_auth)
) -> JSONResponse:
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM prompts WHERE id = ? AND user_id = ?", (prompt_id, user.user_id)
        ).fetchone()
        if not existing:
            return JSONResponse(status_code=404, content={"error": "Prompt not found"})
        conn.execute("UPDATE prompts SET active = 0 WHERE user_id = ?", (user.user_id,))
        conn.execute(
            "UPDATE prompts SET active = 1, updated_at = datetime('now') WHERE id = ?",
            (prompt_id,),
        )
    return JSONResponse(content={"activated": True})


@router.delete("/{prompt_id}")
async def delete_prompt(
    prompt_id: str, user: TokenPayload = Depends(require_auth)
) -> JSONResponse:
    with get_db() as conn:
        deleted = conn.execute(
            "DELETE FROM prompts WHERE id = ? AND user_id = ?", (prompt_id, user.user_id)
        ).rowcount
    if not deleted:
        return JSONResponse(status_code=404, content={"error": "Prompt not found"})
    return JSONResponse(content={"deleted": True})
