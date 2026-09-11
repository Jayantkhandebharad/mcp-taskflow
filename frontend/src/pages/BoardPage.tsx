// Screen 3: one project's tasks in four columns, one per status. Moving a
// task is a <select> on its card that PATCHes `status` — no drag and drop,
// which would be a library or a week, and teaches nothing about the API.
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { api, type TaskFilters } from "../api";
import { useAuth } from "../auth";
import { describeError, useAsync } from "../hooks";
import { PRIORITIES, PRIORITY_LABEL, STATUSES, STATUS_LABEL, isOverdue } from "../labels";
import {
  buttonClass,
  ErrorMessage,
  Field,
  inputClass,
  Loading,
  PriorityBadge,
  RoleBadge,
} from "../components/ui";
import type { Task, TaskPriority, TaskStatus } from "../types";

export function BoardPage() {
  // `key` is in the URL: /projects/WEB. The `!` is safe because the route in
  // App.tsx guarantees the parameter exists.
  const key = useParams().key!;
  const { user } = useAuth();

  // The filters are sent to the API, not applied in the browser. That's on
  // purpose: the list route has them, the MCP `list_tasks` tool will use
  // the same ones, and it keeps the two clients honest with each other.
  const [onlyMine, setOnlyMine] = useState(false);
  const [onlyOverdue, setOnlyOverdue] = useState(false);
  const filters: TaskFilters = {
    assignee_id: onlyMine ? user?.id : undefined,
    overdue: onlyOverdue || undefined,
  };

  const project = useAsync(() => api.getProject(key), [key]);
  const members = useAsync(() => api.listMembers(key), [key]);
  const tasks = useAsync(() => api.listTasks(key, filters), [key, onlyMine, onlyOverdue]);

  const [moveError, setMoveError] = useState<string | null>(null);

  async function moveTask(task: Task, status: TaskStatus) {
    setMoveError(null);
    try {
      await api.patchTask(task.ref, { status });
      tasks.reload();
    } catch (e) {
      setMoveError(describeError(e));
    }
  }

  const isAdmin = project.data?.my_role === "admin";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link to="/" className="text-sm text-slate-500 hover:underline">
            ← Projects
          </Link>
          <h1 className="flex items-center gap-2 text-xl font-semibold">
            <span className="font-mono text-sm text-slate-500">{key}</span>
            {project.data?.name ?? "…"}
            {project.data && <RoleBadge role={project.data.my_role} />}
          </h1>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <label className="flex items-center gap-1">
            <input type="checkbox" checked={onlyMine} onChange={(e) => setOnlyMine(e.target.checked)} />
            Only mine
          </label>
          <label className="flex items-center gap-1">
            <input
              type="checkbox"
              checked={onlyOverdue}
              onChange={(e) => setOnlyOverdue(e.target.checked)}
            />
            Only overdue
          </label>
          {/* Hidden for members, but only as a courtesy: the URL still
              works, and the backend decides what they can do there. */}
          {isAdmin && (
            <Link to={`/projects/${key}/members`} className="text-indigo-600 hover:underline">
              Members
            </Link>
          )}
        </div>
      </div>

      <ErrorMessage message={project.error ?? tasks.error ?? moveError} />
      {tasks.loading && !tasks.data && <Loading />}

      {tasks.data && (
        <div className="grid gap-4 md:grid-cols-4">
          {STATUSES.map((status) => {
            const column = tasks.data!.filter((t) => t.status === status);
            return (
              <section key={status} className="rounded-lg bg-slate-100 p-3">
                <h2 className="mb-2 flex items-center justify-between text-sm font-semibold text-slate-700">
                  {STATUS_LABEL[status]}
                  <span className="rounded-full bg-white px-2 text-xs text-slate-500">{column.length}</span>
                </h2>
                <ul className="space-y-2">
                  {column.map((task) => (
                    <li key={task.id} className="rounded border border-slate-200 bg-white p-3 text-sm">
                      <Link to={`/tasks/${task.ref}`} className="block hover:text-indigo-700">
                        <span className="font-mono text-xs text-slate-500">{task.ref}</span>
                        <div className="font-medium">{task.title}</div>
                      </Link>
                      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-600">
                        <PriorityBadge priority={task.priority} />
                        <span>{task.assignee?.full_name ?? "Unassigned"}</span>
                        {task.due_date && (
                          <span className={isOverdue(task.due_date, task.status) ? "font-medium text-red-600" : ""}>
                            due {task.due_date}
                          </span>
                        )}
                      </div>
                      <select
                        aria-label={`Status of ${task.ref}`}
                        value={task.status}
                        onChange={(e) => moveTask(task, e.target.value as TaskStatus)}
                        className="mt-2 w-full rounded border border-slate-300 px-1 py-0.5 text-xs"
                      >
                        {STATUSES.map((s) => (
                          <option key={s} value={s}>
                            {STATUS_LABEL[s]}
                          </option>
                        ))}
                      </select>
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}
        </div>
      )}

      <NewTaskForm
        projectKey={key}
        members={members.data ?? []}
        onCreated={() => tasks.reload()}
      />
    </div>
  );
}

function NewTaskForm({
  projectKey,
  members,
  onCreated,
}: {
  projectKey: string;
  members: { user_id: string; full_name: string }[];
  onCreated: () => void;
}) {
  const [title, setTitle] = useState("");
  const [priority, setPriority] = useState<TaskPriority>("medium");
  const [assigneeId, setAssigneeId] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.createTask(projectKey, {
        title,
        priority,
        // "" from an empty <select>/<input type=date> becomes null on the wire.
        assignee_id: assigneeId || null,
        due_date: dueDate || null,
      });
      setTitle("");
      setAssigneeId("");
      setDueDate("");
      setPriority("medium");
      onCreated();
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-3 rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="font-semibold">New task</h2>
      <div className="grid gap-3 md:grid-cols-[3fr_1fr_1fr_1fr]">
        <Field label="Title">
          <input
            type="text"
            required
            maxLength={500}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className={inputClass}
          />
        </Field>
        <Field label="Priority">
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value as TaskPriority)}
            className={inputClass}
          >
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {PRIORITY_LABEL[p]}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Assignee">
          <select value={assigneeId} onChange={(e) => setAssigneeId(e.target.value)} className={inputClass}>
            <option value="">Unassigned</option>
            {members.map((m) => (
              <option key={m.user_id} value={m.user_id}>
                {m.full_name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Due">
          <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} className={inputClass} />
        </Field>
      </div>
      <ErrorMessage message={error} />
      <button type="submit" disabled={busy} className={buttonClass}>
        Add task
      </button>
    </form>
  );
}
