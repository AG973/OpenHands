"""CODEIT Knowledge CRUD routes — backend-persisted knowledge base."""

import json
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from openhands.server.codeit.database import get_db
from openhands.server.codeit.routes_auth import TokenPayload, require_auth

router = APIRouter(prefix="/api/codeit/knowledge", tags=["codeit-knowledge"])


class KnowledgeCreate(BaseModel):
    title: str
    content: str = ""
    tags: list[str] = []


class KnowledgeUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[list[str]] = None


def _row_to_dict(r) -> dict:
    tags = []
    try:
        tags = json.loads(r["tags"]) if r["tags"] else []
    except (json.JSONDecodeError, TypeError):
        tags = []
    return {
        "id": r["id"],
        "title": r["title"],
        "content": r["content"],
        "tags": tags,
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
    }


@router.get("")
async def list_knowledge(
    q: str = "", user: TokenPayload = Depends(require_auth)
) -> JSONResponse:
    with get_db() as conn:
        if q:
            like = f"%{q}%"
            rows = conn.execute(
                "SELECT id, title, content, tags, created_at, updated_at "
                "FROM knowledge WHERE user_id = ? AND (title LIKE ? OR content LIKE ? OR tags LIKE ?) "
                "ORDER BY updated_at DESC",
                (user.user_id, like, like, like),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, title, content, tags, created_at, updated_at "
                "FROM knowledge WHERE user_id = ? ORDER BY updated_at DESC",
                (user.user_id,),
            ).fetchall()
    return JSONResponse(content={"items": [_row_to_dict(r) for r in rows]})


@router.post("")
async def create_knowledge(
    body: KnowledgeCreate, user: TokenPayload = Depends(require_auth)
) -> JSONResponse:
    item_id = str(uuid.uuid4())
    tags_json = json.dumps(body.tags)
    with get_db() as conn:
        conn.execute(
            "INSERT INTO knowledge (id, user_id, title, content, tags) VALUES (?, ?, ?, ?, ?)",
            (item_id, user.user_id, body.title, body.content, tags_json),
        )
    return JSONResponse(
        status_code=201,
        content={"id": item_id, "title": body.title, "content": body.content, "tags": body.tags},
    )


@router.put("/{item_id}")
async def update_knowledge(
    item_id: str, body: KnowledgeUpdate, user: TokenPayload = Depends(require_auth)
) -> JSONResponse:
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM knowledge WHERE id = ? AND user_id = ?", (item_id, user.user_id)
        ).fetchone()
        if not existing:
            return JSONResponse(status_code=404, content={"error": "Knowledge item not found"})

        updates = []
        params = []
        if body.title is not None:
            updates.append("title = ?")
            params.append(body.title)
        if body.content is not None:
            updates.append("content = ?")
            params.append(body.content)
        if body.tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(body.tags))
        if updates:
            updates.append("updated_at = datetime('now')")
            params.append(item_id)
            params.append(user.user_id)
            conn.execute(
                f"UPDATE knowledge SET {', '.join(updates)} WHERE id = ? AND user_id = ?",
                params,
            )

        row = conn.execute(
            "SELECT id, title, content, tags, created_at, updated_at FROM knowledge WHERE id = ?",
            (item_id,),
        ).fetchone()
    return JSONResponse(content=_row_to_dict(row))


@router.delete("/{item_id}")
async def delete_knowledge(
    item_id: str, user: TokenPayload = Depends(require_auth)
) -> JSONResponse:
    with get_db() as conn:
        deleted = conn.execute(
            "DELETE FROM knowledge WHERE id = ? AND user_id = ?", (item_id, user.user_id)
        ).rowcount
    if not deleted:
        return JSONResponse(status_code=404, content={"error": "Knowledge item not found"})
    return JSONResponse(content={"deleted": True})
