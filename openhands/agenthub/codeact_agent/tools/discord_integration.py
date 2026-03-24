"""Discord Integration tool for the CodeAct Agent.

Provides the agent with Discord capabilities: manage bots, send messages,
create channels, manage webhooks, and interact with Discord servers.
Uses the Discord REST API via requests.
"""

from litellm import ChatCompletionToolParam, ChatCompletionToolParamFunctionChunk

_DISCORD_DESCRIPTION = """Interact with Discord to manage bots, send messages, create channels, and manage webhooks.

### Available Operations:

**Messaging:**
1. **send_message** - Send a message to a Discord channel.
2. **send_embed** - Send a rich embed message to a channel.
3. **send_file** - Upload and send a file to a channel.
4. **get_messages** - Get recent messages from a channel.

**Channel Management:**
5. **create_channel** - Create a new text or voice channel in a server.
6. **list_channels** - List all channels in a server.
7. **delete_channel** - Delete a channel from a server.
8. **edit_channel** - Edit a channel's name, topic, or permissions.

**Webhook Management:**
9. **create_webhook** - Create a webhook for a channel.
10. **send_webhook** - Send a message via a webhook URL.
11. **list_webhooks** - List webhooks for a channel or server.
12. **delete_webhook** - Delete a webhook.

**Server Management:**
13. **get_server_info** - Get information about a Discord server (guild).
14. **list_members** - List members of a server.
15. **list_roles** - List roles in a server.
16. **create_role** - Create a new role in a server.

**Bot Management:**
17. **bot_status** - Check the bot's connection status and info.
18. **set_bot_activity** - Set the bot's activity/status message.

### Authentication:
- Set DISCORD_BOT_TOKEN environment variable for bot operations.
- Set DISCORD_WEBHOOK_URL for webhook-only operations (no bot token needed).

### Usage Notes:
- Channel and server IDs are required for most operations (numeric IDs).
- Webhook URLs can be used for simple message sending without a bot token.
- Embeds support rich formatting: title, description, color, fields, images, footer.
- Rate limits are handled automatically with retry logic.
"""

DiscordTool = ChatCompletionToolParam(
    type='function',
    function=ChatCompletionToolParamFunctionChunk(
        name='discord',
        description=_DISCORD_DESCRIPTION,
        parameters={
            'type': 'object',
            'properties': {
                'operation': {
                    'type': 'string',
                    'description': 'The Discord operation to perform.',
                    'enum': [
                        'send_message',
                        'send_embed',
                        'send_file',
                        'get_messages',
                        'create_channel',
                        'list_channels',
                        'delete_channel',
                        'edit_channel',
                        'create_webhook',
                        'send_webhook',
                        'list_webhooks',
                        'delete_webhook',
                        'get_server_info',
                        'list_members',
                        'list_roles',
                        'create_role',
                        'bot_status',
                        'set_bot_activity',
                    ],
                },
                'server_id': {
                    'type': 'string',
                    'description': 'Discord server (guild) ID.',
                },
                'channel_id': {
                    'type': 'string',
                    'description': 'Discord channel ID.',
                },
                'message': {
                    'type': 'string',
                    'description': 'Message content to send.',
                },
                'webhook_url': {
                    'type': 'string',
                    'description': 'Webhook URL for webhook operations.',
                },
                'embed': {
                    'type': 'string',
                    'description': 'Embed data as JSON string with fields: title, description, color, fields, image, footer.',
                },
                'channel_name': {
                    'type': 'string',
                    'description': 'Name for new channel (create_channel) or edited channel.',
                },
                'channel_type': {
                    'type': 'string',
                    'description': 'Type of channel to create.',
                    'enum': ['text', 'voice', 'category', 'announcement'],
                },
                'channel_topic': {
                    'type': 'string',
                    'description': 'Topic/description for a text channel.',
                },
                'file_path': {
                    'type': 'string',
                    'description': 'Local file path to upload (send_file operation).',
                },
                'role_name': {
                    'type': 'string',
                    'description': 'Name for a new role (create_role operation).',
                },
                'role_color': {
                    'type': 'string',
                    'description': 'Hex color for a role (e.g., "#FF5733").',
                },
                'activity': {
                    'type': 'string',
                    'description': 'Bot activity/status text (set_bot_activity operation).',
                },
                'limit': {
                    'type': 'number',
                    'description': 'Number of items to return (for list operations). Default: 50.',
                },
                'webhook_id': {
                    'type': 'string',
                    'description': 'Webhook ID for delete_webhook operation.',
                },
            },
            'required': ['operation'],
        },
    ),
)
