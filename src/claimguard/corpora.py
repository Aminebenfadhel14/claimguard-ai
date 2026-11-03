"""Allowlisted corpus routing. Do not mix external benchmark rules with NovaRetail."""
from pathlib import Path

CORPORA = ('novaretail', 'drip_r')

def paths(home, corpus):
    if corpus not in CORPORA:
        raise ValueError('Unknown corpus')
    home = Path(home).resolve()
    if corpus == 'novaretail':
        return dict(policies=home/'data/policies', var=home/'var',
                    evaluation=home/'data/evaluation/questions.jsonl',
                    training=home/'data/synthetic', reports=home/'reports',
                    model=home/'models/novaretail-embedding')
    return dict(policies=home/'data/drip_r/policies', var=home/'var/drip_r',
                evaluation=home/'data/drip_r/evaluation/questions.jsonl',
                training=home/'data/drip_r/training', reports=home/'reports/drip_r',
                model=home/'models/drip-r-policy-embedding')
