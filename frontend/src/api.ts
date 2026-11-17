export type CorpusId = 'drip_r' | 'novaretail'
export type Mode = 'dense' | 'sparse' | 'hybrid' | 'rerank'

export interface Corpus { id: CorpusId; label: string; short: string; dated: boolean; note: string }
export interface Config {
  corpora: Corpus[]
  default_corpus: CorpusId
  profiles: { id: string; label: string }[]
  default_profile: string
  modes: { id: Mode; label: string }[]
  default_query: string
  default_date: string
  groq_configured: boolean
  groq_model: string | null
}
export interface Status {
  corpus: CorpusId
  documents: number
  profile: string
  profile_label: string
  models: { dense: boolean; sparse: boolean; reranker: boolean }
  available_modes: Mode[]
  loaded_modes: Mode[]
  groq_configured: boolean
  engine_ready: boolean
}
export interface Case { scenario_id: string; task_id: string; complaint: string; agent_brief: string }
export interface HitView {
  rank: number
  chunk_id: string
  reference: string
  policy_id: string
  version: string
  title: string
  category: string
  access_level: string
  section: string
  section_title: string | null
  text: string
  source_file: string
  page: number
  line_start: number | null
  line_end: number | null
  file_hash: string
  score: number
  stage: string
}
export type StageName = 'dense' | 'sparse' | 'rrf' | 'reranker' | 'final'
export interface Answer {
  answer: string
  abstained: boolean
  missing_information: string[]
  citations: { chunk_id: string; quote: string; reference: string | null }[]
}
export interface SearchResult {
  corpus: CorpusId
  profile: string
  mode: Mode
  incident_date: string
  query: string
  original_query: string
  rewritten_query: string | null
  stages: Record<StageName, HitView[]>
  diagnostics: Record<string, unknown> & { latency_ms?: number }
  answer: Answer | null
  warnings: string[]
}
export interface SearchPayload {
  corpus: CorpusId
  profile: string
  query: string
  incident_date: string
  mode: Mode
  top_k: number
  category: string | null
  agent_brief: string | null
  use_llm: boolean
}
export interface DocItem {
  name: string
  format: string
  size: number
  policy_id: string | null
  title: string | null
  version: string | null
  category: string | null
  department: string | null
  access_level: string | null
  language: string | null
  effective_date: string | null
  effective_until: string | null
  temporal_basis: string
  has_sections: boolean
}
export interface DocDetail {
  name: string
  metadata: Record<string, unknown>
  text: string | null
  sections: { section: string; title: string; start_line: number; end_line: number }[] | null
  sha256: string
  size: number
}
export interface Experiment {
  id: string
  label: string
  metrics: Record<string, number>
  latency_mean_ms: number | null
  latency_p95_ms: number | null
  mode: string | null
  embedding: string | null
  answerable_questions: number | null
  unanswerable_questions: number | null
}
export interface Evaluation {
  available: boolean
  corpus: CorpusId
  report_path: string
  split: string
  created_at: string | null
  profile_matches: boolean
  sources_changed: boolean
  summary: Experiment[]
  primary: Experiment | null
  comparisons: { id: string; label: string; metric: string; before: number; after: number; delta: number }[]
  protocol: Record<string, unknown>
  experiments: string[]
  targets: { 'recall@5': number; 'mrr@10': number; latency_p95_s: number }
}
export interface QuestionRow {
  question_id: string
  language: string
  expected: string[]
  ranked_sections: string[]
  latency_ms: number
  top_score: number | null
  metrics?: Record<string, number>
}

export class ApiError extends Error {
  status: number
  errorId?: string
  constructor(status: number, message: string, errorId?: string) {
    super(message)
    this.status = status
    this.errorId = errorId
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, {
      ...init,
      headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
    })
  } catch {
    throw new ApiError(0, 'Le serveur FastAPI ne répond pas. Lancez python scripts/run_web.py puis rechargez la page.')
  }
  if (!res.ok) {
    let message = `Erreur ${res.status}`
    let errorId: string | undefined
    try {
      const body = await res.json()
      const d = body.detail
      if (typeof d === 'string') message = d
      else if (Array.isArray(d)) message = d.map((x: { msg: string }) => x.msg).join(' ; ')
      else if (d && typeof d === 'object') {
        message = d.message ?? message
        errorId = d.error_id
        if (d.message && typeof d.message === 'object') {
          message = d.message.message ?? message
          errorId = d.message.error_id
        }
      }
    } catch { /* corps non JSON */ }
    throw new ApiError(res.status, message, errorId)
  }
  return res.json() as Promise<T>
}

const qs = (params: Record<string, string | number | undefined | null>) =>
  '?' + Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join('&')

export const api = {
  config: () => request<Config>('/api/config'),
  status: (corpus: CorpusId, profile: string) => request<Status>('/api/status' + qs({ corpus, profile })),
  load: (corpus: CorpusId, profile: string, mode: Mode) =>
    request<{ loaded: boolean }>('/api/engine/load', { method: 'POST', body: JSON.stringify({ corpus, profile, mode }) }),
  cases: (q: string, limit = 400) => request<{ total: number; items: Case[] }>('/api/cases' + qs({ corpus: 'drip_r', q, limit })),
  categories: (corpus: CorpusId) => request<string[]>('/api/categories' + qs({ corpus })),
  search: (payload: SearchPayload) =>
    request<SearchResult>('/api/search', { method: 'POST', body: JSON.stringify(payload) }),
  documents: (corpus: CorpusId) => request<{ items: DocItem[] }>('/api/documents' + qs({ corpus })),
  document: (corpus: CorpusId, name: string) =>
    request<DocDetail>(`/api/documents/${encodeURIComponent(name)}` + qs({ corpus })),
  downloadUrl: (corpus: CorpusId, name: string) =>
    `/api/documents/${encodeURIComponent(name)}/download` + qs({ corpus }),
  versions: (corpus: CorpusId, policyId: string) =>
    request<{ versions: Record<string, unknown>[] }>(`/api/policies/${encodeURIComponent(policyId)}/versions` + qs({ corpus })),
  compare: (corpus: CorpusId, policyId: string, a: string, b: string) =>
    request<{ diff: string }>(`/api/policies/${encodeURIComponent(policyId)}/compare` + qs({ corpus, a, b })),
  evaluation: (corpus: CorpusId, profile: string) => request<Evaluation>('/api/evaluation' + qs({ corpus, profile })),
  questions: (corpus: CorpusId, experiment: string) =>
    request<{ items: QuestionRow[] }>('/api/evaluation/questions' + qs({ corpus, experiment })),
  chartUrl: (corpus: CorpusId) => '/api/evaluation/chart' + qs({ corpus }),
}

export const pct = (x: number | null | undefined, digits = 1) =>
  x === null || x === undefined ? '—' : (x * 100).toLocaleString('fr-FR', { maximumFractionDigits: digits, minimumFractionDigits: digits }) + ' %'
export const num = (x: number | null | undefined, digits = 3) =>
  x === null || x === undefined ? '—' : x.toLocaleString('fr-FR', { maximumFractionDigits: digits, minimumFractionDigits: digits })
