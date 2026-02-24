/**
 * Flask API client — handles all calls to the Python backend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001/api'

interface FetchOptions extends RequestInit {
  token?: string
}

async function apiFetch<T = unknown>(path: string, options: FetchOptions = {}): Promise<T> {
  const { token, ...fetchOptions } = options

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((fetchOptions.headers as Record<string, string>) || {}),
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...fetchOptions,
    headers,
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ error: res.statusText }))
    throw new Error(error.error || `API error: ${res.status}`)
  }

  return res.json()
}

// Projects
export const api = {
  projects: {
    list: (token: string) =>
      apiFetch<Project[]>('/projects', { token }),
    get: (id: string, token: string) =>
      apiFetch<ProjectDetail>(`/projects/${id}`, { token }),
    create: (data: CreateProjectData, token: string) =>
      apiFetch<Project>('/projects', { method: 'POST', body: JSON.stringify(data), token }),
    update: (id: string, data: Partial<Project>, token: string) =>
      apiFetch<Project>(`/projects/${id}`, { method: 'PUT', body: JSON.stringify(data), token }),
    delete: (id: string, token: string) =>
      apiFetch(`/projects/${id}`, { method: 'DELETE', token }),
  },

  documents: {
    list: (projectId: string, token: string) =>
      apiFetch<Document[]>(`/projects/${projectId}/documents`, { token }),
    upload: async (projectId: string, files: File[], token: string) => {
      const formData = new FormData()
      files.forEach(f => formData.append('files', f))
      const res = await fetch(`${API_BASE}/projects/${projectId}/documents/upload`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      })
      if (!res.ok) throw new Error('Upload failed')
      return res.json()
    },
    delete: (projectId: string, docId: string, token: string) =>
      apiFetch(`/projects/${projectId}/documents/${docId}`, { method: 'DELETE', token }),
  },

  processing: {
    start: (projectId: string, token: string, full = false) =>
      apiFetch<{ job_id: string }>(`/projects/${projectId}/process${full ? '?full=true' : ''}`, {
        method: 'POST', token
      }),
    jobStatus: (jobId: string, token: string) =>
      apiFetch<ProcessingJob>(`/jobs/${jobId}`, { token }),
    activeJob: (projectId: string, token: string) =>
      apiFetch<{ active: boolean; job?: ProcessingJob }>(`/projects/${projectId}/process/active`, { token }),
  },

  graph: {
    get: (projectId: string, token: string) =>
      apiFetch<GraphData>(`/projects/${projectId}/graph`, { token }),
    stats: (projectId: string, token: string) =>
      apiFetch(`/projects/${projectId}/graph/stats`, { token }),
    updateNode: (projectId: string, nodeId: string, data: Record<string, unknown>, token: string) =>
      apiFetch(`/projects/${projectId}/nodes/${nodeId}`, { method: 'PUT', body: JSON.stringify(data), token }),
  },

  todos: {
    list: (projectId: string, token: string) =>
      apiFetch<TodoResponse>(`/projects/${projectId}/todos`, { token }),
    critical: (projectId: string, token: string) =>
      apiFetch(`/projects/${projectId}/todos/critical`, { token }),
    complete: (projectId: string, nodeId: string, token: string) =>
      apiFetch(`/projects/${projectId}/todos/${nodeId}/complete`, { method: 'PUT', token }),
    setStatus: (projectId: string, nodeId: string, status: string, token: string) =>
      apiFetch(`/projects/${projectId}/todos/${nodeId}/status`, {
        method: 'PUT', body: JSON.stringify({ status }), token
      }),
    export: (projectId: string, token: string) =>
      apiFetch<{ markdown: string }>(`/projects/${projectId}/todos/export`, { token }),
  },
}

// Types
export interface Project {
  id: string
  name: string
  description: string
  tender_number: string
  status: string
  deadline: string | null
  created_at: string
  updated_at: string
}

export interface ProjectDetail extends Project {
  stats: {
    total_nodes: number
    completed: number
    completion_pct: number
    by_type: Record<string, number>
  }
}

export interface CreateProjectData {
  name: string
  description?: string
  tender_number?: string
  deadline?: string
}

export interface Document {
  id: string
  filename: string
  file_type: string
  file_size: number
  created_at: string
}

export interface GraphNode {
  id: string
  type: string
  title: string
  description: string
  status: string
  source_text: string
  confidence: number
  tags: string[]
  document_id: string | null
  documents: { filename: string } | null
}

export interface GraphEdge {
  id: string
  source_node_id: string
  target_node_id: string
  type: string
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  total_nodes: number
  total_edges: number
}

export interface ProcessingJob {
  id: string
  status: string
  progress: number
  current_step: string
  total_documents: number
  processed_documents: number
  error_message: string | null
}

export interface TodoResponse {
  categories: TodoCategory[]
  summary: Record<string, unknown>
}

export interface TodoCategory {
  name: string
  items: TodoItem[]
}

export interface TodoItem {
  id: string
  title: string
  description: string
  priority: string
  status: string
  source_document: string
}
