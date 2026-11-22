/**
 * The device store (11.4): what SirisOS keeps on this phone, for working offline.
 *
 * A plain key-value store held in memory and saved to IndexedDB, which holds far more than localStorage's ~5 MB
 * (photos and receipts fit) and survives better. Reads are synchronous (from memory), so the rest of the app reads
 * it like before; `loadStore()` fills it from IndexedDB once at start-up, and moves anything older SirisOS kept in
 * localStorage across. Where IndexedDB isn't there (tests, a locked-down browser) it falls back to localStorage.
 */

const DB = "sirisos";
const STORE = "kv";
const memory = new Map<string, string>();
let db: IDBDatabase | null = null;
let ready = false;
const MIGRATE = ["sirisos.cache.", "sirisos.outbox"];

function ls(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function open(): Promise<IDBDatabase | null> {
  return new Promise((resolve) => {
    try {
      if (typeof indexedDB === "undefined") return resolve(null);
      const req = indexedDB.open(DB, 1);
      req.onupgradeneeded = () => req.result.createObjectStore(STORE);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => resolve(null);
      req.onblocked = () => resolve(null);
    } catch {
      resolve(null);
    }
  });
}

/** Fill the store from IndexedDB (once, before the app renders). Gives up after a second and a half. */
export async function loadStore(): Promise<void> {
  if (ready) return;
  const opened = await Promise.race([open(), new Promise<null>((r) => setTimeout(() => r(null), 1500))]);
  if (!opened) { ready = true; return; }
  db = opened;
  await new Promise<void>((resolve) => {
    try {
      const tx = opened.transaction(STORE, "readonly");
      const req = tx.objectStore(STORE).openCursor();
      req.onsuccess = () => {
        const cur = req.result;
        if (cur) { memory.set(String(cur.key), String(cur.value)); cur.continue(); } else resolve();
      };
      req.onerror = () => resolve();
    } catch {
      resolve();
    }
  });
  // Move what older versions kept in localStorage across, once.
  const old = ls();
  if (old) {
    try {
      for (const k of Object.keys(old)) {
        if (!MIGRATE.some((p) => k.startsWith(p))) continue;
        const v = old.getItem(k);
        if (v !== null && !memory.has(k)) setItem(k, v);
        old.removeItem(k);
      }
    } catch { /* blocked */ }
  }
  ready = true;
}

/** Read IndexedDB in again (after the Get ready frame wrote to it from its own copy of the app). */
export async function reloadStore(): Promise<void> {
  if (!db) return;
  const opened = db;
  await new Promise<void>((resolve) => {
    try {
      const req = opened.transaction(STORE, "readonly").objectStore(STORE).openCursor();
      req.onsuccess = () => {
        const cur = req.result;
        if (cur) { memory.set(String(cur.key), String(cur.value)); cur.continue(); } else resolve();
      };
      req.onerror = () => resolve();
    } catch {
      resolve();
    }
  });
}

/** Is the big store (IndexedDB) in use? */
export function bigStore(): boolean {
  return db !== null;
}

function persist(key: string, value: string | null) {
  if (!db) return;
  try {
    const os = db.transaction(STORE, "readwrite").objectStore(STORE);
    if (value === null) os.delete(key); else os.put(value, key);
  } catch { /* the copy in memory still works */ }
}

export function getItem(key: string): string | null {
  if (db) return memory.get(key) ?? null;
  return ls()?.getItem(key) ?? null;
}

export function setItem(key: string, value: string): boolean {
  if (db) {
    memory.set(key, value);
    persist(key, value);
    return true;
  }
  try {
    ls()?.setItem(key, value);
    return true;
  } catch {
    return false;
  }
}

export function removeItem(key: string): void {
  if (db) {
    memory.delete(key);
    persist(key, null);
    return;
  }
  try { ls()?.removeItem(key); } catch { /* blocked */ }
}

export function keys(prefix: string): string[] {
  if (db) return [...memory.keys()].filter((k) => k.startsWith(prefix));
  const store = ls();
  try {
    return store ? Object.keys(store).filter((k) => k.startsWith(prefix)) : [];
  } catch {
    return [];
  }
}

/** Ask the browser not to clear SirisOS's storage when space is short (iOS honours it for Home Screen apps). */
export async function keepStorage(): Promise<boolean> {
  try {
    return (await navigator.storage?.persist?.()) ?? false;
  } catch {
    return false;
  }
}

/** Tests: start empty. */
export function resetStore(): void {
  memory.clear();
}
