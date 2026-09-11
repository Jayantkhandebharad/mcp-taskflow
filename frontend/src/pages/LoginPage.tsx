// Screen 1: log in, or flip to register. One form, one `mode` flag.
import { useState, type FormEvent } from "react";

import { useAuth } from "../auth";
import { describeError } from "../hooks";
import { buttonClass, ErrorMessage, Field, inputClass } from "../components/ui";

export function LoginPage() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, fullName, password);
      // No navigate() here: App.tsx redirects /login to / the moment `user`
      // is set. One place decides where a logged-in user goes.
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <form onSubmit={onSubmit} className="w-full max-w-sm space-y-4 rounded-lg bg-white p-6 shadow">
        <h1 className="text-xl font-semibold">{mode === "login" ? "Log in" : "Create an account"}</h1>

        <Field label="Email">
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={inputClass}
          />
        </Field>

        {mode === "register" && (
          <Field label="Full name">
            <input
              type="text"
              required
              autoComplete="name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className={inputClass}
            />
          </Field>
        )}

        <Field label="Password">
          <input
            type="password"
            required
            // The backend enforces 8–72; saying so here saves a round trip.
            minLength={8}
            maxLength={72}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={inputClass}
          />
        </Field>

        <ErrorMessage message={error} />

        <button type="submit" disabled={busy} className={`${buttonClass} w-full`}>
          {mode === "login" ? "Log in" : "Register"}
        </button>

        <p className="text-center text-sm text-slate-600">
          {mode === "login" ? "No account?" : "Already have an account?"}{" "}
          <button
            type="button"
            className="text-indigo-600 hover:underline"
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setError(null);
            }}
          >
            {mode === "login" ? "Register" : "Log in"}
          </button>
        </p>

        <p className="text-center text-xs text-slate-400">
          Seed accounts: alice@ / bob@ / carol@example.com, password “password”.
        </p>
      </form>
    </div>
  );
}
