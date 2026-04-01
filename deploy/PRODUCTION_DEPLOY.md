# CODEIT Production Deployment Guide

## Prerequisites

- Ubuntu 22.04+ server with 4GB+ RAM
- Python 3.12+
- Node.js 22+ (for frontend build)
- Docker (optional, for containerized deploy)
- Nginx (for reverse proxy)

## Quick Start (Single Server)

```bash
# 1. Clone the repo
git clone https://github.com/AG973/OpenHands.git /opt/codeit
cd /opt/codeit

# 2. Install Python dependencies
pip install -e '.[dev]'

# 3. Build frontend
cd codeit-ui
npm ci
npm run build
cd ..

# 4. Set environment variables
export CODEIT_DATA_DIR=~/.codeit
export CODEIT_ADMIN_USER=admin
export CODEIT_ADMIN_PASS=<your-secure-password>
export CODEIT_CORS_ORIGINS=https://your-domain.com

# 5. Start backend
python -m uvicorn openhands.server.app:app --host 0.0.0.0 --port 8080

# 6. Serve frontend (via Nginx or static server)
# See Nginx config below
```

## Systemd Services

Copy service files from `deploy/systemd/` to `/etc/systemd/system/`:

```bash
sudo cp deploy/systemd/codeit-backend.service /etc/systemd/system/
sudo cp deploy/systemd/codeit-frontend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable codeit-backend codeit-frontend
sudo systemctl start codeit-backend codeit-frontend
```

## Nginx Configuration

Copy and customize the Nginx config:

```bash
sudo cp deploy/nginx/codeit.conf /etc/nginx/sites-available/codeit
sudo ln -s /etc/nginx/sites-available/codeit /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Key Nginx settings:
- Frontend static files served from `codeit-ui/dist/`
- Backend API proxied at `/api/` to `localhost:8080`
- WebSocket upgrade headers for `/socket.io/`

## Docker Compose

```bash
cd deploy
cp .env.example .env
# Edit .env with your settings
docker compose up -d
```

## Database

### Location
- Default: `~/.codeit/codeit.db` (SQLite with WAL mode)
- Override: set `CODEIT_DATA_DIR` environment variable

### Schema Migrations
Migrations run automatically on startup. The current schema version is tracked in the `schema_version` table.

### Manual Migration Check
```bash
sqlite3 ~/.codeit/codeit.db "SELECT MAX(version) FROM schema_version;"
```

### Known Migration: config_encrypted to config_json
If upgrading from an older version that used `config_encrypted` column in the connectors table:

```sql
-- Check if old column exists
.schema connectors

-- If config_encrypted exists but config_json doesn't:
ALTER TABLE connectors RENAME COLUMN config_encrypted TO config_json;
```

### Backup
```bash
# Hot backup (WAL mode safe)
sqlite3 ~/.codeit/codeit.db ".backup /path/to/backup.db"

# Or simply copy (stop service first for consistency)
sudo systemctl stop codeit-backend
cp ~/.codeit/codeit.db ~/.codeit/codeit.db.backup
sudo systemctl start codeit-backend
```

### Restore
```bash
sudo systemctl stop codeit-backend
cp /path/to/backup.db ~/.codeit/codeit.db
sudo systemctl start codeit-backend
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `CODEIT_DATA_DIR` | `~/.codeit` | Database and uploads directory |
| `CODEIT_UPLOAD_DIR` | `$CODEIT_DATA_DIR/uploads` | File upload storage |
| `CODEIT_ADMIN_USER` | `admin` | Default admin username |
| `CODEIT_ADMIN_PASS` | `codeit` | Default admin password (CHANGE THIS) |
| `CODEIT_CORS_ORIGINS` | `*` | Allowed CORS origins (comma-separated) |
| `LLM_MODEL` | - | Default LLM model name |
| `LLM_BASE_URL` | - | LLM API base URL |
| `LLM_API_KEY` | - | LLM API key |

## JWT Secret

- Auto-generated on first run at `~/.codeit/.jwt_secret`
- Tokens expire after 7 days
- To force all users to re-login: delete `.jwt_secret` and restart

## File Uploads

- Stored in `$CODEIT_UPLOAD_DIR` (default: `~/.codeit/uploads/`)
- Max file size: 50MB
- Allowed extensions: code files, images, documents, archives
- Path traversal protection enforced

## Recovery Commands

```bash
# Check backend status
sudo systemctl status codeit-backend

# View backend logs
sudo journalctl -u codeit-backend -f

# Restart backend
sudo systemctl restart codeit-backend

# Check database integrity
sqlite3 ~/.codeit/codeit.db "PRAGMA integrity_check;"

# Check WAL mode
sqlite3 ~/.codeit/codeit.db "PRAGMA journal_mode;"

# Reset admin password
python3 -c "
from openhands.server.codeit.auth import hash_password
from openhands.server.codeit.database import get_db, init_db
init_db()
pw = hash_password('new-secure-password')
with get_db() as conn:
    conn.execute('UPDATE users SET password_hash = ? WHERE username = ?', (pw, 'admin'))
print('Password reset complete')
"

# Clear all deploy jobs (if stuck)
sqlite3 ~/.codeit/codeit.db "UPDATE deploy_jobs SET status='failed', error='Manual cleanup' WHERE status IN ('pending','running');"

# Check disk usage
du -sh ~/.codeit/
du -sh ~/.codeit/uploads/

# Clean old uploads (older than 30 days)
find ~/.codeit/uploads/ -type f -mtime +30 -delete
```

## Troubleshooting

### Backend won't start
1. Check Python version: `python3 --version` (needs 3.12+)
2. Check if port is in use: `lsof -i :8080`
3. Check database permissions: `ls -la ~/.codeit/`
4. Check logs: `journalctl -u codeit-backend --no-pager -n 50`

### Frontend shows blank page
1. Verify build exists: `ls codeit-ui/dist/index.html`
2. Check Nginx config: `nginx -t`
3. Check browser console for errors
4. Verify `VITE_BACKEND_URL` was set during build

### WebSocket connection fails
1. Check Nginx has WebSocket upgrade headers
2. Verify backend is running: `curl http://localhost:8080/api/codeit/health`
3. Check firewall rules for port 8080

### Auth issues
1. Verify JWT secret exists: `ls -la ~/.codeit/.jwt_secret`
2. Check token expiry (7 days)
3. Try re-registering or resetting password (see recovery commands)

### Database locked errors
1. Check no zombie processes: `fuser ~/.codeit/codeit.db`
2. Verify WAL mode: `sqlite3 ~/.codeit/codeit.db "PRAGMA journal_mode;"`
3. Restart backend to clear stale connections
