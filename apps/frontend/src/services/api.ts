const API_BASE = '/api'

export interface ApiFetchOptions extends RequestInit {
  headers?: Record<string, string>
}

export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T | null> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) },
  })

  if (!response.ok) {
    let detail: string = response.statusText
    try {
      const body = (await response.json()) as { detail?: string }
      detail = body.detail ?? JSON.stringify(body)
    } catch {
      try {
        detail = await response.text()
      } catch {
        // empty/unparseable body — keep statusText
      }
    }
    throw new Error(`${response.status} ${response.statusText}: ${detail}`)
  }

  if (response.status === 204) {
    return null
  }

  return (await response.json()) as T
}
