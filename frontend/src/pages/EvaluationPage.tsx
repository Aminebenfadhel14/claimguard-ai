import { useEffect, useState } from 'react'
import { api, ApiError, CorpusId, Evaluation, num, pct, QuestionRow } from '../api'

const METRICS = ['hit@1', 'recall@1', 'recall@3', 'recall@5', 'recall@10', 'precision@5', 'mrr@10', 'ndcg@10']

function Bars({ data }: { data: Evaluation['summary'] }) {
  const w = 700, rowH = 46, left = 240, barW = w - left - 70
  const h = data.length * rowH + 30
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="bars" role="img" aria-label="Recall@5 et MRR@10 par expérience">
      {[0, 0.25, 0.5, 0.75, 1].map(t => (
        <g key={t}>
          <line x1={left + t * barW} x2={left + t * barW} y1={4} y2={h - 22} className="bars-grid" />
          <text x={left + t * barW} y={h - 6} className="bars-axis" textAnchor="middle">{t * 100} %</text>
        </g>
      ))}
      {data.map((e, i) => {
        const y = i * rowH + 8
        const r = e.metrics['recall@5'] ?? 0, m = e.metrics['mrr@10'] ?? 0
        return (
          <g key={e.id}>
            <text x={left - 10} y={y + 17} textAnchor="end" className="bars-label">{e.label}</text>
            <rect x={left} y={y} width={r * barW} height={14} className="bar-recall" rx={2} />
            <text x={left + r * barW + 6} y={y + 11} className="bars-value">{pct(r)}</text>
            <rect x={left} y={y + 18} width={m * barW} height={14} className="bar-mrr" rx={2} />
            <text x={left + m * barW + 6} y={y + 29} className="bars-value">{num(m)}</text>
          </g>
        )
      })}
    </svg>
  )
}

