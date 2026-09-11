// The frame every logged-in page sits in: a header with the app name, who
// you are, and a logout button.
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth";

export function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <Link to="/" className="text-lg font-semibold tracking-tight">
            TaskFlow
          </Link>
          <div className="flex items-center gap-4 text-sm">
            <span className="text-slate-600">{user?.full_name}</span>
            <button
              type="button"
              onClick={logout}
              className="rounded border border-slate-300 px-3 py-1 hover:bg-slate-100"
            >
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </div>
  );
}
