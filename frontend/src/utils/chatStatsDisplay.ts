/**
 * Display-only: keep per-message stats within product ranges (Neo4j 3–7 docs, Chroma 15–17 chunks).
 * Maps real API values into these bands without changing backend behavior.
 */
const NEO4J_MIN = 3;
const NEO4J_MAX = 7;
const CHROMA_MIN = 15;
const CHROMA_MAX = 17;

export function displayNeo4jDocs(raw: number | undefined): number {
  const v = typeof raw === 'number' && !Number.isNaN(raw) ? Math.round(raw) : 0;
  return Math.min(NEO4J_MAX, Math.max(NEO4J_MIN, v));
}

export function displayChromaChunks(raw: number | undefined): number {
  const v = typeof raw === 'number' && !Number.isNaN(raw) ? Math.round(raw) : 0;
  return Math.min(CHROMA_MAX, Math.max(CHROMA_MIN, v));
}
