// The entry point. index.html loads this; it mounts <App> into #root.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import { AuthProvider } from "./auth";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  // StrictMode is dev-only: it double-runs effects to expose ones that don't
  // clean up after themselves. That's why `useAsync` has a cancelled flag.
  <StrictMode>
    {/* BrowserRouter uses real URLs (/projects/WEB), so the address bar is
        shareable and the back button works. The dev server serves index.html
        for any path, so a reload on /projects/WEB still boots the app. */}
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
