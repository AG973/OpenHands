"""CODEIT Skills CRUD routes — backend-persisted skills."""

import json
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from openhands.server.codeit.database import get_db
from openhands.server.codeit.routes_auth import TokenPayload, require_auth

router = APIRouter(prefix="/api/codeit/skills", tags=["codeit-skills"])


class SkillCreate(BaseModel):
    name: str
    description: str = ""
    content: str = ""
    enabled: bool = True


class SkillUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    enabled: Optional[bool] = None


@router.get("")
async def list_skills(user: TokenPayload = Depends(require_auth)) -> JSONResponse:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, name, description, content, enabled, created_at, updated_at "
            "FROM skills WHERE user_id = ? ORDER BY created_at DESC",
            (user.user_id,),
        ).fetchall()
    items = [
        {
            "id": r["id"],
            "name": r["name"],
            "description": r["description"],
            "content": r["content"],
            "enabled": bool(r["enabled"]),
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]
    return JSONResponse(content={"items": items})


@router.post("")
async def create_skill(
    body: SkillCreate, user: TokenPayload = Depends(require_auth)
) -> JSONResponse:
    skill_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            "INSERT INTO skills (id, user_id, name, description, content, enabled) VALUES (?, ?, ?, ?, ?, ?)",
            (skill_id, user.user_id, body.name, body.description, body.content, int(body.enabled)),
        )
    return JSONResponse(
        status_code=201,
        content={"id": skill_id, "name": body.name, "description": body.description, "content": body.content, "enabled": body.enabled},
    )


@router.put("/{skill_id}")
async def update_skill(
    skill_id: str, body: SkillUpdate, user: TokenPayload = Depends(require_auth)
) -> JSONResponse:
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM skills WHERE id = ? AND user_id = ?", (skill_id, user.user_id)
        ).fetchone()
        if not existing:
            return JSONResponse(status_code=404, content={"error": "Skill not found"})

        updates = []
        params = []
        if body.name is not None:
            updates.append("name = ?")
            params.append(body.name)
        if body.description is not None:
            updates.append("description = ?")
            params.append(body.description)
        if body.content is not None:
            updates.append("content = ?")
            params.append(body.content)
        if body.enabled is not None:
            updates.append("enabled = ?")
            params.append(int(body.enabled))
        if updates:
            updates.append("updated_at = datetime('now')")
            params.append(skill_id)
            params.append(user.user_id)
            conn.execute(
                f"UPDATE skills SET {', '.join(updates)} WHERE id = ? AND user_id = ?",
                params,
            )

        row = conn.execute(
            "SELECT id, name, description, content, enabled, updated_at FROM skills WHERE id = ?",
            (skill_id,),
        ).fetchone()
    return JSONResponse(content={
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "content": row["content"],
        "enabled": bool(row["enabled"]),
        "updated_at": row["updated_at"],
    })


@router.delete("/{skill_id}")
async def delete_skill(
    skill_id: str, user: TokenPayload = Depends(require_auth)
) -> JSONResponse:
    with get_db() as conn:
        deleted = conn.execute(
            "DELETE FROM skills WHERE id = ? AND user_id = ?", (skill_id, user.user_id)
        ).rowcount
    if not deleted:
        return JSONResponse(status_code=404, content={"error": "Skill not found"})
    return JSONResponse(content={"deleted": True})
