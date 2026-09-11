// Small presentational pieces shared by more than one page. No logic here.
import type { ReactNode } from "react";

import { PRIORITY_CLASS, PRIORITY_LABEL } from "../labels";
import type { MemberRole, TaskPriority } from "../types";

/** A backend error, shown where it happened. `null` renders nothing. */
export function ErrorMessage({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
      {message}
    </p>
  );
}

export function Loading() {
  return <p className="text-sm text-slate-500">Loading…</p>;
}

export function PriorityBadge({ priority }: { priority: TaskPriority }) {
  return (
    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${PRIORITY_CLASS[priority]}`}>
      {PRIORITY_LABEL[priority]}
    </span>
  );
}

export function RoleBadge({ role }: { role: MemberRole }) {
  const cls = role === "admin" ? "bg-indigo-100 text-indigo-800" : "bg-slate-100 text-slate-700";
  return <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${cls}`}>{role}</span>;
}

/** Consistent form controls without a component library. */
export const inputClass =
  "w-full rounded border border-slate-300 px-2 py-1.5 text-sm focus:border-indigo-500 focus:outline-none";

export const buttonClass =
  "rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50";

export const secondaryButtonClass =
  "rounded border border-slate-300 bg-white px-3 py-1.5 text-sm hover:bg-slate-100 disabled:opacity-50";

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium text-slate-700">{label}</span>
      {children}
    </label>
  );
}
