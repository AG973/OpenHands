"""CODEIT Deploy Jobs routes — real backend-tracked deployment workflows."""

import json
import subprocess
import threading
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from openhands.core.logger import openhands_logger as logger
from openhands.server.codeit.database import get_db
from openhands.server.codeit.routes_auth import TokenPayload, require_auth

router = APIRouter(prefix="/api/codeit/deploy", tags=["codeit-deploy"])


class DeployJobCreate(BaseModel):
    target: str  # 'local', 'docker', 'aws', 'runpod', 'custom'
    config: dict = {}


class DeployJobUpdate(BaseModel):
    status: Optional[str] = None
    logs: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None


def _row_to_dict(r) -> dict:
    config = {}
    try:
        config = json.loads(r["config"]) if r["config"] else {}
    except (json.JSONDecodeError, TypeError):
        config = {}
    return {
        "id": r["id"],
        "target": r["target"],
        "status": r["status"],
        "logs": r["logs"],
        "config": config,
        "result": r["result"],
        "error": r["error"],
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
        "finished_at": r["finished_at"],
    }


def _run_deploy_job(job_id: str, target: str, config: dict) -> None:
    """Run deployment in background thread. Updates DB with progress."""
    def _append_log(conn, jid: str, line: str):
        conn.execute(
            "UPDATE deploy_jobs SET logs = logs || ?, updated_at = datetime('now') WHERE id = ?",
            (line + "\n", jid),
        )
        conn.commit()

    try:
        with get_db() as conn:
            conn.execute(
                "UPDATE deploy_jobs SET status = 'running', updated_at = datetime('now') WHERE id = ?",
                (job_id,),
            )

        if target == "docker":
            _run_docker_deploy(job_id, config)
        elif target == "local":
            _run_local_deploy(job_id, config)
        else:
            with get_db() as conn:
                _append_log(conn, job_id, f"[INFO] Deploy target '{target}' — queued for manual execution")
                conn.execute(
                    "UPDATE deploy_jobs SET status = 'pending_manual', updated_at = datetime('now') WHERE id = ?",
                    (job_id,),
                )

    except Exception as e:
        logger.error(f"Deploy job {job_id} failed: {e}")
        with get_db() as conn:
            conn.execute(
                "UPDATE deploy_jobs SET status = 'failed', error = ?, finished_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
                (str(e), job_id),
            )


def _run_docker_deploy(job_id: str, config: dict) -> None:
    """Build and run Docker container."""
    workspace = config.get("workspace", "/root/workspace")
    dockerfile = config.get("dockerfile", "Dockerfile")
    image_name = config.get("image_name", f"codeit-deploy-{job_id[:8]}")
    port = config.get("port", "8000")

    commands = [
        f"cd {workspace} && docker build -t {image_name} -f {dockerfile} .",
        f"docker run -d --name {image_name} -p {port}:{port} {image_name}",
    ]

    with get_db() as conn:
        for cmd in commands:
            conn.execute(
                "UPDATE deploy_jobs SET logs = logs || ?, updated_at = datetime('now') WHERE id = ?",
                (f"$ {cmd}\n", job_id),
            )
            conn.commit()

            try:
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=300
                )
                output = result.stdout + result.stderr
                conn.execute(
                    "UPDATE deploy_jobs SET logs = logs || ?, updated_at = datetime('now') WHERE id = ?",
                    (output + "\n", job_id),
                )
                conn.commit()

                if result.returncode != 0:
                    conn.execute(
                        "UPDATE deploy_jobs SET status = 'failed', error = ?, finished_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
                        (f"Command failed with exit code {result.returncode}", job_id),
                    )
                    return
            except subprocess.TimeoutExpired:
                conn.execute(
                    "UPDATE deploy_jobs SET status = 'failed', error = 'Command timed out', finished_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
                    (job_id,),
                )
                return

        conn.execute(
            "UPDATE deploy_jobs SET status = 'success', result = ?, finished_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
            (f"Container {image_name} running on port {port}", job_id),
        )


