export type ApiErrorBody = { code: string; message: string; details: Record<string, unknown> };

function csrfCookie(): string | undefined {
  const match = document.cookie.match(/(?:^|; )invoice_csrf=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : undefined;
}

export function setCsrfToken(value: string): void {
  // Retained as an explicit override for tests that obtain a session bootstrap token.
  document.cookie = `invoice_csrf=${encodeURIComponent(value)}; path=/; SameSite=Lax; Secure`;
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData) && init.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  const csrf = csrfCookie() ?? (typeof __PROTOTYPE_MODE__ !== "undefined" && __PROTOTYPE_MODE__ ? "prototype-csrf-token" : undefined);
  if (init.method && !["GET", "HEAD", "OPTIONS"].includes(init.method.toUpperCase()) && csrf) {
    headers.set("X-CSRF-Token", csrf);
  }
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, { ...init, headers, credentials: "same-origin" });
  } catch {
    throw new Error("Could not reach the invoice server. Keep ./run.sh running and open the app from VS Code's forwarded port 5173.");
  }
  if (!response.ok) {
    const error = (await response.json().catch(() => ({ message: "Request failed." }))) as Partial<ApiErrorBody>;
    throw new Error(error.message ?? `Request failed (${response.status}).`);
  }
  return (await response.json()) as T;
}
