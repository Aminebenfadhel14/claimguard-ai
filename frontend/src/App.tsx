import { useEffect, useState } from 'react'
import { api, AskResult, Evaluation, num, Run, Status } from './api'

type Tab = 'ask' | 'evaluation'

export default function App() {
  const [tab, setTab] = useState<Tab>('ask')
  const [status, setStatus] = useState<Status | null>(null)
  useEffect(() => { api.status().then(setStatus).catch(() => setStatus(null)) }, [])
  return (
    <div className="page">
      <header className="top">
        <div>
          <h1>ClaimGuard AI</h1>
          <p className="muted">Règlements fédéraux 12 CFR (eCFR) · réponses citées, à valider par un humain — pas un avis juridique.</p>
        </div>
        <nav className="tabs">
          <button className={tab === 'ask' ? 'tab active' : 'tab'} onClick={() => setTab('ask')}>Question</button>
          <button className={tab === 'evaluation' ? 'tab active' : 'tab'} onClick={() => setTab('evaluation')}>Évaluations</button>
        </nav>
      </header>
      {status && (
        <p className="small muted">
          Collection <code>{status.collection}</code> · recherche {status.settings.mode}{status.settings.rerank ? ' + CrossEncoder' : ''} ·
          réécriture {status.settings.rewrite ? 'oui' : 'non'} · k={status.settings.k} · Groq {status.groq_configured ? status.groq_model : 'non configuré'}
        </p>
      )}
      {tab === 'ask' ? <AskPage /> : <EvaluationPage />}
    </div>
  )
}

function AskPage() {
  const [question, setQuestion] = useState('How many days does a consumer have to send a billing error notice to a credit card issuer?')
  const [asOf, setAsOf] = useState(new Date().toISOString().slice(0, 10))
  const [result, setResult] = useState<AskResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      setResult(await api.ask(question, asOf))
    } catch (err) {
      setError((err as Error).message)
      setResult(null)
    }
    setBusy(false)
  }
  const verifiedQuotes = (n: number) =>
    (result?.answer?.citations ?? []).filter(c => c.passage === n && c.verified).map(c => c.quote)

  return (
    <section>
      <form className="panel form" onSubmit={submit}>
        <label>Question ou plainte
          <textarea rows={5} value={question} onChange={e => setQuestion(e.target.value)} required minLength={3} />
        </label>
        <div className="row">
          <label>Date de référence (versions en vigueur)
            <input type="date" value={asOf} onChange={e => setAsOf(e.target.value)} required />
          </label>
          <button className="primary" disabled={busy}>{busy ? 'Recherche…' : 'Demander'}</button>
        </div>
      </form>
      {error && <p className="notice error">{error}</p>}
      {result && (
        <>
          {result.warnings.map(w => <p key={w} className="notice warn">{w}</p>)}
          <div className="panel">
            <h2>Réponse</h2>
            {result.answer ? (
              <>
                {result.answer.abstained && <p className="badge">Abstention : preuves insuffisantes</p>}
                <p className="answer">{result.answer.answer}</p>
                {result.answer.consumer_claims.length > 0 && (
                  <>
                    <h3>Déclarations du consommateur (non établies)</h3>
                    <ul>{result.answer.consumer_claims.map(c => <li key={c}>{c}</li>)}</ul>
                  </>
                )}
                {result.answer.missing_information.length > 0 && (
                  <>
                    <h3>Informations manquantes</h3>
                    <ul>{result.answer.missing_information.map(c => <li key={c}>{c}</li>)}</ul>
                  </>
                )}
                <h3>Citations</h3>
                <ul>{result.answer.citations.map((c, i) => (
                  <li key={i}>
                    <span className={c.verified ? 'ok' : 'bad'}>{c.verified ? 'retrouvée mot pour mot' : 'NON retrouvée'}</span>
                    {' '}[{c.passage}] {c.citation} — « {c.quote} »
                  </li>
                ))}</ul>
                <p className="small muted">Une citation retrouvée mot pour mot prouve seulement que ces mots figurent dans le passage, pas que toute la réponse est juste.</p>
              </>
            ) : (
              <p className="muted">Aucune réponse générée{result.generation_error ? ` (${result.generation_error})` : ''} : consultez les passages ci-dessous.</p>
            )}
            <p className="small muted">
              Requête de recherche : « {result.search_query} » · recherche {num(result.timings_ms.retrieval, 0)} ms
              {result.timings_ms.rewrite_llm !== undefined && ` · réécriture ${num(result.timings_ms.rewrite_llm, 0)} ms`}
              {result.timings_ms.answer_llm !== undefined && ` · génération ${num(result.timings_ms.answer_llm, 0)} ms`}
            </p>
          </div>
          <h2 className="section">Sources ({result.documents.length})</h2>
          {result.documents.map(d => (
            <article key={d.chunk_id} className="panel passage">
              <h3>[{d.rank}] {d.citation} — {d.title}</h3>
              <p className="small muted">
                {d.regulation} · {d.section_title} · version {d.version} (eCFR {d.version_date}{d.valid_until ? ` → ${d.valid_until}` : ''}) ·{' '}
                <a href={d.url} target="_blank" rel="noreferrer">texte officiel</a> · chunk <code>{d.chunk_id}</code>
                {d.rerank_score !== null && ` · score CrossEncoder ${num(d.rerank_score, 2)}`}
              </p>
              <blockquote><Highlighted text={d.text} quotes={verifiedQuotes(d.rank)} /></blockquote>
            </article>
          ))}
        </>
      )}
    </section>
  )
}