def _run_local_deploy(job_id: str, config: dict) -> None:
    """Run local deployment (copy files, restart service)."""
    workspace = config.get("workspace", "/root/workspace")
    deploy_dir = config.get("deploy_dir", "/var/www/app")

    with get_db() as conn:
        log_line = f"[INFO] Local deploy from {workspace} to {deploy_dir}\n"
        conn.execute(
            "UPDATE deploy_jobs SET logs = logs || ?, updated_at = datetime('now') WHERE id = ?",
            (log_line, job_id),
        )
        conn.commit()

        try:
            cmd = f"rsync -av --delete {workspace}/ {deploy_dir}/"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
            output = f"$ {cmd}\n{result.stdout}{result.stderr}\n"
            conn.execute(
                "UPDATE deploy_jobs SET logs = logs || ?, updated_at = datetime('now') WHERE id = ?",
                (output, job_id),
            )
            conn.commit()

            if result.returncode == 0:
                conn.execute(
                    "UPDATE deploy_jobs SET status = 'success', result = ?, finished_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
                    (f"Deployed to {deploy_dir}", job_id),
                )
            else:
                conn.execute(
                    "UPDATE deploy_jobs SET status = 'failed', error = ?, finished_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
                    (f"rsync failed with exit code {result.returncode}", job_id),
                )
        except subprocess.TimeoutExpired:
            conn.execute(
                "UPDATE deploy_jobs SET status = 'failed', error = 'Deploy timed out', finished_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
                (job_id,),
            )


@router.get("/jobs")
async def list_deploy_jobs(user: TokenPayload = Depends(require_auth)) -> JSONResponse:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, target, status, logs, config, result, error, created_at, updated_at, finished_at "
            "FROM deploy_jobs WHERE user_id = ? ORDER BY created_at DESC LIMIT 50",
            (user.user_id,),
        ).fetchall()
    return JSONResponse(content={"items": [_row_to_dict(r) for r in rows]})


@router.get("/jobs/{job_id}")
async def get_deploy_job(
    job_id: str, user: TokenPayload = Depends(require_auth)
) -> JSONResponse:
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, target, status, logs, config, result, error, created_at, updated_at, finished_at "
            "FROM deploy_jobs WHERE id = ? AND user_id = ?",
            (job_id, user.user_id),
        ).fetchone()
    if not row:
        return JSONResponse(status_code=404, content={"error": "Deploy job not found"})
    return JSONResponse(content=_row_to_dict(row))


@router.post("/jobs")
async def create_deploy_job(
    body: DeployJobCreate, user: TokenPayload = Depends(require_auth)
) -> JSONResponse:
    job_id = str(uuid.uuid4())
    config_json = json.dumps(body.config)
    with get_db() as conn:
        conn.execute(
            "INSERT INTO deploy_jobs (id, user_id, target, status, config) VALUES (?, ?, ?, 'pending', ?)",
            (job_id, user.user_id, body.target, config_json),
        )

    # Start deployment in background
    thread = threading.Thread(
        target=_run_deploy_job, args=(job_id, body.target, body.config), daemon=True
    )
    thread.start()

    logger.info(f"CODEIT: Deploy job {job_id} created (target={body.target})")
    return JSONResponse(status_code=201, content={"id": job_id, "target": body.target, "status": "pending"})


@router.get("/jobs/{job_id}/logs")
async def get_deploy_logs(
    job_id: str, user: TokenPayload = Depends(require_auth)
) -> JSONResponse:
    with get_db() as conn:
        row = conn.execute(
            "SELECT logs, status FROM deploy_jobs WHERE id = ? AND user_id = ?",
            (job_id, user.user_id),
        ).fetchone()
    if not row:
        return JSONResponse(status_code=404, content={"error": "Deploy job not found"})
    return JSONResponse(content={"logs": row["logs"], "status": row["status"]})
