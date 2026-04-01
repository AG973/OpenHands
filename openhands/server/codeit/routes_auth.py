"""CODEIT auth routes — login, register, token validation."""

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from openhands.core.logger import openhands_logger as logger
from openhands.server.codeit.auth import (
    authenticate_user,
    create_token,
    get_or_create_default_user,
    hash_password,
    verify_token,
)
from openhands.server.codeit.database import get_db

router = APIRouter(prefix="/api/codeit/auth", tags=["codeit-auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str = ""


class TokenPayload(BaseModel):
    user_id: int
    username: str


def get_current_user(authorization: Optional[str] = Header(None)) -> Optional[TokenPayload]:
    """Extract and validate user from Authorization header. Returns None if invalid."""
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
    payload = verify_token(token)
    if not payload:
        return None
    return TokenPayload(user_id=payload["sub"], username=payload["username"])


def require_auth(authorization: Optional[str] = Header(None)) -> TokenPayload:
    """Dependency that requires valid auth. Returns 401 if missing/invalid."""
    user = get_current_user(authorization)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


@router.post("/login")
async def login(req: LoginRequest) -> JSONResponse:
    result = authenticate_user(req.username, req.password)
    if not result:
        return JSONResponse(status_code=401, content={"error": "Invalid username or password"})
    user_id, username = result
    token = create_token(user_id, username)
    return JSONResponse(content={"token": token, "user_id": user_id, "username": username})


@router.post("/register")
async def register(req: RegisterRequest) -> JSONResponse:
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM users WHERE username = ?", (req.username,)).fetchone()
        if existing:
            return JSONResponse(status_code=409, content={"error": "Username already exists"})
        pw_hash = hash_password(req.password)
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, display_name, role) VALUES (?, ?, ?, ?)",
            (req.username, pw_hash, req.display_name or req.username, "user"),
        )
        user_id = cursor.lastrowid
    token = create_token(user_id, req.username)
    logger.info(f"CODEIT: Registered user '{req.username}' (id={user_id})")
    return JSONResponse(status_code=201, content={"token": token, "user_id": user_id, "username": req.username})


@router.get("/me")
async def get_me(user: TokenPayload = Depends(require_auth)) -> JSONResponse:
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, username, display_name, role, created_at FROM users WHERE id = ?",
            (user.user_id,),
        ).fetchone()
        if not row:
            return JSONResponse(status_code=404, content={"error": "User not found"})
    return JSONResponse(content={
        "user_id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "role": row["role"],
        "created_at": row["created_at"],
    })


@router.post("/validate")
async def validate_token_endpoint(authorization: Optional[str] = Header(None)) -> JSONResponse:
    user = get_current_user(authorization)
    if not user:
        return JSONResponse(status_code=401, content={"valid": False})
    return JSONResponse(content={"valid": True, "user_id": user.user_id, "username": user.username})
