import { useCallback, useEffect, useState } from 'react'
import { api, ApiError, Config, CorpusId, SearchResult, Status } from './api'
import SearchPage, { SearchForm } from './pages/SearchPage'
import DocumentsPage, { DocTarget } from './pages/DocumentsPage'
import ExplainPage from './pages/ExplainPage'
import EvaluationPage from './pages/EvaluationPage'
import Sidebar from './components/Sidebar'

type Tab = 'search' | 'documents' | 'explain' | 'evaluation'
const TABS: { id: Tab; label: string }[] = [
  { id: 'search', label: 'Recherche' },
  { id: 'documents', label: 'Documents' },
  { id: 'explain', label: 'Explication RAG' },
  { id: 'evaluation', label: 'Évaluations' },
]

function initialTab(): Tab {
  const h = window.location.hash.replace('#', '') as Tab
  return TABS.some(t => t.id === h) ? h : 'search'
}

export default function App() {
  const [config, setConfig] = useState<Config | null>(null)
  const [bootError, setBootError] = useState<string | null>(null)
  const [corpus, setCorpus] = useState<CorpusId>('drip_r')
  const [profile, setProfile] = useState<string>('')
  const [status, setStatus] = useState<Status | null>(null)
  const [statusError, setStatusError] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>(initialTab)
  const [result, setResult] = useState<SearchResult | null>(null)
  const [form, setForm] = useState<SearchForm | null>(null)
  const [docTarget, setDocTarget] = useState<DocTarget | null>(null)

  useEffect(() => {
    api.config().then(cfg => {
      setConfig(cfg)
      setCorpus(cfg.default_corpus)
      setProfile(cfg.default_profile)
    }).catch((e: ApiError) => setBootError(e.message))
  }, [])

  const refreshStatus = useCallback(() => {
    if (!profile) return
    api.status(corpus, profile)
      .then(s => { setStatus(s); setStatusError(null) })
      .catch((e: ApiError) => setStatusError(e.message))
  }, [corpus, profile])

  useEffect(() => { refreshStatus() }, [refreshStatus])

  useEffect(() => {
    // Un résultat appartient à un corpus et à un profil : on l'efface quand ils changent.
    setResult(null)
    setForm(null)
  }, [corpus, profile])

  const goTo = (t: Tab) => {
    setTab(t)
    window.history.replaceState(null, '', '#' + t)
  }

  if (bootError) {
    return (
      <div className="boot">
        <h1>ClaimGuard AI</h1>
        <p className="notice notice-error">{bootError}</p>
        <p>Depuis le dossier du projet : <code>.\.venv\Scripts\python.exe scripts\run_web.py</code></p>
      </div>
    )
  }
  if (!config) return <div className="boot"><p>Chargement de la configuration…</p></div>

  const corpusInfo = config.corpora.find(c => c.id === corpus)!

  return (
    <div className="shell">
      <Sidebar
        config={config}
        corpus={corpus}
        profile={profile}
        status={status}
        statusError={statusError}
        onCorpus={setCorpus}
        onProfile={setProfile}
        onRefresh={refreshStatus}
      />
      <main className="main">
        <header className="topbar">
          <div>
            <h1 className="brand-title">ClaimGuard AI</h1>
            <p className="brand-sub">Recherche de preuves dans les politiques, pour traiter les réclamations clients.</p>
          </div>
          <nav className="tabs" role="tablist" aria-label="Sections">
            {TABS.map(t => (
              <button key={t.id} role="tab" aria-selected={tab === t.id}
                className={'tab' + (tab === t.id ? ' tab-active' : '')} onClick={() => goTo(t.id)}>
                {t.label}
                {t.id === 'explain' && result && <span className="tab-dot" aria-label="trace disponible" />}
              </button>
            ))}
          </nav>
        </header>
        <p className={'corpus-note' + (corpusInfo.dated ? '' : ' corpus-note-warn')}>
          <strong>{corpusInfo.short}.</strong> {corpusInfo.note}
        </p>

        <div hidden={tab !== 'search'}>
          <SearchPage
            config={config} corpus={corpus} profile={profile} status={status}
            form={form} setForm={setForm}
            result={result} setResult={r => { setResult(r); refreshStatus() }}
            onOpenSource={t => { setDocTarget(t); goTo('documents') }}
            onExplain={() => goTo('explain')}
          />
        </div>
        {tab === 'documents' && <DocumentsPage corpus={corpus} target={docTarget} />}
        {tab === 'explain' && <ExplainPage result={result} onSearch={() => goTo('search')} />}
        {tab === 'evaluation' && <EvaluationPage corpus={corpus} profile={profile} />}
      </main>
    </div>
  )
}
