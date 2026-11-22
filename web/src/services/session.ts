const STORAGE_KEY = "guardian.session";

/** Returns the per-tab session id (uuid v4), creating it on first use. */
export function getSessionId(): string {
  let id = sessionStorage.getItem(STORAGE_KEY);
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem(STORAGE_KEY, id);
  }
  return id;
}

export function resetSessionId(): void {
  sessionStorage.removeItem(STORAGE_KEY);
}
