// Display names and ordering for the enums. The values are the backend's
// (app/models/enums.py); only the labels are ours.

import type { TaskPriority, TaskStatus } from "./types";

/** Board columns, left to right. */
export const STATUSES: TaskStatus[] = ["todo", "in_progress", "in_review", "done"];

export const STATUS_LABEL: Record<TaskStatus, string> = {
  todo: "To do",
  in_progress: "In progress",
  in_review: "In review",
  done: "Done",
};

export const PRIORITIES: TaskPriority[] = ["low", "medium", "high"];

export const PRIORITY_LABEL: Record<TaskPriority, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
};

/** Tailwind classes for a priority badge. */
export const PRIORITY_CLASS: Record<TaskPriority, string> = {
  low: "bg-slate-100 text-slate-700",
  medium: "bg-amber-100 text-amber-800",
  high: "bg-red-100 text-red-800",
};

/** Today as "YYYY-MM-DD" in the browser's timezone, to compare with due_date. */
export function today(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** "Past due and not done" — the backend's definition of overdue. */
export function isOverdue(dueDate: string | null, status: TaskStatus): boolean {
  return dueDate !== null && status !== "done" && dueDate < today();
}

/** An ISO timestamp from the API as a short local date-time. */
export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
