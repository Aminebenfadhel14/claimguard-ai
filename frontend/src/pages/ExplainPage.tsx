import { HitView, SearchResult, StageName } from '../api'

const STAGES: { id: StageName; label: string; help: string }[] = [
  { id: 'dense', label: 'Recherche sémantique', help: 'Embeddings MiniLM, similarité cosinus dans Qdrant.' },
  { id: 'sparse', label: 'Recherche BM25', help: 'Mots-clés pondérés (IDF appliqué par Qdrant).' },
  { id: 'rrf', label: 'Fusion RRF', help: 'Reciprocal Rank Fusion des deux listes, k = 60.' },
  { id: 'reranker', label: 'Reranking', help: 'CrossEncoder : la question et le passage sont lus ensemble.' },
  { id: 'final', label: 'Sections retenues', help: 'Une seule entrée par section, dans l’ordre final.' },
]

function rankOf(list: HitView[], reference: string) {
  const i = list.findIndex(h => h.reference === reference)
  return i === -1 ? null : i + 1
}

export default function ExplainPage({ result, onSearch }: { result: SearchResult | null; onSearch: () => void }) {
  if (!result) {
    return (
      <div className="empty">
        <h2>Aucune recherche à expliquer</h2>
        <p>Lancez une recherche pour voir comment chaque étape a classé les passages.</p>
        <button className="primary" onClick={onSearch}>Aller à la recherche</button>
      </div>
    )
  }
  const active = STAGES.filter(s => result.stages[s.id].length > 0 || s.id === 'final')
  const journeyStages = STAGES.filter(s => s.id !== 'final' && result.stages[s.id].length > 0)

  return (
    <div className="explain">
      <section className="panel">
        <h2>Requête envoyée au moteur</h2>
        <pre className="query-box">{result.query}</pre>
        <ol className="pipeline" aria-label="Étapes du pipeline">
          {active.map(s => (
            <li key={s.id}>
              <strong>{s.label}</strong>
              <span className="pipeline-count">{result.stages[s.id].length} passages</span>
              <small>{s.help}</small>
            </li>
          ))}
        </ol>
      </section>

      {journeyStages.length > 0 && (
        <section className="panel">
          <h2>Parcours des sections retenues</h2>
          <p className="muted">Rang de chaque section à chaque étape. Un tiret signifie qu’elle n’apparaissait pas dans cette liste.</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Final</th><th>Référence</th><th>Section</th>
                  {journeyStages.map(s => <th key={s.id} className="num">{s.label}</th>)}
                </tr>
              </thead>
              <tbody>
                {result.stages.final.map(h => (
                  <tr key={h.chunk_id}>
                    <td className="num">{h.rank}</td>
                    <td><code className="ref">{h.reference}</code></td>
                    <td>{h.section_title ?? h.section}</td>
                    {journeyStages.map(s => {
                      const r = rankOf(result.stages[s.id], h.reference)
                      const better = r !== null && r > h.rank
                      return <td key={s.id} className={'num' + (better ? ' moved-up' : '')}>{r ?? '—'}</td>
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {active.map(s => (
        <details key={s.id} className="panel stage" open={s.id === 'final'}>
          <summary><strong>{s.label}</strong> <span className="muted">— {result.stages[s.id].length} passages</span></summary>
          <div className="table-wrap">
            <table>
              <thead><tr><th className="num">Rang</th><th>Référence</th><th>Section</th><th className="num">Score</th><th>Étape</th></tr></thead>
              <tbody>
                {result.stages[s.id].map(h => (
                  <tr key={h.chunk_id + h.rank}>
                    <td className="num">{h.rank}</td>
                    <td><code className="ref">{h.reference}</code></td>
                    <td>{h.section_title ?? h.section}</td>
                    <td className="num">{h.score.toFixed(4)}</td>
                    <td>{h.stage}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      ))}

      <details className="panel stage">
        <summary><strong>Diagnostics</strong></summary>
        <pre className="json">{JSON.stringify(result.diagnostics, null, 2)}</pre>
      </details>
    </div>
  )
}
