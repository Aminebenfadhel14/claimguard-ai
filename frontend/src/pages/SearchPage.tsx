import { useEffect, useMemo, useState } from 'react'
import { api, ApiError, Case, Config, CorpusId, HitView, Mode, SearchResult, Status } from '../api'
import HitCard from '../components/HitCard'
import { DocTarget } from './DocumentsPage'

export interface SearchForm {
  query: string
  caseId: string
  brief: string
  includeBrief: boolean
  date: string
  mode: Mode
  topK: number
  category: string
  useLlm: boolean
}

interface Props {
  config: Config
  corpus: CorpusId
  profile: string
  status: Status | null
  form: SearchForm | null
  setForm: (f: SearchForm) => void
  result: SearchResult | null
  setResult: (r: SearchResult | null) => void
  onOpenSource: (t: DocTarget) => void
  onExplain: () => void
}

export default function SearchPage({ config, corpus, profile, status, form, setForm, result, setResult, onOpenSource, onExplain }: Props) {
  const [cases, setCases] = useState<Case[]>([])
  const [caseFilter, setCaseFilter] = useState('')
  const [categories, setCategories] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const dated = config.corpora.find(c => c.id === corpus)!.dated
  const modes = status?.available_modes.length ? status.available_modes : (['rerank', 'hybrid', 'dense', 'sparse'] as Mode[])
  const preferred: Mode = modes.includes('rerank') ? 'rerank' : modes[modes.length - 1]

  useEffect(() => {
    if (corpus !== 'drip_r') { setCases([]); return }
    api.cases('').then(r => setCases(r.items)).catch(() => setCases([]))
  }, [corpus])

  useEffect(() => {
    api.categories(corpus).then(setCategories).catch(() => setCategories([]))
  }, [corpus])

  // Formulaire initial (au chargement ou après changement de corpus).
  useEffect(() => {
    if (form) return
    const first = corpus === 'drip_r' ? cases[0] : undefined
    if (corpus === 'drip_r' && !first) return
    setForm({
      query: first ? first.complaint : config.default_query,
      caseId: first ? first.scenario_id : '',
      brief: first ? first.agent_brief : '',
      includeBrief: !!first,
      date: config.default_date,
      mode: preferred,
      topK: 5,
      category: '',
      useLlm: false,
    })
  }, [form, cases, corpus, config, preferred, setForm])

  // Garder un mode valide quand la disponibilité change.
  useEffect(() => {
    if (form && status && status.available_modes.length && !status.available_modes.includes(form.mode)) {
      setForm({ ...form, mode: preferred })
    }
  }, [status, form, preferred, setForm])

  const filteredCases = useMemo(() => {
    const n = caseFilter.trim().toLowerCase()
    const list = n ? cases.filter(c => (c.scenario_id + ' ' + c.task_id + ' ' + c.complaint).toLowerCase().includes(n)) : cases
    return list.slice(0, 200)
  }, [cases, caseFilter])

  if (!form) return <p className="muted">Préparation du formulaire…</p>

  const update = (patch: Partial<SearchForm>) => setForm({ ...form, ...patch })
  const chooseCase = (id: string) => {
    const c = cases.find(x => x.scenario_id === id)
    if (c) update({ caseId: id, query: c.complaint, brief: c.agent_brief, includeBrief: true })
  }
  const noModels = status !== null && status.available_modes.length === 0
  const tooShort = form.query.trim().length < 3

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const r = await api.search({
        corpus, profile, query: form.query, incident_date: form.date, mode: form.mode, top_k: form.topK,
        category: form.category || null,
        agent_brief: corpus === 'drip_r' && form.includeBrief ? form.brief : null,
        use_llm: form.useLlm,
      })
      setResult(r)
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setBusy(false)
    }
  }

  const quotes = result?.answer?.citations.map(c => c.quote) ?? []
  const openSource = (h: HitView) => onOpenSource({ name: h.source_file, section: h.section, lineStart: h.line_start, lineEnd: h.line_end })
  const firstLoad = status !== null && !status.loaded_modes.includes(form.mode)

  return (
    <div className="search-layout">
      <form className="panel search-form" onSubmit={submit}>
        <h2>Décrire la réclamation</h2>

        {corpus === 'drip_r' && cases.length > 0 && (
          <fieldset className="case-picker">
            <legend>Exemple du benchmark DRIP-R ({cases.length} scénarios)</legend>
            <input type="search" placeholder="Filtrer par nom, tâche ou mot-clé" value={caseFilter}
              onChange={e => setCaseFilter(e.target.value)} aria-label="Filtrer les scénarios" />
            <select value={form.caseId} onChange={e => chooseCase(e.target.value)} aria-label="Scénario">
              {!filteredCases.some(c => c.scenario_id === form.caseId) && form.caseId && <option value={form.caseId}>{form.caseId}</option>}
              {filteredCases.map(c => <option key={c.scenario_id} value={c.scenario_id}>{c.scenario_id} — {c.task_id}</option>)}
            </select>
          </fieldset>
        )}

        <label className="field">
          <span>Question ou réclamation, en français ou en anglais</span>
          <textarea rows={7} value={form.query} maxLength={6000} onChange={e => update({ query: e.target.value })} />
          <small className="muted">{form.query.length} / 6 000 caractères</small>
        </label>

        {corpus === 'drip_r' && form.brief && (
          <div className="brief">
            <label className="check">
              <input type="checkbox" checked={form.includeBrief} onChange={e => update({ includeBrief: e.target.checked })} />
              Ajouter le contexte visible par l’agent à la recherche
            </label>
            <p>{form.brief}</p>
            <small className="muted">Les champs privés du simulateur ne sont jamais utilisés.</small>
          </div>
        )}

        <div className="field-row">
          <label className="field">
            <span>{dated ? 'Date de l’incident' : 'Date technique du benchmark'}</span>
            <input type="date" value={form.date} disabled={!dated} onChange={e => update({ date: e.target.value })} />
          </label>
          <label className="field">
            <span>Nombre de sections</span>
            <input type="number" min={1} max={20} value={form.topK}
              onChange={e => update({ topK: Math.max(1, Math.min(20, Number(e.target.value) || 1)) })} />
          </label>
        </div>

        <label className="field">
          <span>Méthode</span>
          <select value={form.mode} onChange={e => update({ mode: e.target.value as Mode })}>
            {config.modes.filter(m => modes.includes(m.id)).map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
          </select>
        </label>

        {categories.length > 1 && (
          <label className="field">
            <span>Catégorie de politique</span>
            <select value={form.category} onChange={e => update({ category: e.target.value })}>
              <option value="">Toutes les catégories</option>
              {categories.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
        )}

        <label className={'check' + (config.groq_configured ? '' : ' check-disabled')}>
          <input type="checkbox" checked={form.useLlm} disabled={!config.groq_configured}
            onChange={e => update({ useLlm: e.target.checked })} />
          Rédiger un brouillon sourcé avec Groq
          {!config.groq_configured && <small className="muted"> — ajoutez GROQ_API_KEY dans .env</small>}
        </label>

        <button type="submit" className="primary" disabled={busy || noModels || tooShort}>
          {busy ? 'Recherche en cours…' : 'Rechercher les règles'}
        </button>
        {busy && firstLoad && <p className="muted small">Premier chargement des modèles et de l’index : cela peut prendre une minute.</p>}
        {noModels && (
          <p className="notice notice-warn">
            Les modèles locaux doivent être préparés : <code>.\.venv\Scripts\python.exe scripts/prepare_models.py --profiles {profile}</code>
          </p>
        )}
      </form>

      <section className="results" aria-live="polite">
        {error && (
          <div className="notice notice-error">
            {error.message}{error.errorId && <> Référence : <code>{error.errorId}</code></>}
          </div>
        )}
        {!result && !error && !busy && (
          <div className="empty">
            <h2>Les règles applicables apparaîtront ici</h2>
            <p>Décrivez la situation du client puis lancez la recherche. Chaque passage est relié à sa politique, sa version et sa section.</p>
          </div>
        )}
        {busy && !result && <div className="skeleton" aria-hidden="true"><div /><div /><div /></div>}
        {result && (
          <>
            <div className="results-head">
              <p>
                <strong>{result.stages.final.length} sections distinctes</strong> en {((result.diagnostics.latency_ms ?? 0) / 1000).toFixed(2)} s,
                profil {result.profile}, méthode {config.modes.find(m => m.id === result.mode)?.label}
              </p>
              <button className="link-btn" onClick={onExplain}>Voir le classement étape par étape</button>
            </div>
            {result.warnings.map((w, i) => <p key={i} className="notice notice-warn">{w}</p>)}
            {result.rewritten_query && (
              <p className="muted small">Requête réécrite par le LLM : « {result.rewritten_query} »</p>
            )}
            {result.answer && (
              <section className={'draft' + (result.answer.abstained ? ' draft-abstained' : '')}>
                <h2>{result.answer.abstained ? 'Le brouillon s’abstient' : 'Brouillon à vérifier'}</h2>
                <p>{result.answer.answer}</p>
                {result.answer.missing_information.length > 0 && (
                  <p className="muted">Informations manquantes : {result.answer.missing_information.join(' ; ')}</p>
                )}
                {result.answer.citations.length > 0 && (
                  <ul className="citations">
                    {result.answer.citations.map((c, i) => (
                      <li key={i}><code className="ref">{c.reference ?? c.chunk_id.slice(0, 10)}</code> <mark>{c.quote}</mark></li>
                    ))}
                  </ul>
                )}
              </section>
            )}
            {result.stages.final.length === 0 && (
              <p className="notice notice-warn">Aucun passage ne correspond aux filtres. Essayez une autre catégorie ou une autre date.</p>
            )}
            {result.stages.final.map(h => <HitCard key={h.chunk_id} hit={h} quotes={quotes} onOpenSource={openSource} />)}
          </>
        )}
      </section>
    </div>
  )
}
