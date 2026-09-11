// The route table. Five screens (PLAN.md §10) plus the guard that keeps
// four of them behind a login.
import { Navigate, Outlet, Route, Routes } from "react-router-dom";

import { useAuth } from "./auth";
import { Layout } from "./components/Layout";
import { BoardPage } from "./pages/BoardPage";
import { LoginPage } from "./pages/LoginPage";
import { MembersPage } from "./pages/MembersPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { TaskPage } from "./pages/TaskPage";

/**
 * Render the child routes only when someone is logged in.
 *
 * This is a convenience, not security: anyone can delete this component and
 * see the pages — but every page would then get 401s from the backend and
 * show nothing. The backend is the rule; the guard is the good manners.
 */
function RequireAuth() {
  const { user } = useAuth();
  if (user === undefined) return <p className="p-8 text-slate-500">Loading…</p>;
  if (user === null) return <Navigate to="/login" replace />;
  return (
    <Layout>
      <Outlet />
    </Layout>
  );
}

export function App() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route path="/" element={<ProjectsPage />} />
        <Route path="/projects/:key" element={<BoardPage />} />
        <Route path="/projects/:key/members" element={<MembersPage />} />
        <Route path="/tasks/:ref" element={<TaskPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
