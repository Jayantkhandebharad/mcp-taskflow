// Vite's build configuration. Vite is the dev server (`npm run dev`) and the
// bundler (`npm run build`); this file tells it about React, Tailwind, and
// where our environment variables live.
import { fileURLToPath } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// The repo root — one level up from this folder. Every service in TaskFlow
// reads the SAME `.env` at the repo root (CLAUDE.md: "all of them listed in
// `.env.example`"). Vite would normally look for `.env` next to this file, so
// we point it at the root instead.
const repoRoot = fileURLToPath(new URL("..", import.meta.url));

export default defineConfig(({ mode }) => {
  // `loadEnv` reads `.env` for *this* config file. The third argument is the
  // prefix filter; "" means "give me every variable", which we need because
  // FRONTEND_PORT does not start with VITE_. (Browser code is a different
  // story — see the comment on `envDir` below.)
  const env = loadEnv(mode, repoRoot, "");

  return {
    plugins: [react(), tailwindcss()],

    // Where the *browser* bundle gets its variables from. Vite only exposes
    // variables prefixed `VITE_` to browser code (as `import.meta.env.VITE_*`),
    // so the database password in the same file can never leak into the
    // bundle. That prefix is the whole safety mechanism; keep it in mind
    // before naming anything VITE_.
    envDir: repoRoot,

    server: {
      port: Number(env.FRONTEND_PORT ?? 5173),
      // If 5173 is taken, fail instead of silently picking 5174 — the
      // backend's CORS list names 5173 exactly, and a different port would
      // produce a confusing "blocked by CORS" error rather than a clear one.
      strictPort: true,
    },
  };
});
