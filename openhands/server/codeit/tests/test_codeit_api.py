"""Comprehensive tests for CODEIT backend APIs.

Tests cover: auth, skills CRUD, knowledge CRUD, prompts CRUD,
connectors CRUD, deploy jobs, file uploads, health/stats endpoints.

Uses a temporary SQLite DB per test session to avoid polluting production data.
"""

import io
import json
import os
import tempfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Point CODEIT to a temp directory BEFORE importing any codeit modules
_tmpdir = tempfile.mkdtemp(prefix="codeit_test_")
os.environ["CODEIT_DATA_DIR"] = _tmpdir
os.environ["CODEIT_UPLOAD_DIR"] = os.path.join(_tmpdir, "uploads")

from openhands.server.codeit.router import get_codeit_routers  # noqa: E402


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app():
    """Create a FastAPI app with all CODEIT routers for testing."""
    _app = FastAPI()
    for router in get_codeit_routers():
        _app.include_router(router)
    return _app


@pytest.fixture(scope="module")
def client(app):
    return TestClient(app)


@pytest.fixture(scope="module")
def auth_token(client):
    """Register a test user and return auth token + headers."""
    resp = client.post("/api/codeit/auth/register", json={
        "username": "testuser",
        "password": "testpass123",
        "display_name": "Test User",
    })
    assert resp.status_code == 201, f"Register failed: {resp.text}"
    data = resp.json()
    assert "token" in data
    return data["token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


# ─── Auth Tests ──────────────────────────────────────────────────────────────

class TestAuth:
    def test_register_new_user(self, client):
        resp = client.post("/api/codeit/auth/register", json={
            "username": "newuser",
            "password": "pass456",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "newuser"
        assert "token" in data
        assert "user_id" in data

    def test_register_duplicate_user(self, client):
        # First registration
        client.post("/api/codeit/auth/register", json={
            "username": "dupuser",
            "password": "pass",
        })
        # Second should fail
        resp = client.post("/api/codeit/auth/register", json={
            "username": "dupuser",
            "password": "pass",
        })
        assert resp.status_code == 409
        assert "already exists" in resp.json().get("error", "")

    def test_login_valid(self, client):
        # Register first
        client.post("/api/codeit/auth/register", json={
            "username": "logintest",
            "password": "mypassword",
        })
        resp = client.post("/api/codeit/auth/login", json={
            "username": "logintest",
            "password": "mypassword",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["username"] == "logintest"

    def test_login_invalid_password(self, client):
        resp = client.post("/api/codeit/auth/login", json={
            "username": "logintest",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/codeit/auth/login", json={
            "username": "doesnotexist",
            "password": "whatever",
        })
        assert resp.status_code == 401

    def test_validate_token(self, client, auth_headers):
        resp = client.post("/api/codeit/auth/validate", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["username"] == "testuser"

    def test_validate_invalid_token(self, client):
        resp = client.post("/api/codeit/auth/validate", headers={
            "Authorization": "Bearer invalid.token.here"
        })
        assert resp.status_code == 401
        assert resp.json()["valid"] is False

    def test_get_me(self, client, auth_headers):
        resp = client.get("/api/codeit/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "testuser"
        assert data["display_name"] == "Test User"
        assert "user_id" in data
        assert "created_at" in data

    def test_get_me_no_auth(self, client):
        resp = client.get("/api/codeit/auth/me")
        assert resp.status_code == 401


# ─── Skills Tests ────────────────────────────────────────────────────────────

class TestSkills:
    def test_list_skills_empty(self, client, auth_headers):
        resp = client.get("/api/codeit/skills", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_create_skill(self, client, auth_headers):
        resp = client.post("/api/codeit/skills", headers=auth_headers, json={
            "name": "Python Expert",
            "description": "Writes clean Python code",
            "content": "You are a Python expert...",
            "enabled": True,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Python Expert"
        assert data["enabled"] is True
        assert "id" in data

    def test_list_skills_after_create(self, client, auth_headers):
        resp = client.get("/api/codeit/skills", headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 1
        assert any(s["name"] == "Python Expert" for s in items)

    def test_update_skill(self, client, auth_headers):
        # Create a skill to update
        create_resp = client.post("/api/codeit/skills", headers=auth_headers, json={
            "name": "To Update",
            "description": "Original",
            "content": "original content",
        })
        skill_id = create_resp.json()["id"]

        resp = client.put(f"/api/codeit/skills/{skill_id}", headers=auth_headers, json={
            "name": "Updated Skill",
            "enabled": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Skill"
        assert data["enabled"] is False

    def test_update_nonexistent_skill(self, client, auth_headers):
        resp = client.put("/api/codeit/skills/nonexistent-id", headers=auth_headers, json={
            "name": "Nope",
        })
        assert resp.status_code == 404

    def test_delete_skill(self, client, auth_headers):
        create_resp = client.post("/api/codeit/skills", headers=auth_headers, json={
            "name": "To Delete",
        })
        skill_id = create_resp.json()["id"]

        resp = client.delete(f"/api/codeit/skills/{skill_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        # Verify it's gone
        list_resp = client.get("/api/codeit/skills", headers=auth_headers)
        assert not any(s["id"] == skill_id for s in list_resp.json()["items"])

    def test_delete_nonexistent_skill(self, client, auth_headers):
        resp = client.delete("/api/codeit/skills/nonexistent-id", headers=auth_headers)
        assert resp.status_code == 404

    def test_skills_require_auth(self, client):
        resp = client.get("/api/codeit/skills")
        assert resp.status_code == 401


# ─── Knowledge Tests ─────────────────────────────────────────────────────────

class TestKnowledge:
    def test_list_knowledge_empty(self, client, auth_headers):
        resp = client.get("/api/codeit/knowledge", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_create_knowledge(self, client, auth_headers):
        resp = client.post("/api/codeit/knowledge", headers=auth_headers, json={
            "title": "Docker Commands",
            "content": "docker build -t app .",
            "tags": ["docker", "devops"],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Docker Commands"
        assert data["tags"] == ["docker", "devops"]
        assert "id" in data

    def test_list_knowledge_with_search(self, client, auth_headers):
        resp = client.get("/api/codeit/knowledge?q=docker", headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 1
        assert items[0]["title"] == "Docker Commands"

    def test_update_knowledge(self, client, auth_headers):
        create_resp = client.post("/api/codeit/knowledge", headers=auth_headers, json={
            "title": "To Update",
            "content": "original",
            "tags": ["test"],
        })
        item_id = create_resp.json()["id"]

        resp = client.put(f"/api/codeit/knowledge/{item_id}", headers=auth_headers, json={
            "title": "Updated Knowledge",
            "tags": ["updated", "test"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated Knowledge"
        assert "updated" in data["tags"]

    def test_delete_knowledge(self, client, auth_headers):
        create_resp = client.post("/api/codeit/knowledge", headers=auth_headers, json={
            "title": "To Delete",
        })
        item_id = create_resp.json()["id"]

        resp = client.delete(f"/api/codeit/knowledge/{item_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_knowledge_requires_auth(self, client):
        resp = client.get("/api/codeit/knowledge")
        assert resp.status_code == 401


# ─── Prompts Tests ───────────────────────────────────────────────────────────

class TestPrompts:
    def test_list_prompts_empty(self, client, auth_headers):
        resp = client.get("/api/codeit/prompts", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_create_prompt(self, client, auth_headers):
        resp = client.post("/api/codeit/prompts", headers=auth_headers, json={
            "name": "Code Review",
            "content": "You are a code reviewer...",
            "active": True,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Code Review"
        assert data["active"] is True

    def test_update_prompt(self, client, auth_headers):
        create_resp = client.post("/api/codeit/prompts", headers=auth_headers, json={
            "name": "To Update",
            "content": "original",
        })
        prompt_id = create_resp.json()["id"]

        resp = client.put(f"/api/codeit/prompts/{prompt_id}", headers=auth_headers, json={
            "name": "Updated Prompt",
            "active": True,
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Prompt"

    def test_delete_prompt(self, client, auth_headers):
        create_resp = client.post("/api/codeit/prompts", headers=auth_headers, json={
            "name": "To Delete",
        })
        prompt_id = create_resp.json()["id"]

        resp = client.delete(f"/api/codeit/prompts/{prompt_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_prompts_require_auth(self, client):
        resp = client.get("/api/codeit/prompts")
        assert resp.status_code == 401


# ─── Connectors Tests ────────────────────────────────────────────────────────

class TestConnectors:
    def test_list_connectors_empty(self, client, auth_headers):
        resp = client.get("/api/codeit/connectors", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_create_connector(self, client, auth_headers):
        resp = client.post("/api/codeit/connectors", headers=auth_headers, json={
            "name": "GitHub",
            "type": "github",
            "icon": "github",
            "config": {"token": "ghp_test123", "org": "myorg"},
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "GitHub"
        assert data["type"] == "github"
        assert "id" in data

    def test_connector_secrets_masked_in_list(self, client, auth_headers):
        """Secrets should be masked when listing connectors."""
        resp = client.get("/api/codeit/connectors", headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        github_items = [c for c in items if c["type"] == "github"]
        assert len(github_items) >= 1
        # Token should be masked
        for c in github_items:
            if "token" in c["config"]:
                assert c["config"]["token"].startswith("***")

    def test_update_connector(self, client, auth_headers):
        create_resp = client.post("/api/codeit/connectors", headers=auth_headers, json={
            "name": "AWS",
            "type": "aws",
            "icon": "aws",
            "config": {"access_key": "AKIA1234", "secret_key": "secret", "region": "us-east-1"},
        })
        conn_id = create_resp.json()["id"]

        resp = client.put(f"/api/codeit/connectors/{conn_id}", headers=auth_headers, json={
            "status": "connected",
            "config": {"access_key": "AKIA5678", "secret_key": "newsecret", "region": "eu-west-1"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "connected"

    def test_disconnect_connector(self, client, auth_headers):
        create_resp = client.post("/api/codeit/connectors", headers=auth_headers, json={
            "name": "Discord",
            "type": "discord",
            "icon": "discord",
            "config": {"bot_token": "test123"},
        })
        conn_id = create_resp.json()["id"]

        resp = client.post(f"/api/codeit/connectors/{conn_id}/disconnect", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["disconnected"] is True

    def test_delete_connector(self, client, auth_headers):
        create_resp = client.post("/api/codeit/connectors", headers=auth_headers, json={
            "name": "To Delete",
            "type": "test",
            "icon": "test",
        })
        conn_id = create_resp.json()["id"]

        resp = client.delete(f"/api/codeit/connectors/{conn_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_connectors_require_auth(self, client):
        resp = client.get("/api/codeit/connectors")
        assert resp.status_code == 401


# ─── Deploy Jobs Tests ───────────────────────────────────────────────────────

class TestDeployJobs:
    def test_list_jobs_empty(self, client, auth_headers):
        resp = client.get("/api/codeit/deploy/jobs", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_create_deploy_job(self, client, auth_headers):
        resp = client.post("/api/codeit/deploy/jobs", headers=auth_headers, json={
            "target": "docker",
            "config": {"workspace": "/tmp/test-app", "port": "8080"},
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["target"] == "docker"
        assert data["status"] == "pending"
        assert "id" in data

    def test_get_deploy_job(self, client, auth_headers):
        create_resp = client.post("/api/codeit/deploy/jobs", headers=auth_headers, json={
            "target": "local",
            "config": {"workspace": "/tmp/app", "deploy_dir": "/tmp/deploy"},
        })
        job_id = create_resp.json()["id"]

        resp = client.get(f"/api/codeit/deploy/jobs/{job_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == job_id
        assert data["target"] == "local"

    def test_get_deploy_logs(self, client, auth_headers):
        create_resp = client.post("/api/codeit/deploy/jobs", headers=auth_headers, json={
            "target": "custom",
            "config": {},
        })
        job_id = create_resp.json()["id"]

        # Give background thread a moment
        import time
        time.sleep(0.5)

        resp = client.get(f"/api/codeit/deploy/jobs/{job_id}/logs", headers=auth_headers)
        assert resp.status_code == 200
        assert "logs" in resp.json()

    def test_get_nonexistent_job(self, client, auth_headers):
        resp = client.get("/api/codeit/deploy/jobs/nonexistent", headers=auth_headers)
        assert resp.status_code == 404

    def test_deploy_requires_auth(self, client):
        resp = client.get("/api/codeit/deploy/jobs")
        assert resp.status_code == 401


# ─── File Upload Tests ───────────────────────────────────────────────────────

class TestFileUploads:
    def test_upload_file(self, client, auth_headers):
        file_content = b"print('hello world')"
        resp = client.post(
            "/api/codeit/uploads",
            headers=auth_headers,
            files={"file": ("test.py", io.BytesIO(file_content), "text/x-python")},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["original_name"] == "test.py"
        assert data["size_bytes"] == len(file_content)
        assert "id" in data

    def test_upload_disallowed_extension(self, client, auth_headers):
        resp = client.post(
            "/api/codeit/uploads",
            headers=auth_headers,
            files={"file": ("malware.exe", io.BytesIO(b"evil"), "application/octet-stream")},
        )
        assert resp.status_code == 400
        assert "not allowed" in resp.json().get("error", "")

    def test_upload_path_traversal(self, client, auth_headers):
        resp = client.post(
            "/api/codeit/uploads",
            headers=auth_headers,
            files={"file": ("../../../etc/passwd", io.BytesIO(b"bad"), "text/plain")},
        )
        assert resp.status_code == 400
        assert "Invalid filename" in resp.json().get("error", "")

    def test_list_uploads(self, client, auth_headers):
        # Upload a file first
        client.post(
            "/api/codeit/uploads",
            headers=auth_headers,
            files={"file": ("list_test.json", io.BytesIO(b'{"key":"val"}'), "application/json")},
        )
        resp = client.get("/api/codeit/uploads", headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 1

    def test_download_file(self, client, auth_headers):
        content = b"download test content"
        upload_resp = client.post(
            "/api/codeit/uploads",
            headers=auth_headers,
            files={"file": ("download.txt", io.BytesIO(content), "text/plain")},
        )
        file_id = upload_resp.json()["id"]

        resp = client.get(f"/api/codeit/uploads/{file_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.content == content

    def test_delete_upload(self, client, auth_headers):
        upload_resp = client.post(
            "/api/codeit/uploads",
            headers=auth_headers,
            files={"file": ("to_delete.txt", io.BytesIO(b"delete me"), "text/plain")},
        )
        file_id = upload_resp.json()["id"]

        resp = client.delete(f"/api/codeit/uploads/{file_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        # Verify it's gone
        resp = client.get(f"/api/codeit/uploads/{file_id}", headers=auth_headers)
        assert resp.status_code == 404

    def test_uploads_require_auth(self, client):
        resp = client.get("/api/codeit/uploads")
        assert resp.status_code == 401


# ─── Health & Stats Tests ────────────────────────────────────────────────────

class TestHealthStats:
    def test_health_endpoint(self, client):
        resp = client.get("/api/codeit/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("ok", "degraded")
        assert "database" in data["checks"]
        assert "disk" in data["checks"]
        assert "uptime" in data["checks"]

    def test_stats_endpoint(self, client):
        resp = client.get("/api/codeit/stats")
        assert resp.status_code == 200
        stats = resp.json()["stats"]
        assert "users" in stats
        assert "skills" in stats
        assert "knowledge" in stats
        assert "prompts" in stats
        assert "connectors" in stats
        assert "deploy_jobs" in stats
        assert "file_uploads" in stats
        # Should have at least the users we registered
        assert stats["users"] >= 1


# ─── User Isolation Tests ────────────────────────────────────────────────────

class TestUserIsolation:
    """Verify that user A cannot see/modify user B's data."""

    def test_skills_isolated(self, client, auth_headers):
        # Create skill as testuser
        client.post("/api/codeit/skills", headers=auth_headers, json={
            "name": "testuser-only-skill",
        })

        # Register a different user
        resp = client.post("/api/codeit/auth/register", json={
            "username": "otheruser",
            "password": "otherpass",
        })
        other_token = resp.json()["token"]
        other_headers = {"Authorization": f"Bearer {other_token}"}

        # Other user should NOT see testuser's skills
        resp = client.get("/api/codeit/skills", headers=other_headers)
        items = resp.json()["items"]
        assert not any(s["name"] == "testuser-only-skill" for s in items)

    def test_knowledge_isolated(self, client, auth_headers):
        # Create knowledge as testuser
        client.post("/api/codeit/knowledge", headers=auth_headers, json={
            "title": "testuser-only-knowledge",
        })

        # Use otheruser (already registered above)
        resp = client.post("/api/codeit/auth/login", json={
            "username": "otheruser",
            "password": "otherpass",
        })
        other_headers = {"Authorization": f"Bearer {resp.json()['token']}"}

        # Other user should NOT see testuser's knowledge
        resp = client.get("/api/codeit/knowledge", headers=other_headers)
        items = resp.json()["items"]
        assert not any(k["title"] == "testuser-only-knowledge" for k in items)


# ─── Deploy Path Validation Tests ────────────────────────────────────────────

class TestDeployValidation:
    """Verify deploy path restrictions work."""

    def test_deploy_with_valid_path(self, client, auth_headers):
        resp = client.post("/api/codeit/deploy/jobs", headers=auth_headers, json={
            "target": "local",
            "config": {"workspace": "/tmp/myapp", "deploy_dir": "/tmp/deploy"},
        })
        assert resp.status_code == 201

    def test_deploy_job_created_with_custom_target(self, client, auth_headers):
        """Custom targets get queued for manual execution."""
        resp = client.post("/api/codeit/deploy/jobs", headers=auth_headers, json={
            "target": "aws",
            "config": {},
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["target"] == "aws"
        assert data["status"] == "pending"