function Highlighted({ text, quotes }: { text: string; quotes: string[] }) {
  const quote = quotes.find(q => text.includes(q))
  if (!quote) return <>{text}</>
  const i = text.indexOf(quote)
  return <>{text.slice(0, i)}<mark>{quote}</mark>{text.slice(i + quote.length)}</>
}

function RunTable({ run }: { run: Run }) {
  const k = run.k
  const keys = [`precision@${k}`, `recall@${k}`, `hit@${k}`, `mrr@${k}`, `ndcg@${k}`, ...(run.suite === 'cfpb' ? [`paragraph_recall@${k}`] : [])]
  return (
    <div className="panel">
      <h3>{run.suite === 'documents' ? 'Benchmark documentaire' : 'Plaintes CFPB réelles'} — {run.split}</h3>
      <p className="small muted">
        <code>{run.collection}</code> · {run.n_candidates} candidats · réécriture {run.rewrite ? 'oui' : 'non'} ·{' '}
        {run.questions_evaluated}/{run.questions_total} questions évaluées · {run.created_at.slice(0, 16).replace('T', ' ')} UTC
      </p>
      {run.questions_without_qrels.length > 0 && (
        <p className="small">Sans chunk pertinent (exclues des moyennes) : {run.questions_without_qrels.join(', ')}</p>
      )}
      <div className="scroll">
        <table>
          <thead><tr><th>Stratégie</th>{keys.map(key => <th key={key}>{key}</th>)}<th>p50</th><th>p95</th></tr></thead>
          <tbody>{Object.entries(run.results).map(([name, r]) => (
            <tr key={name}>
              <td>{name}</td>{keys.map(key => <td key={key}>{num(r.metrics[key])}</td>)}
              <td>{num(r.latency_ms.p50, 0)} ms</td><td>{num(r.latency_ms.p95, 0)} ms</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      {run.annotation && <p className="small muted">{run.annotation} {run.date_filter}</p>}
    </div>
  )
}

function EvaluationPage() {
  const [data, setData] = useState<Evaluation | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { api.evaluation().then(setData).catch(e => setError(e.message)) }, [])
  if (error) return <p className="notice error">{error}</p>
  if (!data) return <p className="muted">Chargement des rapports…</p>
  const s = data.selection
  const key = (r: Run) => `${r.suite}-${r.collection}-${r.n_candidates}-${r.rewrite}`
  return (
    <section>
      <p className="small muted">
        Valeurs lues dans les rapports de <code>reports/v3/</code> produits par <code>python -m claimguard</code> ;
        synthèse : <code>reports/v3/RESULTS.md</code>.
      </p>
      {s && (
        <div className="panel">
          <h2>Configuration choisie sur le développement</h2>
          <p>
            <code>{s.chosen.collection}</code> · {s.chosen.n_candidates} candidats · réécriture {s.chosen.rewrite ? 'oui' : 'non'} ·{' '}
            {s.chosen.mode}{s.chosen.rerank ? ' + CrossEncoder' : ''} (développement : documents {s.metrics.documents} {num(s.chosen.documents)}, CFPB {s.metrics.cfpb} {num(s.chosen.cfpb)})
          </p>
          <p className="small muted">{s.rule} {s.amendment}</p>
        </div>
      )}
      <h2 className="section">Test</h2>
      {data.test.length ? data.test.map(r => <RunTable key={key(r)} run={r} />) : <p className="muted">Aucun run de test.</p>}
      {data.generation && (
        <div className="panel">
          <h2>Génération ({data.generation.model})</h2>
          <p className="small">
            {data.generation.summary.total} questions · échecs {data.generation.summary.generation_failures} ·
            citations retrouvées {num(data.generation.summary.citation_verified_rate)}
          </p>
          <table>
            <thead><tr><th>Groupe</th><th>Questions</th><th>Échecs</th><th>Abstention</th><th>Réponse avec citation vérifiée</th></tr></thead>
            <tbody>{Object.entries(data.generation.summary.groups).map(([g, v]) => (
              <tr key={g}><td>{g}</td><td>{v.count}</td><td>{v.failures}</td><td>{num(v.abstention_rate)}</td><td>{num(v.answered_with_verified_citation)}</td></tr>
            ))}</tbody>
          </table>
          <ul className="small muted">{data.generation.notes.map(n => <li key={n}>{n}</li>)}</ul>
        </div>
      )}
      <details>
        <summary>Runs de développement ({data.development.length})</summary>
        {data.development.map(r => <RunTable key={key(r)} run={r} />)}
      </details>
    </section>
  )
}
