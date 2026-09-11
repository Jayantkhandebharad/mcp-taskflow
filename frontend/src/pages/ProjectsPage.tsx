// Screen 2: the projects I belong to, a form to create one, and — because
// the route exists and the chat client will have a `my_tasks` tool to
// compare against — the tasks assigned to me across all projects.
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import { describeError, useAsync } from "../hooks";
import { STATUS_LABEL, isOverdue } from "../labels";
import {
  buttonClass,
  ErrorMessage,
  Field,
  inputClass,
  Loading,
  PriorityBadge,
  RoleBadge,
} from "../components/ui";

export function ProjectsPage() {
  const projects = useAsync(() => api.listProjects(), []);
  const myTasks = useAsync(() => api.myTasks(), []);

  const [key, setKey] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function createProject(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.createProject(key, name, description || null);
      setKey("");
      setName("");
      setDescription("");
      projects.reload();
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-8 md:grid-cols-[2fr_1fr]">
      <div className="space-y-8">
        <section>
          <h1 className="mb-3 text-xl font-semibold">Projects</h1>
          {projects.loading && <Loading />}
          <ErrorMessage message={projects.error} />
          {projects.data?.length === 0 && (
            <p className="text-sm text-slate-500">You're not in any project yet. Create one →</p>
          )}
          <ul className="grid gap-3 sm:grid-cols-2">
            {projects.data?.map((p) => (
              <li key={p.id}>
                <Link
                  to={`/projects/${p.key}`}
                  className="block rounded-lg border border-slate-200 bg-white p-4 hover:border-indigo-400"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs text-slate-500">{p.key}</span>
                    <RoleBadge role={p.my_role} />
                  </div>
                  <div className="mt-1 font-medium">{p.name}</div>
                  {p.description && (
                    <p className="mt-1 line-clamp-2 text-sm text-slate-600">{p.description}</p>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-semibold">Assigned to me</h2>
          {myTasks.loading && <Loading />}
          <ErrorMessage message={myTasks.error} />
          {myTasks.data?.length === 0 && <p className="text-sm text-slate-500">Nothing assigned to you.</p>}
          <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
            {myTasks.data?.map((t) => (
              <li key={t.id}>
                <Link to={`/tasks/${t.ref}`} className="flex items-center gap-3 px-4 py-2 hover:bg-slate-50">
                  <span className="w-16 font-mono text-xs text-slate-500">{t.ref}</span>
                  <span className="flex-1 text-sm">{t.title}</span>
                  <PriorityBadge priority={t.priority} />
                  <span className="w-24 text-right text-xs text-slate-500">{STATUS_LABEL[t.status]}</span>
                  {t.due_date && (
                    <span
                      className={`w-24 text-right text-xs ${
                        isOverdue(t.due_date, t.status) ? "font-medium text-red-600" : "text-slate-500"
                      }`}
                    >
                      {t.due_date}
                    </span>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <aside>
        <form onSubmit={createProject} className="space-y-3 rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="font-semibold">New project</h2>
          <Field label="Key">
            <input
              type="text"
              required
              // Same rule as ProjectCreate in the backend: a letter, then 1–9
              // letters or digits. Lowercase is accepted and uppercased there.
              pattern="[A-Za-z][A-Za-z0-9]{1,9}"
              title="A letter followed by 1–9 letters or digits, e.g. WEB"
              placeholder="WEB"
              value={key}
              onChange={(e) => setKey(e.target.value.toUpperCase())}
              className={`${inputClass} font-mono uppercase`}
            />
          </Field>
          <Field label="Name">
            <input
              type="text"
              required
              maxLength={200}
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={inputClass}
            />
          </Field>
          <Field label="Description">
            <textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className={inputClass}
            />
          </Field>
          <ErrorMessage message={error} />
          <button type="submit" disabled={busy} className={buttonClass}>
            Create project
          </button>
          <p className="text-xs text-slate-500">You become its admin.</p>
        </form>
      </aside>
    </div>
  );
}
