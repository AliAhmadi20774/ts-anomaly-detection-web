type QueryValue = string | number | undefined;

interface ApiOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
  data?: unknown;
  params?: Record<string, QueryValue>;
  signal?: AbortSignal;
}

export class ApiError extends Error {
  constructor(public status: number, public details: unknown, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

function errorMessage(data: unknown, status: number): string {
  if (data && typeof data === 'object') {
    const fields = data as Record<string, unknown>;
    if (typeof fields.detail === 'string') return fields.detail;
    return Object.entries(fields)
      .map(([key, value]) => `${key.replaceAll('_', ' ')}: ${Array.isArray(value) ? value.join(' ') : String(value)}`)
      .join(' ') || `Request failed (HTTP ${status}).`;
  }
  return `Request failed (HTTP ${status}).`;
}

function csrfCookie(): string {
  const cookie = document.cookie.split(';').map((part) => part.trim())
    .find((part) => part.startsWith('csrftoken='));
  return cookie ? decodeURIComponent(cookie.slice('csrftoken='.length)) : '';
}

export async function apiRequest<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const { method = 'GET', data, params, signal } = options;
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params || {})) {
    if (value !== undefined && value !== '') query.set(key, String(value));
  }
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (data !== undefined) headers['Content-Type'] = 'application/json';
  if (method !== 'GET') headers['X-CSRFToken'] = csrfCookie();

  let response: Response;
  try {
    response = await fetch(`/backend/api${path}${query.size ? `?${query}` : ''}`, {
      method, headers, credentials: 'same-origin', mode: 'same-origin', cache: 'no-store',
      body: data === undefined ? undefined : JSON.stringify(data), signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError(0, undefined, 'Unable to reach the server. Please try again.');
  }
  if (response.status === 204) return undefined as T;
  const result: unknown = await response.json().catch(() => undefined);
  if (!response.ok) {
    const message = errorMessage(result, response.status);
    if (response.status === 403 && message === 'Authentication credentials were not provided.'
      && path !== '/auth/me/' && window.location.pathname !== '/user/login') {
      const redirect = window.location.pathname + window.location.search;
      window.location.assign(`/user/login?redirect=${encodeURIComponent(redirect)}`);
    }
    throw new ApiError(response.status, result, message);
  }
  return result as T;
}
