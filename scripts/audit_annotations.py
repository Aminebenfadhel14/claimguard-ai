"""Structural/source audit only. Does not claim independent semantic review."""
import json
from datetime import datetime, timezone
from claimguard.settings import ROOT, file_hash
from claimguard.corpora import paths
from claimguard.datasets.drip_r import read_jsonl
from claimguard.ingestion.pipeline import parse_with_sidecar

def audit(corpus):
    locations = paths(ROOT, corpus)
    sources = {}
    for path in locations['policies'].glob('*'):
        if path.suffix not in {'.md','.txt','.pdf'}: continue
        _, chunks = parse_with_sidecar(path)
        for c in chunks: sources.setdefault(c.reference(), []).append(c.text)
    questions = read_jsonl(locations['evaluation'])
    missing = [{'question_id': q['question_id'], 'reference': ref} for q in questions for ref in q['relevant_sections'] if ref not in sources]
    report = {'schema_version': 1, 'created_at': datetime.now(timezone.utc).isoformat(),
              'dataset_sha256': file_hash(locations['evaluation']), 'questions': len(questions), 'missing_references': missing,
              'independent_semantic_review': False, 'annotation_changes': [],
              'correction_policy': 'Any correction must be justified in a new dataset version; frozen annotations are never overwritten.'}
    destination = locations['reports']/'annotation_audit_v1.json'
    destination.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(corpus, 'missing references:', len(missing))
    if missing: raise SystemExit(1)

if __name__ == '__main__':
    for corpus in ('drip_r','novaretail'): audit(corpus)
