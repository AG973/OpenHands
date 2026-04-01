"""CODEIT Connectors CRUD routes — backend-persisted connector configs."""

import json
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from openhands.server.codeit.database import get_db
from openhands.server.codeit.routes_auth import TokenPayload, require_auth

router = APIRouter(prefix="/api/codeit/connectors", tags=["codeit-connectors"])


class ConnectorCreate(BaseModel):
    name: str
    type: str
    icon: str = ""
    status: str = "disconnected"
    config: dict[str, str] = {}


class ConnectorUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    config: Optional[dict[str, str]] = None


def _row_to_dict(r) -> dict:
    config = {}
    try:
        config = json.loads(r["config_json"]) if r["config_json"] else {}
    except (json.JSONDecodeError, TypeError):
        config = {}
    # Mask sensitive values in response
    masked_config = {}
    sensitive_keys = {"token", "key", "secret", "password", "ssh_key", "bot_token", "api_key", "access_key", "secret_key"}
    for k, v in config.items():
        if any(s in k.lower() for s in sensitive_keys) and v:
            masked_config[k] = "***" + v[-4:] if len(v) > 4 else "****"
        else:
            masked_config[k] = v
    return {
        "id": r["id"],
        "name": r["name"],
        "type": r["type"],
        "icon": r["icon"],
        "status": r["status"],
        "config": masked_config,
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
    }


@router.get("")
async def list_connectors(user: TokenPayload = Depends(require_auth)) -> JSONResponse:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, name, type, icon, status, config_json, created_at, updated_at "
            "FROM connectors WHERE user_id = ? ORDER BY created_at",
            (user.user_id,),
        ).fetchall()
    return JSONResponse(content={"items": [_row_to_dict(r) for r in rows]})


@router.post("")
async def create_connector(
    body: ConnectorCreate, user: TokenPayload = Depends(require_auth)
) -> JSONResponse:
    connector_id = str(uuid.uuid4())
    config_json = json.dumps(body.config)
    with get_db() as conn:
        conn.execute(
            "INSERT INTO connectors (id, user_id, name, type, icon, status, config_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (connector_id, user.user_id, body.name, body.type, body.icon, body.status, config_json),
        )
    return JSONResponse(status_code=201, content={
        "id": connector_id, "name": body.name, "type": body.type, "status": body.status,
    })


@router.put("/{connector_id}")
async def update_connector(
    connector_id: str, body: ConnectorUpdate, user: TokenPayload = Depends(require_auth)
) -> JSONResponse:
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id, config_json FROM connectors WHERE id = ? AND user_id = ?",
            (connector_id, user.user_id),
        ).fetchone()
        if not existing:
            return JSONResponse(status_code=404, content={"error": "Connector not found"})

        updates = []
        params = []
        if body.name is not None:
            updates.append("name = ?")
            params.append(body.name)
        if body.status is not None:
            updates.append("status = ?")
            params.append(body.status)
        if body.config is not None:
            # Merge with existing config (preserve values not sent)
            try:
                old_config = json.loads(existing["config_json"]) if existing["config_json"] else {}
            except (json.JSONDecodeError, TypeError):
                old_config = {}
            # Filter out masked values (e.g. "***1234") to prevent overwriting real secrets
            clean_config = {
                k: v for k, v in body.config.items()
                if not (isinstance(v, str) and v.startswith("***"))
            }
            merged = {**old_config, **clean_config}
            updates.append("config_json = ?")
            params.append(json.dumps(merged))
        if updates:
            updates.append("updated_at = datetime('now')")
            params.append(connector_id)
            params.append(user.user_id)
            conn.execute(
                f"UPDATE connectors SET {', '.join(updates)} WHERE id = ? AND user_id = ?",
                params,
            )

        row = conn.execute(
            "SELECT id, name, type, icon, status, config_json, created_at, updated_at "
            "FROM connectors WHERE id = ?",
            (connector_id,),
        ).fetchone()
    return JSONResponse(content=_row_to_dict(row))


@router.post("/{connector_id}/disconnect")
async def disconnect_connector(
    connector_id: str, user: TokenPayload = Depends(require_auth)
) -> JSONResponse:
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM connectors WHERE id = ? AND user_id = ?",
            (connector_id, user.user_id),
        ).fetchone()
        if not existing:
            return JSONResponse(status_code=404, content={"error": "Connector not found"})
        # Clear config and set status to disconnected
        conn.execute(
            "UPDATE connectors SET status = 'disconnected', config_json = '{}', updated_at = datetime('now') WHERE id = ?",
            (connector_id,),
        )
    return JSONResponse(content={"disconnected": True})


@router.delete("/{connector_id}")
async def delete_connector(
    connector_id: str, user: TokenPayload = Depends(require_auth)
) -> JSONResponse:
    with get_db() as conn:
        deleted = conn.execute(
            "DELETE FROM connectors WHERE id = ? AND user_id = ?", (connector_id, user.user_id)
        ).rowcount
    if not deleted:
        return JSONResponse(status_code=404, content={"error": "Connector not found"})
    return JSONResponse(content={"deleted": True})
