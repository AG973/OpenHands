"""Server entrypoint — canonical path with V0 as explicit opt-in fallback.

The OPENHANDS_SERVER_VERSION env var controls which server is started:
  - "v1" (default): openhands.app_server (canonical path through EngineeringOS/TaskEngine)
  - "v0": openhands.server.listen:app (legacy, deprecated April 1, 2026 — explicit opt-in only)

Fix #4 (ChatGPT review): Choose one server deployment target. V1 is now the default.
V0 requires explicit OPENHANDS_SERVER_VERSION=v0 to activate.
"""

import os

import uvicorn

from openhands.core.logger import get_uvicorn_json_log_config
from openhands.core.logger import openhands_logger as logger


def main():
    # Fix #4: Default to V1 canonical path. V0 is explicit opt-in only.
    server_version = os.getenv('OPENHANDS_SERVER_VERSION', 'v1').lower()
    log_config = None
    if os.getenv('LOG_JSON', '0') in ('1', 'true', 'True'):
        log_config = get_uvicorn_json_log_config()

    if server_version == 'v0':
        # Explicit V0 legacy opt-in
        app_module = 'openhands.server.listen:app'
        logger.info(
            '[Server] Starting legacy V0 server (explicit opt-in via '
            'OPENHANDS_SERVER_VERSION=v0, deprecated April 1, 2026)'
        )
    else:
        # V1 canonical path (default)
        try:
            import importlib
            mod = importlib.import_module('openhands.app_server')
            if not hasattr(mod, 'app'):
                raise AttributeError("openhands.app_server has no 'app' attribute")
            app_module = 'openhands.app_server:app'
            logger.info('[Server] Starting V1 canonical app_server (default)')
        except (ImportError, AttributeError) as exc:
            logger.warning(
                f'[Server] V1 app_server not available ({exc}), '
                f'falling back to V0 server'
            )
            app_module = 'openhands.server.listen:app'

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
