/**
 * CODEIT Backend API service — replaces localStorage with real backend persistence.
 * All custom feature CRUD goes through these functions.
 */

const BACKEND_URL = (import.meta.env.VITE_BACKEND_URL || '').replace(/\/+$/, '')

// ─── Auth Token Management ──────────────────────────────────────────────────

let _authToken: string | null = localStorage.getItem('codeit_auth_token')

export function getAuthToken(): string | null {
  return _authToken
}

export function setAuthToken(token: string | null): void {
  _authToken = token
  if (token) {
    localStorage.setItem('codeit_auth_token', token)
  } else {
    localStorage.removeItem('codeit_auth_token')
  }
}

function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  }
  if (_authToken) {
    headers['Authorization'] = `Bearer ${_authToken}`
  }
  return headers
}

// ─── Generic fetch helpers ──────────────────────────────────────────────────

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${BACKEND_URL}${path}`
  const res = await fetch(url, {
    ...options,
    headers: { ...authHeaders(), ...options.headers as Record<string, string> },
  })
  if (res.status === 401) {
    // Token expired or invalid — clear auth
    setAuthToken(null)
    throw new Error('Authentication required')
  }
  if (!res.ok) {
    const body = await res.text()
    let msg = `${res.status}`
    try { msg = JSON.parse(body).error || msg } catch { msg = body || msg }
    throw new Error(msg)
  }
  return res.json()
}

async function apiGet<T>(path: string): Promise<T> {
  return apiFetch<T>(path, { method: 'GET' })
}

async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: 'POST',
    body: body ? JSON.stringify(body) : undefined,
  })
}

async function apiPut<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: 'PUT',
    body: JSON.stringify(body),
  })
}

async function apiDelete<T>(path: string): Promise<T> {
  return apiFetch<T>(path, { method: 'DELETE' })
}

// ─── Auth API ───────────────────────────────────────────────────────────────

export interface LoginResponse {
  token: string
  user_id: number
  username: string
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  const res = await apiPost<LoginResponse>('/api/codeit/auth/login', { username, password })
  setAuthToken(res.token)
  return res
}

export async function register(username: string, password: string, display_name?: string): Promise<LoginResponse> {
  const res = await apiPost<LoginResponse>('/api/codeit/auth/register', { username, password, display_name })
  setAuthToken(res.token)
  return res
}

export async function validateToken(): Promise<{ valid: boolean; user_id?: number; username?: string }> {
  try {
    return await apiPost('/api/codeit/auth/validate')
  } catch {
    return { valid: false }
  }
}

export async function getMe(): Promise<{ user_id: number; username: string; display_name: string; role: string }> {
  return apiGet('/api/codeit/auth/me')
}

export function logout(): void {
  setAuthToken(null)
}

// ─── Skills API ─────────────────────────────────────────────────────────────

import type { SkillItem, KnowledgeItem, PromptItem, ConnectorItem, DeployJob, FileUpload } from '../types/codeit'

export async function listSkills(): Promise<SkillItem[]> {
  const res = await apiGet<{ items: SkillItem[] }>('/api/codeit/skills')
  return res.items
}

export async function createSkill(skill: { name: string; description?: string; content?: string; enabled?: boolean }): Promise<SkillItem> {
  return apiPost('/api/codeit/skills', skill)
}

export async function updateSkill(id: string, updates: Partial<SkillItem>): Promise<SkillItem> {
  return apiPut(`/api/codeit/skills/${id}`, updates)
}

export async function deleteSkill(id: string): Promise<void> {
  await apiDelete(`/api/codeit/skills/${id}`)
}

// ─── Knowledge API ──────────────────────────────────────────────────────────

export async function listKnowledge(q?: string): Promise<KnowledgeItem[]> {
  const query = q ? `?q=${encodeURIComponent(q)}` : ''
  const res = await apiGet<{ items: KnowledgeItem[] }>(`/api/codeit/knowledge${query}`)
  return res.items
}

export async function createKnowledge(item: { title: string; content?: string; tags?: string[] }): Promise<KnowledgeItem> {
  return apiPost('/api/codeit/knowledge', item)
}

export async function updateKnowledge(id: string, updates: Partial<KnowledgeItem>): Promise<KnowledgeItem> {
  return apiPut(`/api/codeit/knowledge/${id}`, updates)
}

export async function deleteKnowledge(id: string): Promise<void> {
  await apiDelete(`/api/codeit/knowledge/${id}`)
}

// ─── Prompts API ────────────────────────────────────────────────────────────

export async function listPrompts(): Promise<PromptItem[]> {
  const res = await apiGet<{ items: PromptItem[] }>('/api/codeit/prompts')
  return res.items
}

export async function createPrompt(prompt: { name: string; content?: string; active?: boolean }): Promise<PromptItem> {
  return apiPost('/api/codeit/prompts', prompt)
}

export async function updatePrompt(id: string, updates: Partial<PromptItem>): Promise<PromptItem> {
  return apiPut(`/api/codeit/prompts/${id}`, updates)
}

export async function activatePrompt(id: string): Promise<void> {
  await apiPost(`/api/codeit/prompts/${id}/activate`)
}

export async function deletePrompt(id: string): Promise<void> {
  await apiDelete(`/api/codeit/prompts/${id}`)
}

// ─── Connectors API ─────────────────────────────────────────────────────────

export async function listConnectors(): Promise<ConnectorItem[]> {
  const res = await apiGet<{ items: ConnectorItem[] }>('/api/codeit/connectors')
  return res.items
}

export async function createConnector(connector: { name: string; type: string; icon?: string; config?: Record<string, string> }): Promise<ConnectorItem> {
  return apiPost('/api/codeit/connectors', connector)
}

export async function updateConnector(id: string, updates: Partial<ConnectorItem>): Promise<ConnectorItem> {
  return apiPut(`/api/codeit/connectors/${id}`, updates)
}

export async function disconnectConnector(id: string): Promise<void> {
  await apiPost(`/api/codeit/connectors/${id}/disconnect`)
}

export async function deleteConnector(id: string): Promise<void> {
  await apiDelete(`/api/codeit/connectors/${id}`)
}

// ─── Deploy API ─────────────────────────────────────────────────────────────

export async function listDeployJobs(): Promise<DeployJob[]> {
  const res = await apiGet<{ items: DeployJob[] }>('/api/codeit/deploy/jobs')
  return res.items
}

export async function createDeployJob(target: string, config?: Record<string, string>): Promise<DeployJob> {
  return apiPost('/api/codeit/deploy/jobs', { target, config })
}

export async function getDeployJob(id: string): Promise<DeployJob> {
  return apiGet(`/api/codeit/deploy/jobs/${id}`)
}

export async function getDeployLogs(id: string): Promise<{ logs: string; status: string }> {
  return apiGet(`/api/codeit/deploy/jobs/${id}/logs`)
}

// ─── File Upload API ────────────────────────────────────────────────────────

export async function uploadFile(file: File, conversationId?: string): Promise<FileUpload> {
  const formData = new FormData()
  formData.append('file', file)
  if (conversationId) {
    formData.append('conversation_id', conversationId)
  }

  const url = `${BACKEND_URL}/api/codeit/uploads`
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      ..._authToken ? { 'Authorization': `Bearer ${_authToken}` } : {},
    },
    body: formData,
  })

  if (res.status === 401) {
    setAuthToken(null)
    throw new Error('Authentication required')
  }
  if (!res.ok) {
    const body = await res.text()
    let msg = `${res.status}`
    try { msg = JSON.parse(body).error || msg } catch { msg = body || msg }
    throw new Error(msg)
  }
  return res.json()
}

export async function listUploads(conversationId?: string): Promise<FileUpload[]> {
  const query = conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : ''
  const res = await apiGet<{ items: FileUpload[] }>(`/api/codeit/uploads${query}`)
  return res.items
}

export async function deleteUpload(id: string): Promise<void> {
  await apiDelete(`/api/codeit/uploads/${id}`)
}

// ─── Health API ─────────────────────────────────────────────────────────────

export async function getCodeitHealth(): Promise<{ status: string; checks: Record<string, unknown> }> {
  return apiGet('/api/codeit/health')
}

export async function getCodeitStats(): Promise<{ stats: Record<string, number> }> {
  return apiGet('/api/codeit/stats')
}
