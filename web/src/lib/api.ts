import type { Atlas, Entry, Graph, Meta, Month, Privacy, SearchResult, SeedStatus } from './types'

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, { cache: 'no-store', ...init })
  } catch {
    throw new ApiError(0, 'The Dreamlog service is not reachable.')
  }
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body: unknown = await response.json()
      if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string') detail = body.detail
    } catch {
      // not JSON: keep the status text
    }
    throw new ApiError(response.status, detail)
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T)
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  meta: () => request<Meta>('/meta'),
  health: () => request<{ status: string; models_ready: boolean }>('/health'),
  entries: (symbol?: number) => request<Entry[]>(symbol === undefined ? '/entries' : `/entries?symbol=${symbol}`),
  entry: (id: string) => request<Entry>(`/entries/${id}`),
  createFromText: (text: string) => request<Entry>('/entries', json('POST', { text })),
  createFromAudio: (blob: Blob, filename: string) => {
    const form = new FormData()
    form.append('file', blob, filename)
    return request<Entry>('/entries/audio', { method: 'POST', body: form })
  },
  update: (id: string, text: string) => request<Entry>(`/entries/${id}`, json('PUT', { text })),
  remove: (id: string) => request<void>(`/entries/${id}`, { method: 'DELETE' }),
  graph: () => request<Graph>('/graph'),
  search: (query: string) => request<SearchResult>(`/search?q=${encodeURIComponent(query)}`),
  months: () => request<Month[]>('/months'),
  atlas: (month: string) => request<Atlas>(`/atlas/${month}`),
  privacy: () => request<Privacy>('/privacy'),
  deleteAll: () => request<{ entries: number; files: number }>('/all?confirm=delete-everything', { method: 'DELETE' }),
  loadSamples: () => request<SeedStatus>('/fixtures/load', { method: 'POST' }),
  sampleStatus: () => request<SeedStatus>('/fixtures/status'),
}
