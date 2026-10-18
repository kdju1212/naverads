"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "./api";

interface State<T> { key: string | null; data: T | null; error: string | null }

/** path가 null이면 요청하지 않는다(조직 미선택 등). path가 바뀌면 이전 응답은 무시한다. */
export function useFetch<T>(path: string | null) {
  const [state, setState] = useState<State<T>>({ key: null, data: null, error: null });

  useEffect(() => {
    if (!path) return;
    let alive = true;
    api<T>(path).then(
      (data) => alive && setState({ key: path, data, error: null }),
      (e: Error) => alive && setState((s) => ({ key: path, data: s.data, error: e.message })),
    );
    return () => { alive = false; };
  }, [path]);

  const reload = useCallback(async () => {
    if (!path) return;
    try {
      const data = await api<T>(path);
      setState({ key: path, data, error: null });
    } catch (e) {
      setState((s) => ({ key: path, data: s.data, error: (e as Error).message }));
    }
  }, [path]);

  return { data: state.data, error: state.error, loading: !!path && state.key !== path, reload };
}
