// CODEIT shared TypeScript types — used by frontend services and components

export interface SkillItem {
  id: string
  name: string
  description: string
  content: string
  enabled: boolean
  created_at?: string
  updated_at?: string
}

export interface KnowledgeItem {
  id: string
  title: string
  content: string
  tags: string[]
  created_at?: string
  updated_at?: string
}

export interface PromptItem {
  id: string
  name: string
  content: string
  active: boolean
  created_at?: string
  updated_at?: string
}

export interface ConnectorItem {
  id: string
  name: string
  type: string
  icon: string
  status: string
  config: Record<string, string>
  created_at?: string
  updated_at?: string
}

export interface DeployJob {
  id: string
  target: string
  status: string
  logs: string
  config: Record<string, string>
  result: string
  error: string
  created_at?: string
  updated_at?: string
  finished_at?: string
}

export interface FileUpload {
  id: string
  original_name: string
  mime_type: string
  size_bytes: number
  conversation_id: string
  url: string
  created_at?: string
}

export interface AuthUser {
  user_id: number
  username: string
  display_name?: string
  role?: string
}

export interface AuthState {
  token: string | null
  user: AuthUser | null
  isAuthenticated: boolean
}
