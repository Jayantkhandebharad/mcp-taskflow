// The shapes the backend sends and accepts, as TypeScript types.
//
// These mirror the Pydantic classes in `fastapi-backend/app/schemas/` field
// for field, and they keep the backend's snake_case names on purpose. The
// repo convention is camelCase for TypeScript *identifiers* — variables,
// functions, components — but these are descriptions of JSON we don't own.
// Renaming `full_name` to `fullName` here would mean a translation layer
// between the reader and what they see in the network tab or on /docs,
// and that layer is exactly where "it works in curl but not in the app"
// bugs live.
//
// Nothing checks these against the backend. If a Pydantic schema changes and
// this file doesn't, the type checker will happily lie. That's the trade you
// make when you skip an OpenAPI code generator; it's fine at this size.

export type TaskStatus = "todo" | "in_progress" | "in_review" | "done";
export type TaskPriority = "low" | "medium" | "high";
export type MemberRole = "admin" | "member";

/** `UserOut` — what `/auth/me` and `/auth/register` return. */
export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  created_at: string;
}

/** `UserRef` — a person seen from another object (assignee, comment author). */
export interface UserRef {
  id: string;
  email: string;
  full_name: string;
}

/** `ProjectOut`. `my_role` is the caller's row in project_members. */
export interface Project {
  id: string;
  key: string;
  name: string;
  description: string | null;
  created_by: string;
  created_at: string;
  my_role: MemberRole;
}

/** `MemberOut` — one row of a project's members list. */
export interface Member {
  user_id: string;
  email: string;
  full_name: string;
  role: MemberRole;
  added_at: string;
}

/** `TaskOut`. `ref` is "WEB-14"; `due_date` is a plain "YYYY-MM-DD". */
export interface Task {
  id: string;
  ref: string;
  project_key: string;
  number: number;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  assignee: UserRef | null;
  created_by: string;
  due_date: string | null;
  created_at: string;
  updated_at: string;
}

/** `TaskCreate` — the body of POST /projects/{key}/tasks. */
export interface TaskCreate {
  title: string;
  description?: string | null;
  status?: TaskStatus;
  priority?: TaskPriority;
  assignee_id?: string | null;
  due_date?: string | null;
}

/**
 * `TaskPatch` — the body of PATCH /tasks/{ref}. Every field optional.
 *
 * The backend distinguishes "left out" (don't touch) from "sent null"
 * (clear it). `JSON.stringify` does the same: a key whose value is
 * `undefined` is dropped from the output, a key whose value is `null` is
 * kept. So this type maps onto the wire exactly — see `api.patchTask`.
 */
export interface TaskPatch {
  title?: string;
  description?: string | null;
  status?: TaskStatus;
  priority?: TaskPriority;
  assignee_id?: string | null;
  due_date?: string | null;
}

/** `CommentOut`. */
export interface Comment {
  id: string;
  author: UserRef;
  body: string;
  created_at: string;
}
