/* Story centroids and topic vectors arrive as int8, base64-encoded — the
   packing `export._centroids` and `readers.pack` share. Pure functions only,
   so they can be tested against the numbers the backend packed. */

const cache = new Map<string, Int8Array>();

export function decodeVector(packed: string | null | undefined): Int8Array | null {
  if (!packed) return null;
  const hit = cache.get(packed);
  if (hit) return hit;
  const raw = atob(packed);
  const out = new Int8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) out[i] = (raw.charCodeAt(i) << 24) >> 24; // byte -> signed
  cache.set(packed, out);
  return out;
}

export function cosine(a: Int8Array, b: Int8Array): number {
  if (a.length !== b.length) return 0;
  let dot = 0, na = 0, nb = 0;
  for (let i = 0; i < a.length; i += 1) { dot += a[i] * b[i]; na += a[i] * a[i]; nb += b[i] * b[i]; }
  return na && nb ? dot / Math.sqrt(na * nb) : 0;
}
