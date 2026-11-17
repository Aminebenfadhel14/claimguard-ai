"""Compare only development data. Never selects on frozen benchmark results."""
import argparse
import hashlib
import json
from pathlib import Path
from claimguard.settings import ROOT, load_profile
from claimguard.evaluation.runner import evaluate


def tune(home, profiles, corpus='drip_r', append=False):
    candidates = []
    from claimguard.settings import file_hash
    dataset_sha=file_hash(home/'data/drip_r/development/questions.jsonl')
    if append:
        old=json.loads((home/'reports/drip_r/profile_selection.json').read_text(encoding='utf-8'))
        runs=[json.loads(p.read_text(encoding='utf-8')) for p in (home/'reports/drip_r/runs').glob('*.json')]
        for candidate in old['candidates']:
            if not any(r.get('split')=='development' and r.get('dataset_sha256')==dataset_sha and
                       r.get('profile_fingerprint')==candidate['profile']['fingerprint'] for r in runs):
                raise ValueError('Cannot reuse a selection without matching development-run evidence')
        candidates.extend(old['candidates'])
    for name in profiles:
        for depth in (20, 30):
            profile = load_profile(home, name)
            profile.update(rerank_k=depth)
            result = evaluate(home, corpus=corpus, profile=profile, split='development', modes=['hybrid','rerank'], publish=False)
            score = result['summary']['E4']
            candidates.append({'profile': result['profile'], 'metrics': score['metrics'],
                               'latency_p95_ms': score['latency_p95_ms']})
    eligible = [c for c in candidates if c['latency_p95_ms'] <= 3000] or candidates
    winner = max(eligible, key=lambda c: (c['metrics']['mrr@10'], c['metrics']['recall@5'], -c['latency_p95_ms']))
    report = {'selection_split': 'development', 'dataset_sha256':dataset_sha,
              'selection_order': ['p95 <= 3000 ms if available', 'MRR@10', 'Recall@5', 'lower p95'],
              'candidates': candidates, 'selected': winner, 'test_used_for_selection': False}
    (home/'reports/drip_r/profile_selection.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    # Save the exact selected settings as a new reproducible profile. Keep course untouched.
    config_path = home/'configs/retrieval.json'
    config = json.loads(config_path.read_text(encoding='utf-8'))
    chosen = {k:v for k,v in winner['profile'].items() if k not in {'name','fingerprint'}}
    chosen['label'] = 'Profil validé · ' + winner['profile']['name']
    config['profiles']['validated'] = chosen
    config['default'] = 'validated'
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profiles', nargs='+', default=['course','multilingual','course_reference'])
    p.add_argument('--append',action='store_true',help='Reuse only prior candidates with matching versioned development runs')
    a = p.parse_args()
    tune(ROOT, a.profiles,append=a.append)
