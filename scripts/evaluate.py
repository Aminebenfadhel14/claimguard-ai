"""Measured E1–E5. Frozen test and original reports are preserved."""
import argparse
from pathlib import Path
from claimguard.settings import ROOT
from claimguard.evaluation.runner import evaluate

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--home', type=Path, default=ROOT)
    p.add_argument('--trained', type=Path)
    p.add_argument('--corpus', choices=['drip_r', 'novaretail'], default='novaretail')
    p.add_argument('--profile', default=None)
    p.add_argument('--split', choices=['test', 'development'], default='test')
    p.add_argument('--dataset', type=Path)
    p.add_argument('--output', type=Path)
    p.add_argument('--modes', nargs='+', choices=['dense', 'sparse', 'hybrid', 'rerank'])
    a = p.parse_args()
    evaluate(a.home, a.trained, a.corpus, a.profile, a.split, a.dataset, a.modes, a.output)
