// Screen 4: one task. Edit its fields, read and add comments, delete it if
// you're an admin.
//
// The edit form is where PATCH semantics show up in the UI: on save, only
// the fields that differ from the loaded task are sent. Clearing the
// assignee sends `assignee_id: null`; not touching it sends nothing.
import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api } from "../api";
import { describeError, useAsync } from "../hooks";
import { PRIORITIES, PRIORITY_LABEL, STATUSES, STATUS_LABEL, formatDateTime } from "../labels";
import {
  buttonClass,
  ErrorMessage,
  Field,
  inputClass,
  Loading,
  secondaryButtonClass,
} from "../components/ui";
import type { Task, TaskPatch, TaskPriority, TaskStatus } from "../types";

/** The editable fields, as the form holds them (strings; "" for empty). */
interface Draft {
  title: string;
  description: string;
  status: TaskStatus;
  priority: TaskPriority;
  assignee_id: string;
  due_date: string;
}

function draftFrom(task: Task): Draft {
  return {
    title: task.title,
    description: task.description ?? "",
    status: task.status,
    priority: task.priority,
    assignee_id: task.assignee?.id ?? "",
    due_date: task.due_date ?? "",
  };
}

/** The PATCH body: only what changed. Empty strings become null. */
function diff(task: Task, draft: Draft): TaskPatch {
  const patch: TaskPatch = {};
  if (draft.title !== task.title) patch.title = draft.title;
  if ((draft.description || null) !== task.description) patch.description = draft.description || null;
  if (draft.status !== task.status) patch.status = draft.status;
  if (draft.priority !== task.priority) patch.priority = draft.priority;
  if ((draft.assignee_id || null) !== (task.assignee?.id ?? null)) {
    patch.assignee_id = draft.assignee_id || null;
  }
  if ((draft.due_date || null) !== task.due_date) patch.due_date = draft.due_date || null;
  return patch;
}

