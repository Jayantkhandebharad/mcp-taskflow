// The only file that talks to the backend.
//
// Three jobs:
//   1. Attach the JWT to every request (PLAN.md §6, step 3).
//   2. Turn the backend's error bodies into one `ApiError` the pages can show.
//   3. Notice when the token has stopped working and log the user out.
//
// Everything else in `src/` calls the typed functions at the bottom and never
// touches `fetch` directly. That is what keeps "how we talk to the API" in one
// place when it inevitably changes (a refresh token, a different header, a
// proxy) — the pages don't know and don't care.

import type {
  Comment,
  Member,
  MemberRole,
  Project,
  Task,
  TaskCreate,
  TaskPatch,
  TaskStatus,
  User,
} from "./types";

// Comes from the repo-root `.env` (VITE_API_URL); see vite.config.ts. The
// browser calls the API directly, so this is a localhost URL, not the
// in-Compose `http://fastapi-backend:8000` the other services will use.
const API_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/** What a page catches. `status` lets it treat 403/404/409 differently. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// ── The token ────────────────────────────────────────────────────────────────
//
// Kept in memory (this variable) and mirrored to localStorage so a page reload
// doesn't log the user out. Anyone who can run JavaScript on this origin can
// read localStorage, which is the standard objection to storing a token
// there. For a learning app on localhost that is acceptable, and the
// alternative (an httpOnly cookie) would need CSRF protection on the backend
// and a different CORS setup — a whole post of its own. Said plainly, as
// PLAN.md §6 promised.

const TOKEN_KEY = "taskflow.token";
let token: string | null = localStorage.getItem(TOKEN_KEY);

export function setToken(value: string | null): void {
  token = value;
  if (value === null) localStorage.removeItem(TOKEN_KEY);
  else localStorage.setItem(TOKEN_KEY, value);
}

export function hasToken(): boolean {
  return token !== null;
}

// Called when a request that *carried* a token got a 401 back — the token
// expired (12 hours, JWT_EXPIRE_MINUTES) or the secret changed. The auth
// provider registers a handler that drops the user back to the login page.
// A plain variable, not React state, because this file must not know React.
let unauthorizedHandler: () => void = () => {};

export function onUnauthorized(handler: () => void): void {
  unauthorizedHandler = handler;
}

// ── The one request function ─────────────────────────────────────────────────

type Method = "GET" | "POST" | "PATCH" | "DELETE";

async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token !== null) headers["Authorization"] = `Bearer ${token}`;

  const response = await fetch(API_URL + path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  // DELETE routes answer 204 with no body; `response.json()` would throw.
  if (response.status === 204) return undefined as T;

  // A body we can't parse (a proxy's HTML error page, say) becomes `null`
  // and `errorMessage` falls back to the status code.
  const data: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    // Only a 401 on a request that *had* a token means "your session is
    // over". A 401 from POST /auth/login with a wrong password is a
    // different thing — it's the answer to the question, not a sign that
    // anything expired — and must not bounce the user around.
    if (response.status === 401 && token !== null) {
      setToken(null);
      unauthorizedHandler();
    }
    throw new ApiError(response.status, errorMessage(response.status, data));
  }
  return data as T;
}

/**
 * Pull a sentence out of a FastAPI error body.
 *
 * Two shapes exist (docs/briefs/phase-3.md, "one status per body shape"):
 *   - `{"detail": "Only an admin of project 'WEB' can do this"}` for 401,
 *     403, 404 and 409 — a sentence written to be shown to a person.
 *   - `{"detail": [{"loc": ["body", "email"], "msg": "...", ...}, ...]}` for
 *     422 — pydantic's list of what was wrong with the request.
 */
function errorMessage(status: number, data: unknown): string {
  if (typeof data === "object" && data !== null && "detail" in data) {
    const detail = (data as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item: { loc?: unknown[]; msg?: string }) => {
          const field = item.loc?.slice(1).join(".") ?? "";
          return field ? `${field}: ${item.msg}` : (item.msg ?? "invalid");
        })
        .join("; ");
    }
  }
  return `Request failed (HTTP ${status})`;
}

/** Build a query string, leaving out anything undefined. */
function query(params: Record<string, string | boolean | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== false) search.set(key, String(value));
  }
  const s = search.toString();
  return s ? `?${s}` : "";
}

// ── The typed surface — one function per route in PLAN.md §7 ─────────────────

// A `type`, not an `interface`, on purpose: TypeScript lets an object
// *type* satisfy `Record<string, ...>` (it infers an index signature) but
// refuses the same for an `interface`. `query()` below wants the Record.
export type TaskFilters = {
  status?: TaskStatus;
  assignee_id?: string;
  overdue?: boolean;
};

export const api = {
  // auth
  register: (email: string, full_name: string, password: string) =>
    request<User>("POST", "/auth/register", { email, full_name, password }),
  login: (email: string, password: string) =>
    request<{ access_token: string; token_type: string }>("POST", "/auth/login", {
      email,
      password,
    }),
  me: () => request<User>("GET", "/auth/me"),

  // projects + members
  listProjects: () => request<Project[]>("GET", "/projects"),
  createProject: (key: string, name: string, description: string | null) =>
    request<Project>("POST", "/projects", { key, name, description }),
  getProject: (key: string) => request<Project>("GET", `/projects/${key}`),
  listMembers: (key: string) => request<Member[]>("GET", `/projects/${key}/members`),
  addMember: (key: string, email: string, role: MemberRole) =>
    request<Member>("POST", `/projects/${key}/members`, { email, role }),
  removeMember: (key: string, userId: string) =>
    request<void>("DELETE", `/projects/${key}/members/${userId}`),

  // tasks
  listTasks: (key: string, filters: TaskFilters = {}) =>
    request<Task[]>("GET", `/projects/${key}/tasks${query(filters)}`),
  createTask: (key: string, body: TaskCreate) =>
    request<Task>("POST", `/projects/${key}/tasks`, body),
  getTask: (ref: string) => request<Task>("GET", `/tasks/${ref}`),
  // Send only the fields you mean to change. `undefined` keys vanish in
  // JSON.stringify; `null` keys survive and mean "clear this". See TaskPatch.
  patchTask: (ref: string, patch: TaskPatch) => request<Task>("PATCH", `/tasks/${ref}`, patch),
  deleteTask: (ref: string) => request<void>("DELETE", `/tasks/${ref}`),

  // comments
  listComments: (ref: string) => request<Comment[]>("GET", `/tasks/${ref}/comments`),
  addComment: (ref: string, body: string) =>
    request<Comment>("POST", `/tasks/${ref}/comments`, { body }),

  // me
  myTasks: () => request<Task[]>("GET", "/me/tasks"),
};
