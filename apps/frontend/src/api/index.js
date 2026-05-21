const API_BASE = '/api'

export async function apiFetch(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = body.detail || JSON.stringify(body)
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

  return response.json()
}
