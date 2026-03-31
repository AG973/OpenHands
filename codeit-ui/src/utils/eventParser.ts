export interface ChatMessage { id: number; role: 'user' | 'assistant' | 'system'; content: string; timestamp: string }
export interface AgentAction { id: number; type: 'command' | 'file_write' | 'file_edit' | 'browse' | 'think' | 'task' | 'other'; title: string; detail: string; status: 'running' | 'done' | 'error' }
export interface ConversationMeta { conversation_id: string; title: string; created_at: string; status: string }

export type SidebarView = 'chat' | 'skills' | 'knowledge' | 'prompts' | 'connectors' | 'deploy' | 'logs'

export function parseEvent(evt: Record<string, unknown>): { message?: ChatMessage; action?: AgentAction } {
  const id = Number(evt.id) || Date.now()
  const source = evt.source as string
  const timestamp = (evt.timestamp as string) || new Date().toISOString()
  if (source === 'user' && (evt.type === 'message' || evt.action === 'message')) {
    const args = evt.args as Record<string, string> | undefined
    return { message: { id, role: 'user', content: args?.content || evt.message as string || '', timestamp } }
  }
  if (source === 'agent' && (evt.type === 'message' || evt.action === 'message')) {
    const args = evt.args as Record<string, string> | undefined
    return { message: { id, role: 'assistant', content: args?.content || evt.message as string || '', timestamp } }
  }
  if (evt.action === 'run') {
    const args = evt.args as Record<string, string> | undefined
    return { action: { id, type: 'command', title: 'Run command', detail: args?.command || '', status: 'running' } }
  }
  if (evt.observation === 'run') {
    const content = evt.content as string || ''
    return { action: { id, type: 'command', title: 'Command output', detail: content.slice(0, 500), status: (evt.extras as Record<string, number>)?.exit_code === 0 ? 'done' : 'error' } }
  }
  if (evt.action === 'write') {
    const args = evt.args as Record<string, string> | undefined
    return { action: { id, type: 'file_write', title: `Create ${args?.path?.split('/').pop() || 'file'}`, detail: args?.path || '', status: 'running' } }
  }
  if (evt.action === 'edit') {
    const args = evt.args as Record<string, string> | undefined
    return { action: { id, type: 'file_edit', title: `Edit ${args?.path?.split('/').pop() || 'file'}`, detail: args?.path || '', status: 'running' } }
  }
  if (evt.observation === 'agent_state_changed') {
    const extras = evt.extras as Record<string, string> | undefined
    if (extras?.agent_state === 'error') return { message: { id, role: 'system', content: `Agent error: ${extras?.reason || 'Unknown'}`, timestamp } }
  }
  if (evt.type === 'status') return { action: { id, type: 'task', title: 'Status', detail: evt.message as string || '', status: 'done' } }
  return {}
}
