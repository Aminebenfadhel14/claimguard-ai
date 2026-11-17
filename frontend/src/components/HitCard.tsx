import { HitView } from '../api'

interface Props {
  hit: HitView
  quotes?: string[]
  onOpenSource?: (hit: HitView) => void
}

/** Surligne les citations exactes du brouillon dans le passage. */
export function Highlighted({ text, quotes }: { text: string; quotes?: string[] }) {
  const marks = (quotes ?? []).filter(q => q && text.includes(q))
  if (!marks.length) return <>{text}</>
  const parts: (string | JSX.Element)[] = []
  let rest = text
  let key = 0
  while (rest) {
    let best = -1
    let q = ''
    for (const m of marks) {
      const i = rest.indexOf(m)
      if (i !== -1 && (best === -1 || i < best)) { best = i; q = m }
    }
    if (best === -1) { parts.push(rest); break }
    parts.push(rest.slice(0, best))
    parts.push(<mark key={key++}>{q}</mark>)
    rest = rest.slice(best + q.length)
  }
  return <>{parts}</>
}

export default function HitCard({ hit, quotes, onOpenSource }: Props) {
  const where = hit.line_start
    ? `lignes ${hit.line_start}–${hit.line_end}`
    : `page ${hit.page}`
  const cited = (quotes ?? []).some(q => hit.text.includes(q))
  return (
    <article className={'hit' + (cited ? ' hit-cited' : '')}>
      <div className="hit-rank" aria-label={`Rang ${hit.rank}`}>{hit.rank}</div>
      <div className="hit-body">
        <header className="hit-head">
          <h3>{hit.section_title || hit.title}</h3>
          <code className="ref">{hit.reference}</code>
        </header>
        <p className="hit-meta">
          {hit.title} — version {hit.version}, {where}, fichier {hit.source_file}
        </p>
        <blockquote className="hit-text"><Highlighted text={hit.text} quotes={quotes} /></blockquote>
        <footer className="hit-foot">
          <span title="Score de classement, pas une probabilité">Score {hit.score.toFixed(4)}</span>
          <span>Étape : {hit.stage}</span>
          <span title={hit.file_hash}>SHA-256 {hit.file_hash.slice(0, 12)}</span>
          {onOpenSource && (
            <button className="link-btn" onClick={() => onOpenSource(hit)}>Voir dans le document</button>
          )}
        </footer>
      </div>
    </article>
  )
}
