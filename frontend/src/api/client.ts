export type ApiError = {
  message: string
  status: number
}

const API_BASE = import.meta.env.VITE_API_BASE || ''

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = sessionStorage.getItem('zc_token')
  const headers = new Headers(options.headers)
  if (!headers.has('Content-Type') && options.body && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers })
  const contentType = response.headers.get('content-type') || ''
  const body = contentType.includes('application/json') ? await response.json() : await response.text()
  if (!response.ok) {
    const message = typeof body === 'object' && body?.message ? body.message : response.statusText
    throw { message, status: response.status } satisfies ApiError
  }
  return body as T
}

export function postJson<T>(path: string, data: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function postForm<T>(path: string, data: FormData): Promise<T> {
  return apiFetch<T>(path, {
    method: 'POST',
    body: data,
  })
}
