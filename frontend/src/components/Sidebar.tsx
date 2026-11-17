import { Config, CorpusId, Status } from '../api'

interface Props {
  config: Config
  corpus: CorpusId
  profile: string
  status: Status | null
  statusError: string | null
  onCorpus: (c: CorpusId) => void
  onProfile: (p: string) => void
  onRefresh: () => void
}

const MODEL_LABELS: Record<string, string> = { dense: 'Embeddings', sparse: 'BM25', reranker: 'Reranker' }

export default function Sidebar({ config, corpus, profile, status, statusError, onCorpus, onProfile, onRefresh }: Props) {
  return (
    <aside className="sidebar">
      <div className="logo">
        <svg viewBox="0 0 32 32" width="30" height="30" aria-hidden="true">
          <path d="M16 4l10 3.6v7.2c0 6-4.2 10.8-10 13.2C10.2 25.6 6 20.8 6 14.8V7.6z" fill="none" stroke="#F2C14E" strokeWidth="2.2" />
          <path d="M11.5 16l3.2 3.2 6-7" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span>ClaimGuard</span>
      </div>

      <label className="side-field">
        <span>Corpus</span>
        <select value={corpus} onChange={e => onCorpus(e.target.value as CorpusId)}>
          {config.corpora.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
        </select>
      </label>
      <label className="side-field">
        <span>Profil de recherche</span>
        <select value={profile} onChange={e => onProfile(e.target.value)}>
          {config.profiles.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
        </select>
      </label>

      <section className="side-status" aria-live="polite">
        <div className="side-status-head">
          <h2>Disponibilité locale</h2>
          <button className="link-btn" onClick={onRefresh}>Actualiser</button>
        </div>
        {statusError && <p className="side-error">{statusError}</p>}
        {status && (
          <ul>
            {Object.entries(status.models).map(([k, ok]) => (
              <li key={k}><span className={'led ' + (ok ? 'led-ok' : 'led-off')} />{MODEL_LABELS[k]} : {ok ? 'prêt' : 'à préparer'}</li>
            ))}
            <li><span className="led led-ok" />{status.documents} documents dans le corpus</li>
            <li><span className={'led ' + (status.groq_configured ? 'led-ok' : 'led-idle')} />
              Groq : {status.groq_configured ? 'configuré' : 'non configuré (facultatif)'}</li>
            <li><span className={'led ' + (status.engine_ready ? 'led-ok' : 'led-idle')} />
              {status.engine_ready
                ? 'Moteur chargé · ' + status.loaded_modes.join(', ')
                : 'Index chargé à la première recherche'}</li>
          </ul>
        )}
      </section>

    </aside>
  )
}
