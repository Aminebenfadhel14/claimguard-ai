import { useEffect, useMemo, useRef, useState } from 'react'
import { api, ApiError, CorpusId, DocDetail, DocItem } from '../api'

export interface DocTarget { name: string; section: string; lineStart: number | null; lineEnd: number | null }

interface Block { section: string | null; title: string | null; lines: string[]; start: number }

const HEADING = /^(?:#{1,6}\s+)?(\d+(?:\.\d+)+)\s+[—–-]?\s*(.*)$/

/** Découpe le texte en blocs de section (sidecar .sections.json ou titres numérotés). */
function toBlocks(doc: DocDetail): Block[] {
  const lines = (doc.text ?? '').split(/\r?\n/)
  if (doc.sections?.length) {
    return doc.sections.map(s => ({ section: s.section, title: s.title, lines: lines.slice(s.start_line - 1, s.end_line), start: s.start_line }))
  }
  const blocks: Block[] = [{ section: null, title: null, lines: [], start: 1 }]
  lines.forEach((line, i) => {
    const m = line.match(HEADING)
    if (m) blocks.push({ section: m[1], title: m[2], lines: [line], start: i + 1 })
    else blocks[blocks.length - 1].lines.push(line)
  })
  return blocks.filter(b => b.lines.some(l => l.trim()))
}

function DiffView({ diff }: { diff: string }) {
  if (!diff.trim()) return <p className="muted">Aucune différence de texte entre ces versions.</p>
  return (
    <pre className="diff">
      {diff.split('\n').map((l, i) => {
        const cls = l.startsWith('+++') || l.startsWith('---') ? 'd-file' : l.startsWith('@@') ? 'd-hunk' : l.startsWith('+') ? 'd-add' : l.startsWith('-') ? 'd-del' : ''
        return <span key={i} className={cls}>{l + '\n'}</span>
      })}
    </pre>
  )
}

export default function DocumentsPage({ corpus, target }: { corpus: CorpusId; target: DocTarget | null }) {
  const [items, setItems] = useState<DocItem[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [doc, setDoc] = useState<DocDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showMeta, setShowMeta] = useState(false)
  const [cmp, setCmp] = useState<{ a: string; b: string; diff: string | null; busy: boolean; error: string | null }>({ a: '', b: '', diff: null, busy: false, error: null })
  const viewer = useRef<HTMLDivElement>(null)
  const activeTarget = target && target.name === selected ? target : null

  useEffect(() => {
    setError(null)
    api.documents(corpus).then(r => {
      setItems(r.items)
      const wanted = target && r.items.some(d => d.name === target.name) ? target.name : r.items[0]?.name ?? null
      setSelected(wanted)
    }).catch((e: ApiError) => setError(e.message))
  }, [corpus, target])

  useEffect(() => {
    if (!selected) return
    setDoc(null)
    api.document(corpus, selected).then(setDoc).catch((e: ApiError) => setError(e.message))
  }, [corpus, selected])

  const blocks = useMemo(() => (doc ? toBlocks(doc) : []), [doc])

  useEffect(() => {
    if (!doc || !activeTarget) return
    const el = viewer.current?.querySelector('[data-active="true"]')
    el?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [doc, activeTarget])

  const current = items.find(d => d.name === selected)
  const siblings = current?.policy_id ? items.filter(d => d.policy_id === current.policy_id) : []
  useEffect(() => {
    if (siblings.length > 1) {
      setCmp({ a: siblings[0].version ?? '', b: siblings[siblings.length - 1].version ?? '', diff: null, busy: false, error: null })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current?.policy_id, siblings.length])

  const runCompare = async () => {
    if (!current?.policy_id) return
    setCmp(c => ({ ...c, busy: true, error: null }))
    try {
      const r = await api.compare(corpus, current.policy_id, cmp.a, cmp.b)
      setCmp(c => ({ ...c, diff: r.diff, busy: false }))
    } catch (e) {
      setCmp(c => ({ ...c, busy: false, error: (e as ApiError).message }))
    }
  }

  const groups = useMemo(() => {
    const g = new Map<string, DocItem[]>()
    items.forEach(d => { const k = d.policy_id ?? d.name; g.set(k, [...(g.get(k) ?? []), d]) })
    return [...g.entries()]
  }, [items])

  if (error) return <p className="notice notice-error">{error}</p>
  if (!items.length) return <p className="muted">Aucun document source disponible pour ce corpus.</p>

  return (
    <div className="docs-layout">
      <nav className="panel doc-list" aria-label="Documents sources">
        <h2>Documents sources</h2>
        {groups.map(([policy, docs]) => (
          <div key={policy} className="doc-group">
            <p className="doc-group-title">{docs[0].title ?? policy}</p>
            {docs.map(d => (
              <button key={d.name} className={'doc-item' + (d.name === selected ? ' doc-item-active' : '')}
                onClick={() => setSelected(d.name)}>
                <code>{d.policy_id}</code>
                <span>v{d.version}{d.effective_date ? `, dès le ${d.effective_date}` : ''}{d.temporal_basis === 'dataset_snapshot' ? ', instantané' : ''}</span>
              </button>
            ))}
          </div>
        ))}
      </nav>

      <section className="panel doc-viewer" ref={viewer}>
        {!doc && <p className="muted">Chargement du document…</p>}
        {doc && current && (
          <>
            <header className="doc-head">
              <div>
                <h2>{current.title}</h2>
                <p className="muted">
                  {current.policy_id} version {current.version} · {current.category} · accès {current.access_level} · {current.department}
                  {current.effective_date && <> · en vigueur du {current.effective_date}{current.effective_until ? ` au ${current.effective_until}` : ''}</>}
                </p>
              </div>
              <div className="doc-actions">
                <a className="btn" href={api.downloadUrl(corpus, doc.name)} download>Télécharger la source</a>
                <button className="btn" onClick={() => setShowMeta(s => !s)} aria-expanded={showMeta}>
                  {showMeta ? 'Masquer la provenance' : 'Provenance et métadonnées'}
                </button>
              </div>
            </header>
            {showMeta && (
              <div className="meta-box">
                <p><strong>Fichier :</strong> {doc.name} ({doc.size.toLocaleString('fr-FR')} octets)</p>
                <p><strong>SHA-256 :</strong> <code>{doc.sha256}</code></p>
                <pre>{JSON.stringify(doc.metadata, null, 2)}</pre>
              </div>
            )}

            {siblings.length > 1 && (
              <div className="compare">
                <p><strong>{siblings.length} versions de {current.policy_id}.</strong> Comparer le texte :</p>
                <select value={cmp.a} onChange={e => setCmp(c => ({ ...c, a: e.target.value, diff: null }))} aria-label="Version A">
                  {siblings.map(s => <option key={s.name} value={s.version ?? ''}>v{s.version}</option>)}
                </select>
                <span>avec</span>
                <select value={cmp.b} onChange={e => setCmp(c => ({ ...c, b: e.target.value, diff: null }))} aria-label="Version B">
                  {siblings.map(s => <option key={s.name} value={s.version ?? ''}>v{s.version}</option>)}
                </select>
                <button className="btn" onClick={runCompare} disabled={cmp.busy || cmp.a === cmp.b}>
                  {cmp.busy ? 'Comparaison…' : 'Comparer'}
                </button>
                {cmp.error && <p className="notice notice-error">{cmp.error}</p>}
                {cmp.diff !== null && <DiffView diff={cmp.diff} />}
              </div>
            )}

            {doc.text === null ? (
              <p className="notice">Document PDF : utilisez « Télécharger la source » pour l’ouvrir.</p>
            ) : (
              <div className="policy-text">
                {blocks.map((b, i) => {
                  const active = !!activeTarget && b.section === activeTarget.section
                  return (
                    <div key={i} className={'policy-block' + (active ? ' policy-block-active' : '')} data-active={active}>
                      {b.section && doc.sections && (
                        <p className="policy-block-label">§ {b.section} — {b.title} <span className="muted">(lignes {b.start}–{b.start + b.lines.length - 1})</span></p>
                      )}
                      <div className="policy-lines">{b.lines.join('\n')}</div>
                    </div>
                  )
                })}
              </div>
            )}
          </>
        )}
      </section>
    </div>
  )
}
