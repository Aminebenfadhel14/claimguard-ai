"""Offline resource diagnostics; --load additionally validates actual retrieval."""
import argparse
import json
from dotenv import load_dotenv
from claimguard.settings import ROOT
from claimguard.diagnostics import readiness

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile', default=None)
    p.add_argument('--corpus', choices=['drip_r', 'novaretail'], default='drip_r')
    p.add_argument('--require-ready', action='store_true')
    p.add_argument('--load', action='store_true')
    a = p.parse_args()
    load_dotenv(ROOT / '.env')
    status = readiness(ROOT, a.corpus, a.profile, verify=True)
    if a.load and 'rerank' in status['available_modes']:
        from claimguard.runtime import build
        from claimguard.models import SearchRequest
        _, engine = build(ROOT, corpus=a.corpus, profile=a.profile, mode='rerank')
        try:
            trace = engine.retrieve(SearchRequest(query='defective product return', incident_date='2026-11-02', mode='rerank'))
            status['engine_ready'] = True
            status['index'] = trace['diagnostics']['index']
        finally: engine.index.close()
    print(json.dumps(status, indent=2, ensure_ascii=False))
    if a.require_ready and 'rerank' not in status['available_modes']: raise SystemExit(1)
