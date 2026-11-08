export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8011";

export class ApiError extends Error {
  code: string;
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = data.error || { code: "http_error", message: "请求没有完成" };
    throw new ApiError(error.code, error.message);
  }
  return data as T;
}

export async function apiForm<T>(path: string, body: FormData): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { method: "POST", body, credentials: "include" });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = data.error || { code: "http_error", message: "请求没有完成" };
    throw new ApiError(error.code, error.message);
  }
  return data as T;
}

export function wsUrl(callId: string): string {
  const base = API_BASE.replace(/^http/, "ws");
  return `${base}/api/v1/calls/${callId}/live`;
}
