import { useCallback, useEffect, useState } from "react";

import { ApiError } from "./api";

/** A human sentence for anything a `fetch` or the API threw. */
export function describeError(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof TypeError) {
    // What `fetch` throws when the server isn't there at all (or CORS
    // refused the response). The most common error on a fresh clone, so it
    // gets a specific hint.
    return "Could not reach the API. Is the backend running on port 8000?";
  }
  return error instanceof Error ? error.message : String(error);
}

interface AsyncState<T> {
  data: T | undefined;
  error: string | null;
  loading: boolean;
}

/**
 * Load something when the component mounts (and again when `deps` change),
 * and expose `reload` so the page can refetch after it changes something.
 *
 * This is the "no React Query" decision in code (frontend/README.md): four
 * pages need "fetch on mount, show a spinner, show the error, refetch after
 * a write". That's ~30 lines once, here, instead of a library to learn.
 *
 * `load` is deliberately not in the effect's dependency list. Pages pass an
 * inline arrow, which is a new function on every render; depending on it
 * would refetch on every render, forever. `deps` is the list of values that
 * should trigger a refetch (usually the route parameter).
 */
export function useAsync<T>(load: () => Promise<T>, deps: unknown[]) {
  const [state, setState] = useState<AsyncState<T>>({
    data: undefined,
    error: null,
    loading: true,
  });
  // Bumping this number is how `reload` re-runs the effect.
  const [generation, setGeneration] = useState(0);

  useEffect(() => {
    // Why the flag: React 19 in dev (StrictMode) mounts, unmounts and mounts
    // every component once to surface effects that don't clean up. Without
    // this, the first (thrown-away) mount's response could land after the
    // second's and overwrite fresh data with stale. The same race happens
    // for real when the user clicks from WEB to API before WEB has loaded.
    let cancelled = false;
    setState((previous) => ({ ...previous, loading: true, error: null }));
    load().then(
      (data) => {
        if (!cancelled) setState({ data, error: null, loading: false });
      },
      (error: unknown) => {
        if (!cancelled) setState({ data: undefined, error: describeError(error), loading: false });
      },
    );
    return () => {
      cancelled = true;
    };
    // eslint would want `load` here; see the docstring for why it isn't.
  }, [...deps, generation]);

  const reload = useCallback(() => setGeneration((g) => g + 1), []);
  return { ...state, reload };
}
