"use client";

import { useCallback, useEffect, useState } from "react";
import { api, getToken } from "./api";

interface State<T> { key: string | null; data: T | null; error: string | null }

// 화면을 옮겨 다닐 때 지난 응답을 바로 보여 주고 뒤에서 새로 받는다. 메모리에만 두므로 사이트를 새로 열면 비어 있다.
// 토큰을 키에 넣어 다른 사용자로 로그인하면 섞이지 않게
const cache = new Map<string, unknown>();
const cacheKey = (path: string) => `${getToken()}|${path}`;

/** path가 null이면 요청하지 않는다(조직 미선택 등). path가 바뀌면 이전 응답은 무시한다. */
export function useFetch<T>(path: string | null) {
  const [state, setState] = useState<State<T>>({ key: null, data: null, error: null });

  useEffect(() => {
    if (!path) return;
    let alive = true;
    api<T>(path).then(
      (data) => {
        cache.set(cacheKey(path), data);
        if (alive) setState({ key: path, data, error: null });
      },
      (e: Error) => alive && setState((s) => ({ key: path, data: s.data, error: e.message })),
    );
    return () => { alive = false; };
  }, [path]);

  const reload = useCallback(async () => {
    if (!path) return;
    try {
      const data = await api<T>(path);
      cache.set(cacheKey(path), data);
      setState({ key: path, data, error: null });
    } catch (e) {
      setState((s) => ({ key: path, data: s.data, error: (e as Error).message }));
    }
  }, [path]);

  const cached = path && state.key !== path ? (cache.get(cacheKey(path)) as T | undefined) : undefined;
  return { data: state.key === path ? state.data : cached ?? state.data, error: state.error, loading: !!path && state.key !== path && cached === undefined, reload };
}
