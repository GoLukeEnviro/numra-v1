/** A fresh Idempotency-Key for one user-initiated start (falls back where `crypto.randomUUID`
 *  is unavailable). */
export function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `key-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