export function TaskPage() {
  const ref = useParams().ref!;
  // "WEB-14" → "WEB". Keys can't contain a hyphen (schemas/projects.py), so
  // the first one is always the split point.
  const key = ref.split("-")[0];
  const navigate = useNavigate();

  const task = useAsync(() => api.getTask(ref), [ref]);
  const project = useAsync(() => api.getProject(key), [key]);
  const members = useAsync(() => api.listMembers(key), [key]);
  const comments = useAsync(() => api.listComments(ref), [ref]);

  const [draft, setDraft] = useState<Draft | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // (Re)fill the form whenever a fresh task arrives — after load and after
  // every save, so the form always reflects what the server has.
  useEffect(() => {
    if (task.data) setDraft(draftFrom(task.data));
  }, [task.data]);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!task.data || !draft) return;
    const patch = diff(task.data, draft);
    if (Object.keys(patch).length === 0) return; // nothing to send
    setBusy(true);
    setSaveError(null);
    try {
      await api.patchTask(ref, patch);
      task.reload();
    } catch (e) {
      setSaveError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm(`Delete ${ref}? This cannot be undone.`)) return;
    setSaveError(null);
    try {
      await api.deleteTask(ref);
      navigate(`/projects/${key}`);
    } catch (e) {
      setSaveError(describeError(e));
    }
  }

  const isAdmin = project.data?.my_role === "admin";
  const dirty = task.data && draft ? Object.keys(diff(task.data, draft)).length > 0 : false;

  return (
    <div className="space-y-6">
      <div>
        <Link to={`/projects/${key}`} className="text-sm text-slate-500 hover:underline">
          ← {project.data?.name ?? key}
        </Link>
        <h1 className="text-xl font-semibold">
          <span className="font-mono text-sm text-slate-500">{ref}</span> {task.data?.title ?? "…"}
        </h1>
      </div>

      {task.loading && !task.data && <Loading />}
      <ErrorMessage message={task.error ?? project.error ?? saveError} />

      {task.data && draft && (
        <div className="grid gap-6 md:grid-cols-[2fr_1fr]">
          <form onSubmit={save} className="space-y-3 rounded-lg border border-slate-200 bg-white p-4">
            <Field label="Title">
              <input
                type="text"
                required
                maxLength={500}
                value={draft.title}
                onChange={(e) => setDraft({ ...draft, title: e.target.value })}
                className={inputClass}
              />
            </Field>
            <Field label="Description">
              <textarea
                rows={6}
                value={draft.description}
                onChange={(e) => setDraft({ ...draft, description: e.target.value })}
                className={inputClass}
              />
            </Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Status">
                <select
                  value={draft.status}
                  onChange={(e) => setDraft({ ...draft, status: e.target.value as TaskStatus })}
                  className={inputClass}
                >
                  {STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {STATUS_LABEL[s]}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Priority">
                <select
                  value={draft.priority}
                  onChange={(e) => setDraft({ ...draft, priority: e.target.value as TaskPriority })}
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
                <select
                  value={draft.assignee_id}
                  onChange={(e) => setDraft({ ...draft, assignee_id: e.target.value })}
                  className={inputClass}
                >
                  <option value="">Unassigned</option>
                  {members.data?.map((m) => (
                    <option key={m.user_id} value={m.user_id}>
                      {m.full_name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Due date">
                <input
                  type="date"
                  value={draft.due_date}
                  onChange={(e) => setDraft({ ...draft, due_date: e.target.value })}
                  className={inputClass}
                />
              </Field>
            </div>
            <div className="flex items-center gap-2">
              <button type="submit" disabled={busy || !dirty} className={buttonClass}>
                Save
              </button>
              {dirty && (
                <button
                  type="button"
                  onClick={() => setDraft(draftFrom(task.data!))}
                  className={secondaryButtonClass}
                >
                  Discard
                </button>
              )}
              {/* Admin-only in the backend (require_admin). Shown only to
                  admins here — but a member who forced it would get the
                  backend's 403 sentence in the error banner, not a crash. */}
              {isAdmin && (
                <button
                  type="button"
                  onClick={remove}
                  className="ml-auto rounded border border-red-300 px-3 py-1.5 text-sm text-red-700 hover:bg-red-50"
                >
                  Delete task
                </button>
              )}
            </div>
            <p className="text-xs text-slate-400">
              Created {formatDateTime(task.data.created_at)} · updated {formatDateTime(task.data.updated_at)}
            </p>
          </form>

          <Comments taskRef={ref} comments={comments.data ?? []} error={comments.error} onAdded={comments.reload} />
        </div>
      )}
    </div>
  );
}

function Comments({
  taskRef,
  comments,
  error,
  onAdded,
}: {
  taskRef: string;
  comments: { id: string; author: { full_name: string }; body: string; created_at: string }[];
  error: string | null;
  onAdded: () => void;
}) {
  const [body, setBody] = useState("");
  const [addError, setAddError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setAddError(null);
    try {
      await api.addComment(taskRef, body);
      setBody("");
      onAdded();
    } catch (e) {
      setAddError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-3">
      <h2 className="font-semibold">Comments</h2>
      <ErrorMessage message={error} />
      {comments.length === 0 && <p className="text-sm text-slate-500">No comments yet.</p>}
      <ul className="space-y-2">
        {comments.map((c) => (
          <li key={c.id} className="rounded border border-slate-200 bg-white p-3 text-sm">
            <div className="mb-1 text-xs text-slate-500">
              <span className="font-medium text-slate-700">{c.author.full_name}</span> ·{" "}
              {formatDateTime(c.created_at)}
            </div>
            <p className="whitespace-pre-wrap">{c.body}</p>
          </li>
        ))}
      </ul>
      <form onSubmit={onSubmit} className="space-y-2">
        <textarea
          rows={3}
          required
          placeholder="Add a comment…"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          className={inputClass}
        />
        <ErrorMessage message={addError} />
        <button type="submit" disabled={busy} className={buttonClass}>
          Comment
        </button>
      </form>
    </section>
  );
}
