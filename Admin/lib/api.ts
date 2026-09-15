/**
 * Thin client for the shared Gawacha Bazaar FastAPI backend - the same
 * backend the website and mobile app talk to. The admin panel has no
 * business logic of its own: every mutation here is a direct call to an
 * existing (or, as each phase is built, newly added) backend endpoint, and
 * every authorization decision is re-checked server-side regardless of
 * what this client sends.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export interface UserProfile {
  id: number;
  name: string;
  email: string;
  phone: string;
  status: string;
  created_at: string;
  roles: string[];
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface LoginResponse extends TokenPair {
  user: UserProfile;
}

export class ApiError extends Error {
  code: string;
  status: number;
  details: unknown;

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function parseErrorResponse(response: Response): Promise<ApiError> {
  try {
    const body = await response.json();
    return new ApiError(
      response.status,
      body.code ?? "UNKNOWN_ERROR",
      body.message ?? "Something went wrong. Please try again.",
      body.details,
    );
  } catch {
    return new ApiError(response.status, "UNKNOWN_ERROR", "Something went wrong. Please try again.");
  }
}

export async function login(identifier: string, password: string): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ identifier, password }),
  });
  if (!response.ok) throw await parseErrorResponse(response);
  return response.json();
}

export async function refreshSession(refreshToken: string): Promise<TokenPair> {
  const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) throw await parseErrorResponse(response);
  return response.json();
}

export async function fetchMe(accessToken: string): Promise<UserProfile> {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!response.ok) throw await parseErrorResponse(response);
  return response.json();
}

export async function logout(refreshToken: string): Promise<void> {
  await fetch(`${API_BASE_URL}/auth/logout`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  }).catch(() => undefined);
}

/**
 * Authenticated fetch used by every admin module. Attaches the bearer
 * token; the caller is responsible for handling a 401 by triggering a
 * refresh (see `lib/auth-context.tsx`) since only that context holds the
 * refresh token.
 */
export async function apiFetch(
  path: string,
  accessToken: string,
  init: RequestInit = {},
): Promise<Response> {
  return fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      Authorization: `Bearer ${accessToken}`,
      ...init.headers,
    },
  });
}

export { API_BASE_URL };
