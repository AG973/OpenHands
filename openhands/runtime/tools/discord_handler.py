"""Discord operations execution handler.

Executes Discord API calls using the requests library.
Uses the Discord REST API v10.
"""

import json
import os
from typing import Any

import requests

from openhands.core.logger import openhands_logger as logger

DISCORD_API_BASE = 'https://discord.com/api/v10'


def _get_headers() -> dict[str, str]:
    """Get Discord API headers with bot token."""
    token = os.environ.get('DISCORD_BOT_TOKEN', '')
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bot {token}'
    return headers


def _api_get(endpoint: str, params: dict | None = None) -> dict[str, Any]:
    """Make a GET request to the Discord API."""
    url = f'{DISCORD_API_BASE}{endpoint}'
    try:
        resp = requests.get(url, headers=_get_headers(), params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        return {'error': str(e), 'status_code': resp.status_code}
    except Exception as e:
        return {'error': str(e)}


def _api_post(endpoint: str, data: dict | None = None) -> dict[str, Any]:
    """Make a POST request to the Discord API."""
    url = f'{DISCORD_API_BASE}{endpoint}'
    try:
        resp = requests.post(url, headers=_get_headers(), json=data, timeout=15)
        resp.raise_for_status()
        return resp.json() if resp.content else {'success': True}
    except requests.exceptions.HTTPError as e:
        return {'error': str(e), 'status_code': resp.status_code}
    except Exception as e:
        return {'error': str(e)}


def send_message(channel_id: str, message: str) -> dict[str, Any]:
    """Send a message to a Discord channel."""
    return _api_post(f'/channels/{channel_id}/messages', {'content': message})


def send_embed(channel_id: str, embed_json: str) -> dict[str, Any]:
    """Send a rich embed message."""
    try:
        embed = json.loads(embed_json) if isinstance(embed_json, str) else embed_json
    except json.JSONDecodeError:
        return {'error': 'Invalid embed JSON'}
    return _api_post(f'/channels/{channel_id}/messages', {'embeds': [embed]})


def get_messages(channel_id: str, limit: int = 50) -> dict[str, Any]:
    """Get recent messages from a channel."""
    return _api_get(f'/channels/{channel_id}/messages', {'limit': min(limit, 100)})


def create_channel(server_id: str, name: str, channel_type: str = 'text', topic: str = '') -> dict[str, Any]:
    """Create a new channel in a server."""
    type_map = {'text': 0, 'voice': 2, 'category': 4, 'announcement': 5}
    data: dict[str, Any] = {'name': name, 'type': type_map.get(channel_type, 0)}
    if topic:
        data['topic'] = topic
    return _api_post(f'/guilds/{server_id}/channels', data)


def list_channels(server_id: str) -> dict[str, Any]:
    """List all channels in a server."""
    return _api_get(f'/guilds/{server_id}/channels')


def get_server_info(server_id: str) -> dict[str, Any]:
    """Get server (guild) information."""
    return _api_get(f'/guilds/{server_id}')


def list_members(server_id: str, limit: int = 50) -> dict[str, Any]:
    """List server members."""
    return _api_get(f'/guilds/{server_id}/members', {'limit': min(limit, 100)})


def create_webhook(channel_id: str, name: str = 'OpenHands Bot') -> dict[str, Any]:
    """Create a webhook for a channel."""
    return _api_post(f'/channels/{channel_id}/webhooks', {'name': name})


def send_webhook(webhook_url: str, message: str, embed_json: str = '') -> dict[str, Any]:
    """Send a message via a webhook URL."""
    data: dict[str, Any] = {'content': message}
    if embed_json:
        try:
            embed = json.loads(embed_json) if isinstance(embed_json, str) else embed_json
            data['embeds'] = [embed]
        except json.JSONDecodeError:
            pass
    try:
        resp = requests.post(webhook_url, json=data, timeout=15)
        return {'success': resp.status_code in (200, 204), 'status_code': resp.status_code}
    except Exception as e:
        return {'error': str(e)}


def bot_status() -> dict[str, Any]:
    """Check bot connection status."""
    token = os.environ.get('DISCORD_BOT_TOKEN', '')
    if not token:
        return {'error': 'DISCORD_BOT_TOKEN not set', 'connected': False}
    result = _api_get('/users/@me')
    if 'error' not in result:
        return {'connected': True, 'username': result.get('username', ''), 'id': result.get('id', '')}
    return {'connected': False, 'error': result.get('error', '')}


def execute_discord_operation(operation: str, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Execute a Discord operation and return (content_string, result_data)."""
    try:
        if operation == 'send_message':
            result = send_message(params.get('channel_id', ''), params.get('message', ''))
        elif operation == 'send_embed':
            result = send_embed(params.get('channel_id', ''), params.get('embed', '{}'))
        elif operation == 'get_messages':
            result = get_messages(params.get('channel_id', ''), params.get('limit', 50))
        elif operation == 'create_channel':
            result = create_channel(
                params.get('server_id', ''), params.get('channel_name', ''),
                params.get('channel_type', 'text'), params.get('channel_topic', '')
            )
        elif operation == 'list_channels':
            result = list_channels(params.get('server_id', ''))
        elif operation == 'get_server_info':
            result = get_server_info(params.get('server_id', ''))
        elif operation == 'list_members':
            result = list_members(params.get('server_id', ''), params.get('limit', 50))
        elif operation == 'create_webhook':
            result = create_webhook(params.get('channel_id', ''), 'OpenHands Bot')
        elif operation == 'send_webhook':
            result = send_webhook(params.get('webhook_url', ''), params.get('message', ''), params.get('embed', ''))
        elif operation == 'bot_status':
            result = bot_status()
        else:
            result = {'error': f'Unknown Discord operation: {operation}'}

        content = json.dumps(result, indent=2, default=str)
        return content, result if isinstance(result, dict) else {'data': result}

    except Exception as e:
        logger.error(f'Discord operation {operation} failed: {e}')
        error_result = {'error': str(e)}
        return json.dumps(error_result), error_result
