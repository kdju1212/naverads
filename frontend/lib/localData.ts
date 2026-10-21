/** 브라우저 보관소(IndexedDB). 광고 데이터 사본은 서버 DB 대신 여기에만 둔다.
 * 비밀키·토큰은 넣지 않는다. 로그인·로그아웃 때 전부 지운다(같은 PC를 다른 사람이 쓸 수 있음). */

const DB = "naverads";
const STORE = "accounts";

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function run<T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await open();
  try {
    return await new Promise<T>((resolve, reject) => {
      const req = fn(db.transaction(STORE, mode).objectStore(STORE));
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  } finally {
    db.close();
  }
}

// 사생활 보호 모드 등 IndexedDB를 못 쓰는 환경에서는 보관 없이 매번 받는다
export async function loadLocal<T>(key: string): Promise<T | undefined> {
  try { return await run<T>("readonly", (s) => s.get(key) as IDBRequest<T>); } catch { return undefined; }
}
export async function saveLocal(key: string, value: unknown) {
  try { await run("readwrite", (s) => s.put(value, key)); } catch { /* 보관 불가 */ }
}
export async function localKeys(): Promise<string[]> {
  try { return (await run("readonly", (s) => s.getAllKeys())).map(String); } catch { return []; }
}
export async function removeLocal(key: string) {
  try { await run("readwrite", (s) => s.delete(key)); } catch { /* 보관 불가 */ }
}
export async function clearLocal() {
  try { await run("readwrite", (s) => s.clear()); } catch { /* 보관 불가 */ }
}
