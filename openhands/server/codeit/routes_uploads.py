"""CODEIT File Upload routes — real server-side file storage."""

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse

from openhands.core.logger import openhands_logger as logger
from openhands.server.codeit.database import get_db
from openhands.server.codeit.routes_auth import TokenPayload, require_auth

router = APIRouter(prefix="/api/codeit/uploads", tags=["codeit-uploads"])

# Upload directory — configurable, defaults to ~/.codeit/uploads
_UPLOAD_DIR = os.environ.get(
    "CODEIT_UPLOAD_DIR",
    os.path.join(os.environ.get("CODEIT_DATA_DIR", os.path.expanduser("~/.codeit")), "uploads"),
)

# Max file size: 50MB
MAX_FILE_SIZE = 50 * 1024 * 1024

# Allowed extensions (security)
ALLOWED_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".json", ".yaml", ".yml",
    ".md", ".txt", ".csv", ".xml", ".sql", ".sh", ".bash", ".zsh",
    ".java", ".go", ".rs", ".cpp", ".c", ".h", ".rb", ".php", ".swift", ".kt",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".zip", ".tar", ".gz", ".tgz",
    ".toml", ".ini", ".cfg", ".env",
    ".dockerfile", ".dockerignore", ".gitignore",
}


def _is_safe_filename(filename: str) -> bool:
    """Check that filename doesn't contain path traversal or dangerous chars."""
    if not filename:
        return False
    if ".." in filename or "/" in filename or "\\" in filename:
        return False
    if filename.startswith("."):
        return False
    return True


def _get_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    conversation_id: str = "",
    user: TokenPayload = Depends(require_auth),
) -> JSONResponse:
    if not file.filename:
        return JSONResponse(status_code=400, content={"error": "No filename provided"})

    if not _is_safe_filename(file.filename):
        return JSONResponse(status_code=400, content={"error": "Invalid filename"})

    ext = _get_extension(file.filename)
    if ext and ext not in ALLOWED_EXTENSIONS:
        return JSONResponse(status_code=400, content={"error": f"File type '{ext}' not allowed"})

    # Read file content
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        return JSONResponse(status_code=400, content={"error": f"File too large (max {MAX_FILE_SIZE // 1024 // 1024}MB)"})

    # Store file on disk
    file_id = str(uuid.uuid4())
    safe_name = f"{file_id}{ext}"
    upload_dir = Path(_UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_path = upload_dir / safe_name

    with open(stored_path, "wb") as f:
        f.write(content)

    # Record in database
    mime_type = file.content_type or ""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO file_uploads (id, user_id, original_name, stored_path, mime_type, size_bytes, conversation_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (file_id, user.user_id, file.filename, str(stored_path), mime_type, len(content), conversation_id),
        )

    logger.info(f"CODEIT: File uploaded: {file.filename} ({len(content)} bytes) -> {stored_path}")
    return JSONResponse(status_code=201, content={
        "id": file_id,
        "original_name": file.filename,
        "size_bytes": len(content),
        "mime_type": mime_type,
        "url": f"/api/codeit/uploads/{file_id}",
    })


@router.get("")
async def list_uploads(
    conversation_id: str = "",
    user: TokenPayload = Depends(require_auth),
) -> JSONResponse:
    with get_db() as conn:
        if conversation_id:
            rows = conn.execute(
                "SELECT id, original_name, mime_type, size_bytes, conversation_id, created_at "
                "FROM file_uploads WHERE user_id = ? AND conversation_id = ? ORDER BY created_at DESC",
                (user.user_id, conversation_id),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, original_name, mime_type, size_bytes, conversation_id, created_at "
                "FROM file_uploads WHERE user_id = ? ORDER BY created_at DESC LIMIT 100",
                (user.user_id,),
            ).fetchall()
    items = [
        {
            "id": r["id"],
            "original_name": r["original_name"],
            "mime_type": r["mime_type"],
            "size_bytes": r["size_bytes"],
            "conversation_id": r["conversation_id"],
            "url": f"/api/codeit/uploads/{r['id']}",
            "created_at": r["created_at"],
        }
        for r in rows
    ]
    return JSONResponse(content={"items": items})


@router.get("/{file_id}")
async def get_upload(
    file_id: str,
    user: TokenPayload = Depends(require_auth),
) -> JSONResponse:
    from fastapi.responses import FileResponse

    with get_db() as conn:
        row = conn.execute(
            "SELECT stored_path, original_name, mime_type FROM file_uploads WHERE id = ? AND user_id = ?",
            (file_id, user.user_id),
        ).fetchone()
    if not row:
        return JSONResponse(status_code=404, content={"error": "File not found"})

    stored_path = row["stored_path"]
    if not os.path.exists(stored_path):
        return JSONResponse(status_code=404, content={"error": "File missing from disk"})

    return FileResponse(
        path=stored_path,
        filename=row["original_name"],
        media_type=row["mime_type"] or "application/octet-stream",
    )


@router.delete("/{file_id}")
async def delete_upload(
    file_id: str,
    user: TokenPayload = Depends(require_auth),
) -> JSONResponse:
    with get_db() as conn:
        row = conn.execute(
            "SELECT stored_path FROM file_uploads WHERE id = ? AND user_id = ?",
            (file_id, user.user_id),
        ).fetchone()
        if not row:
            return JSONResponse(status_code=404, content={"error": "File not found"})

        # Delete from disk
        stored_path = row["stored_path"]
        if os.path.exists(stored_path):
            os.remove(stored_path)

        conn.execute("DELETE FROM file_uploads WHERE id = ?", (file_id,))

    return JSONResponse(content={"deleted": True})