export default function EvaluationPage({ corpus, profile }: { corpus: CorpusId; profile: string }) {
  const [ev, setEv] = useState<Evaluation | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [experiment, setExperiment] = useState('E4')
  const [rows, setRows] = useState<QuestionRow[]>([])
  const [onlyMisses, setOnlyMisses] = useState(false)

  useEffect(() => {
    setEv(null); setError(null)
    api.evaluation(corpus, profile).then(e => {
      setEv(e)
      if (e.available && !e.experiments.includes(experiment)) setExperiment(e.experiments[e.experiments.length - 1])
    }).catch((e: ApiError) => setError(e.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [corpus, profile])

  useEffect(() => {
    if (!ev?.available) return
    api.questions(corpus, experiment).then(r => setRows(r.items)).catch(() => setRows([]))
  }, [ev, corpus, experiment])

  if (error) return <p className="notice notice-error">{error}</p>
  if (!ev) return <p className="muted">Chargement du rapport…</p>
  if (!ev.available) return <div className="empty"><h2>Aucune évaluation enregistrée pour ce corpus</h2><p>Lancez <code>python scripts/evaluate.py --corpus {corpus}</code>.</p></div>

  const p = ev.primary
  const t = ev.targets
  const shown = onlyMisses ? rows.filter(r => r.expected.length > 0 && (r.metrics?.['recall@5'] ?? 1) < 1) : rows

  return (
    <div className="evaluation">
      <p className="muted">
        Rapport <code>{ev.report_path}</code>, jeu {ev.split}{ev.created_at ? `, produit le ${new Date(ev.created_at).toLocaleString('fr-FR')}` : ''}.
        Annotations de pertinence rédigées pour le projet ; une revue humaine indépendante reste requise.
      </p>
      {!ev.profile_matches && <p className="notice notice-warn">Ce rapport correspond à une autre configuration que le profil actif : il ne le mesure pas.</p>}
      {ev.sources_changed && <p className="notice notice-warn">Les documents ont changé depuis cette évaluation. Relancez le protocole pour mesurer le corpus courant.</p>}

      {p && (
        <div className="kpis">
          <div className={'kpi' + (p.metrics['recall@5'] >= t['recall@5'] ? ' kpi-ok' : ' kpi-miss')}>
            <span className="kpi-value">{pct(p.metrics['recall@5'])}</span>
            <span className="kpi-label">Recall@5, hybride + reranking</span>
            <span className="kpi-target">objectif ≥ {pct(t['recall@5'], 0)}</span>
          </div>
          <div className={'kpi' + (p.metrics['mrr@10'] >= t['mrr@10'] ? ' kpi-ok' : ' kpi-miss')}>
            <span className="kpi-value">{num(p.metrics['mrr@10'])}</span>
            <span className="kpi-label">MRR@10</span>
            <span className="kpi-target">objectif ≥ {num(t['mrr@10'], 2)}</span>
          </div>
          <div className={'kpi' + ((p.latency_p95_ms ?? Infinity) / 1000 <= t.latency_p95_s ? ' kpi-ok' : ' kpi-miss')}>
            <span className="kpi-value">{p.latency_p95_ms ? (p.latency_p95_ms / 1000).toFixed(2) + ' s' : 'Non mesurée'}</span>
            <span className="kpi-label">Latence p95 après chargement</span>
            <span className="kpi-target">objectif ≤ {t.latency_p95_s} s</span>
          </div>
        </div>
      )}

      <section className="panel">
        <div className="panel-head">
          <h2>Recall@5 et MRR@10 par expérience</h2>
          <p className="legend"><span className="sw sw-recall" /> Recall@5 <span className="sw sw-mrr" /> MRR@10</p>
        </div>
        <Bars data={ev.summary} />
      </section>

      <section className="panel">
        <h2>Toutes les mesures</h2>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Expérience</th>{METRICS.map(m => <th key={m} className="num">{m}</th>)}<th className="num">Latence moy.</th><th className="num">p95</th></tr></thead>
            <tbody>
              {ev.summary.map(e => (
                <tr key={e.id}>
                  <td>{e.label} <span className="muted">({e.id})</span></td>
                  {METRICS.map(m => <td key={m} className="num">{num(e.metrics[m])}</td>)}
                  <td className="num">{e.latency_mean_ms ? e.latency_mean_ms.toFixed(0) + ' ms' : '—'}</td>
                  <td className="num">{e.latency_p95_ms ? e.latency_p95_ms.toFixed(0) + ' ms' : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted small">Recall@1 : part des sections attendues retrouvée au premier rang. Hit@1 : présence d’une section pertinente au premier rang. Une question peut nécessiter plusieurs sections.</p>
      </section>

      {ev.comparisons.length > 0 && (
        <details className="panel stage">
          <summary><strong>Comparaison avec la livraison initiale</strong></summary>
          <p className="muted small">Le découpage et la sélection par section ont changé ; les annotations du test historique restent identiques.</p>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Expérience</th><th>Mesure</th><th className="num">Avant</th><th className="num">Après</th><th className="num">Variation</th></tr></thead>
              <tbody>
                {ev.comparisons.map((c, i) => (
                  <tr key={i}>
                    <td>{c.label}</td><td>{c.metric}</td>
                    <td className="num">{num(c.before)}</td><td className="num">{num(c.after)}</td>
                    <td className={'num ' + (c.delta > 0 ? 'delta-up' : c.delta < 0 ? 'delta-down' : '')}>{c.delta > 0 ? '+' : ''}{num(c.delta)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}

      <section className="panel">
        <div className="panel-head">
          <h2>Détail par question</h2>
          <div className="inline-controls">
            <select value={experiment} onChange={e => setExperiment(e.target.value)} aria-label="Expérience">
              {ev.summary.map(e => <option key={e.id} value={e.id}>{e.label}</option>)}
            </select>
            <label className="check"><input type="checkbox" checked={onlyMisses} onChange={e => setOnlyMisses(e.target.checked)} /> Seulement les rappels incomplets</label>
          </div>
        </div>
        <p className="muted small">{shown.length} questions affichées sur {rows.length}.</p>
        <div className="table-wrap tall">
          <table>
            <thead><tr><th>Question</th><th>Attendu</th><th>Top 3 obtenu</th><th className="num">Recall@5</th><th className="num">MRR@10</th><th className="num">Latence</th></tr></thead>
            <tbody>
              {shown.map(r => (
                <tr key={r.question_id}>
                  <td>{r.question_id}</td>
                  <td>{r.expected.length ? r.expected.map(x => <code key={x} className="ref">{x}</code>) : <span className="muted">sans réponse</span>}</td>
                  <td>{r.ranked_sections.slice(0, 3).map(x => <code key={x} className={'ref' + (r.expected.includes(x) ? ' ref-hit' : '')}>{x}</code>)}</td>
                  <td className="num">{num(r.metrics?.['recall@5'], 2)}</td>
                  <td className="num">{num(r.metrics?.['mrr@10'], 2)}</td>
                  <td className="num">{r.latency_ms.toFixed(0)} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <details className="panel stage">
        <summary><strong>Protocole et provenance du rapport</strong></summary>
        <pre className="json">{JSON.stringify(ev.protocol, null, 2)}</pre>
      </details>
      <p className="muted small">Sans exécution Groq, la qualité des réponses et l’abstention ne sont pas évaluées. Des citations exactes ne garantissent pas à elles seules la justesse d’une réponse.</p>
    </div>
  )
}
