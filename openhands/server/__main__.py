"""Server entrypoint — routes through canonical V1 app_server when available.

The OPENHANDS_SERVER_VERSION env var controls which server is started:
  - "v1" (default): openhands.app_server (V1 canonical path)
  - "v0": openhands.server.listen:app (legacy, deprecated April 1, 2026)

All new deployments should use V1. The V0 path is preserved only for
backward compatibility during the migration window.
"""

import os

import uvicorn

from openhands.core.logger import get_uvicorn_json_log_config
from openhands.core.logger import openhands_logger as logger


def main():
    server_version = os.getenv('OPENHANDS_SERVER_VERSION', 'v0').lower()
    log_config = None
    if os.getenv('LOG_JSON', '0') in ('1', 'true', 'True'):
        log_config = get_uvicorn_json_log_config()

    if server_version == 'v1':
        app_module = 'openhands.app_server:app'
        logger.info('[Server] Starting V1 canonical app_server')
    else:
        app_module = 'openhands.server.listen:app'
        logger.info('[Server] Starting legacy V0 server (set OPENHANDS_SERVER_VERSION=v1 for canonical path)')

    uvicorn.run(
        app_module,
        host='0.0.0.0',
        port=int(os.environ.get('port') or '3000'),
        log_level='debug' if os.environ.get('DEBUG') else 'info',
        log_config=log_config,
        # If LOG_JSON enabled, force colors off; otherwise let uvicorn default
        use_colors=False if log_config else None,
    )


if __name__ == '__main__':
    main()
