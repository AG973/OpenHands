"""Server entrypoint — routes through canonical V1 app_server when available.

The OPENHANDS_SERVER_VERSION env var controls which server is started:
  - "v0" (default): openhands.server.listen:app (stable, production-ready)
  - "v1": openhands.app_server (canonical path through EngineeringOS/TaskEngine)

Fix #4 (ChatGPT review): V1 path exists and is selectable. Default remains V0
until openhands.app_server exports a working `app` object.
"""

import os

import uvicorn

from openhands.core.logger import get_uvicorn_json_log_config
from openhands.core.logger import openhands_logger as logger


def main():
    # Fix #4: V1 path exists; default stays V0 until app_server:app is ready.
    server_version = os.getenv('OPENHANDS_SERVER_VERSION', 'v0').lower()
    log_config = None
    if os.getenv('LOG_JSON', '0') in ('1', 'true', 'True'):
        log_config = get_uvicorn_json_log_config()

    if server_version == 'v1':
        # V1 canonical path (opt-in until app_server:app is implemented)
        try:
            import importlib

            mod = importlib.import_module('openhands.app_server')
            if not hasattr(mod, 'app'):
                raise AttributeError("openhands.app_server has no 'app' attribute")
            app_module = 'openhands.app_server:app'
            logger.info('[Server] Starting V1 canonical app_server')
        except (ImportError, AttributeError) as exc:
            logger.warning(
                f'[Server] V1 app_server not available ({exc}), '
                f'falling back to V0 server'
            )
            app_module = 'openhands.server.listen:app'
    else:
        app_module = 'openhands.server.listen:app'
        logger.info(
            '[Server] Starting V0 server '
            '(set OPENHANDS_SERVER_VERSION=v1 for canonical path)'
        )

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
