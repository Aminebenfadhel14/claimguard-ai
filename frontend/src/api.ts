// Typed client of the thin FastAPI interface (src/claimguard/api.py).
export interface Passage {
  rank: number; chunk_id: string; citation: string; reference: string; title: string; section_title: string
  regulation: string; version: string; version_date: string; valid_until: string | null; source: string
  url: string; start_index: number; rerank_score: number | null; text: string
}
export interface CitationCheck { passage: number; quote: string; verified: boolean; chunk_id: string | null; citation: string | null }
export interface Answer {
  answer: string; consumer_claims: string[]; citations: CitationCheck[]; abstained: boolean; missing_information: string[]
}
export interface AskResult {
  question: string; search_query: string; as_of: string; documents: Passage[]; answer: Answer | null
  warnings: string[]; generation_error: string | null; rewrite_error: string | null; timings_ms: Record<string, number>
}
export interface Status {
  collection: string; loaded: boolean; groq_configured: boolean; groq_model: string
  settings: { mode: string; rerank: boolean; rewrite: boolean; k: number; n_candidates: number }
}
export interface StrategyResult {
  mode: string; rerank: boolean; questions: number; metrics: Record<string, number>
  latency_ms: { mean: number | null; p50: number | null; p95: number | null }
}
export interface Run {
  suite: 'documents' | 'cfpb'; split: string; collection: string; k: number; n_candidates: number; rewrite: boolean
  created_at: string; questions_total: number; questions_evaluated: number; questions_without_qrels: string[]
  rewrite_failures: string[]; results: Record<string, StrategyResult>; annotation?: string; date_filter?: string
}
export interface Selection {
  rule: string; amendment: string | null; metrics: { documents: string; cfpb: string }
  chosen: { collection: string; n_candidates: number; rewrite: boolean; mode: string; rerank: boolean; documents: number; cfpb: number }
}
export interface GenerationGroup { count: number; failures: number; abstention_rate: number | null; answered_with_verified_citation: number | null }
export interface Generation {
  model: string; created_at: string; notes: string[]
  summary: { total: number; generation_failures: number; citation_verified_rate: number | null; groups: Record<string, GenerationGroup> }
}
export interface Evaluation { test: Run[]; development: Run[]; selection: Selection | null; generation: Generation | null }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, { ...init, headers: init?.body ? { 'Content-Type': 'application/json' } : undefined })
  } catch {
    throw new Error('Le serveur ne répond pas : lancez « python -m claimguard serve ».')
  }
  if (!res.ok) {
    const detail = await res.json().then(d => d.detail).catch(() => null)
    throw new Error(typeof detail === 'string' ? detail : `Erreur ${res.status}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  status: () => request<Status>('/api/status'),
  ask: (question: string, as_of: string) =>
    request<AskResult>('/api/ask', { method: 'POST', body: JSON.stringify({ question, as_of }) }),
  evaluation: () => request<Evaluation>('/api/evaluation'),
}

export const num = (x: number | null | undefined, digits = 3) =>
  x === null || x === undefined ? '—' : x.toLocaleString('fr-FR', { maximumFractionDigits: digits, minimumFractionDigits: digits })
