export type User = { id: number; username: string; email: string; role: 'operator' | 'manager' }
export type Product = { id: number; name: string; category: string; price: number; status: string; image_url: string; summary: string; inventory: number; warning_threshold: number; inventory_warning: boolean }
export type Task = { id: number; product_id: number; kind: string; title: string; status: string; progress: number; provider_mode: string; error_message?: string; retryable?: boolean; result_url?: string }

const TOKEN_KEY = 'ecommerce_ops_token'
export const auth = {
  get token() { return localStorage.getItem(TOKEN_KEY) || '' },
  set token(value: string) { value ? localStorage.setItem(TOKEN_KEY, value) : localStorage.removeItem(TOKEN_KEY) },
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (!(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  if (auth.token) headers.set('Authorization', `Bearer ${auth.token}`)
  const response = await fetch(path, { ...options, headers })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body.detail || `请求失败 ${response.status}`)
  return body as T
}
