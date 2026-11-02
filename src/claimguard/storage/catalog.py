"""Immutable document versions and transactional catalog. Index is rebuildable."""
import hashlib
import json
import sqlite3
from datetime import date
from pathlib import Path
from claimguard.models import Chunk, PolicyMetadata
from claimguard.ingestion.pipeline import parse_with_sidecar

class Catalog:
    def __init__(self, home: Path):
        self.home = Path(home)
        self.home.mkdir(parents=True, exist_ok=True)
        (self.home / 'sources').mkdir(exist_ok=True)
        self.db = self.home / 'catalog.sqlite'
        with self.connect() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS documents (
              policy_id TEXT NOT NULL, version TEXT NOT NULL, hash TEXT NOT NULL,
              metadata TEXT NOT NULL, source TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
              PRIMARY KEY(policy_id,version));
            CREATE TABLE IF NOT EXISTS chunks (id TEXT PRIMARY KEY, policy_id TEXT, version TEXT, data TEXT);
            CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, occurred TEXT DEFAULT CURRENT_TIMESTAMP,
              action TEXT, policy_id TEXT, version TEXT, actor TEXT);
            ''')
    def connect(self):
        return sqlite3.connect(self.db)
    def ingest(self, path: Path, actor='local-admin'):
        meta, chunks = parse_with_sidecar(path)
        digest = chunks[0].file_hash
        with self.connect() as c:
            old = c.execute('SELECT hash,metadata FROM documents WHERE policy_id=? AND version=?',
                            (meta.policy_id, meta.version)).fetchone()
            if old:
                if old[0] == digest and PolicyMetadata.model_validate_json(old[1]) == meta:
                    if path.with_suffix(path.suffix + '.sections.json').exists():
                        previous_chunks = c.execute('SELECT data FROM chunks WHERE policy_id=? AND version=?',
                            (meta.policy_id,meta.version)).fetchall()
                        stored = sorted(Chunk.model_validate_json(r[0]).model_dump_json() for r in previous_chunks)
                        incoming = sorted(x.model_dump_json() for x in chunks)
                        if stored != incoming:
                            raise ValueError('Immutable section mapping conflict: create a new snapshot version')
                    return {'status':'duplicate', 'chunks':0}
                raise ValueError('Immutable version conflict: create a new version and effective interval')
            intervals = c.execute('SELECT metadata FROM documents WHERE policy_id=?', (meta.policy_id,)).fetchall()
            for (raw,) in intervals:
                previous = json.loads(raw)
                a, b = (meta.effective_date or date.min).isoformat(), (meta.effective_until or date.max).isoformat()
                if a < (previous['effective_until'] or date.max.isoformat()) and (previous['effective_date'] or date.min.isoformat()) < b:
                    raise ValueError('Overlapping effective intervals for policy versions')
            source = self.home / 'sources' / (digest + path.suffix.lower())
            source.write_bytes(path.read_bytes())
            c.execute('INSERT INTO documents(policy_id,version,hash,metadata,source) VALUES (?,?,?,?,?)',
                      (meta.policy_id,meta.version,digest,meta.model_dump_json(),str(source)))
            c.executemany('INSERT INTO chunks VALUES (?,?,?,?)',
                          [(x.chunk_id,meta.policy_id,meta.version,x.model_dump_json()) for x in chunks])
            c.execute('INSERT INTO events(action,policy_id,version,actor) VALUES (?,?,?,?)',
                      ('ingest',meta.policy_id,meta.version,actor))
        return {'status':'added','chunks':len(chunks),'file_hash':digest}
    def deactivate(self, policy_id, version, actor):
        with self.connect() as c:
            if not c.execute('SELECT 1 FROM documents WHERE policy_id=? AND version=?',(policy_id,version)).fetchone():
                raise KeyError('Unknown version')
            c.execute('UPDATE documents SET active=0 WHERE policy_id=? AND version=?',(policy_id,version))
            c.execute('INSERT INTO events(action,policy_id,version,actor) VALUES (?,?,?,?)',
                      ('deactivate',policy_id,version,actor))
    def chunks(self, as_of: date | None = None, access=('public','internal'), category=None):
        with self.connect() as c:
            rows = c.execute('SELECT c.data FROM chunks c JOIN documents d ON c.policy_id=d.policy_id '
                             'AND c.version=d.version WHERE d.active=1 ORDER BY c.id').fetchall()
        result = [Chunk.model_validate_json(r[0]) for r in rows]
        return [x for x in result if x.metadata.access_level in access
                and (not category or x.metadata.category==category)
                and (as_of is None or ((x.metadata.effective_date is None or x.metadata.effective_date <= as_of)
                     and (x.metadata.effective_until is None or as_of < x.metadata.effective_until)))]
    def versions(self, policy_id):
        with self.connect() as c:
            return [json.loads(r[0]) for r in c.execute('SELECT metadata FROM documents WHERE policy_id=? ORDER BY version',(policy_id,))]
    def compare(self, policy_id, v1, v2):
        import difflib
        with self.connect() as c:
            contents = []
            for version in (v1,v2):
                rows=c.execute('SELECT data FROM chunks WHERE policy_id=? AND version=?',(policy_id,version)).fetchall()
                if not rows: raise KeyError('Unknown policy/version')
                chunks=sorted((Chunk.model_validate_json(r[0]) for r in rows),key=lambda x:(x.page,x.section))
                contents.append('\n'.join(x.text for x in chunks).splitlines())
        return '\n'.join(difflib.unified_diff(*contents,fromfile=v1,tofile=v2,lineterm=''))
