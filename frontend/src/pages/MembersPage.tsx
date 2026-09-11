// Screen 5: who is in the project, add someone by email, remove someone.
//
// The list is visible to any member (GET .../members is member-only in the
// backend); adding and removing are admin-only. The form and the remove
// buttons are shown only to admins. That is a courtesy for the reader of
// the page, not the rule — the rule is `require_admin` in app/deps.py, and
// phase 8's tool gating will follow exactly this shape: hide, but never rely
// on hiding.
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api";
import { useAuth } from "../auth";
import { describeError, useAsync } from "../hooks";
import { formatDateTime } from "../labels";
import {
  buttonClass,
  ErrorMessage,
  Field,
  inputClass,
  Loading,
  RoleBadge,
} from "../components/ui";
import type { Member, MemberRole } from "../types";

export function MembersPage() {
  const key = useParams().key!;
  const { user } = useAuth();

  const project = useAsync(() => api.getProject(key), [key]);
  const members = useAsync(() => api.listMembers(key), [key]);

  const [email, setEmail] = useState("");
  const [role, setRole] = useState<MemberRole>("member");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const isAdmin = project.data?.my_role === "admin";

  async function addMember(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.addMember(key, email, role);
      setEmail("");
      setRole("member");
      members.reload();
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  async function removeMember(member: Member) {
    const who = member.user_id === user?.id ? "yourself" : member.full_name;
    if (!window.confirm(`Remove ${who} from ${key}? Their tasks will be unassigned.`)) return;
    setError(null);
    try {
      await api.removeMember(key, member.user_id);
      members.reload();
    } catch (e) {
      // "Cannot remove the last admin" arrives here as a 409 sentence.
      setError(describeError(e));
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <Link to={`/projects/${key}`} className="text-sm text-slate-500 hover:underline">
          ← {project.data?.name ?? key}
        </Link>
        <h1 className="text-xl font-semibold">Members</h1>
      </div>

      {(project.loading || members.loading) && !members.data && <Loading />}
      <ErrorMessage message={project.error ?? members.error ?? error} />

      <div className="grid gap-6 md:grid-cols-[2fr_1fr]">
        <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
          {members.data?.map((m) => (
            <li key={m.user_id} className="flex items-center gap-3 px-4 py-3 text-sm">
              <div className="flex-1">
                <div className="font-medium">
                  {m.full_name}
                  {m.user_id === user?.id && <span className="ml-1 text-xs text-slate-400">(you)</span>}
                </div>
                <div className="text-xs text-slate-500">{m.email}</div>
              </div>
              <RoleBadge role={m.role} />
              <span className="hidden w-40 text-right text-xs text-slate-400 sm:block">
                added {formatDateTime(m.added_at)}
              </span>
              {isAdmin && (
                <button
                  type="button"
                  onClick={() => removeMember(m)}
                  className="rounded border border-red-300 px-2 py-1 text-xs text-red-700 hover:bg-red-50"
                >
                  Remove
                </button>
              )}
            </li>
          ))}
        </ul>

        {isAdmin ? (
          <form onSubmit={addMember} className="space-y-3 rounded-lg border border-slate-200 bg-white p-4">
            <h2 className="font-semibold">Add a member</h2>
            <Field label="Email">
              <input
                type="email"
                required
                placeholder="carol@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label="Role">
              <select value={role} onChange={(e) => setRole(e.target.value as MemberRole)} className={inputClass}>
                <option value="member">Member</option>
                <option value="admin">Admin</option>
              </select>
            </Field>
            <button type="submit" disabled={busy} className={buttonClass}>
              Add
            </button>
            <p className="text-xs text-slate-500">
              They need an account already — there is no invite flow.
            </p>
          </form>
        ) : (
          project.data && (
            <p className="text-sm text-slate-500">Only an admin of this project can add or remove members.</p>
          )
        )}
      </div>
    </div>
  );
}
