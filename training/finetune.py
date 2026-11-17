"""Real CPU triplet training; hard negatives and validation retrieval selection.

The original checkpoint is preserved. Epoch zero is a candidate; no automatic
production promotion occurs without a measured end-to-end validation gain.
"""
import argparse
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import torch
from claimguard.settings import ROOT, load_profile, file_hash
from claimguard.runtime import build
from claimguard.corpora import paths
from claimguard.models import SearchRequest
from claimguard.datasets.drip_r import read_jsonl
from claimguard.evaluation.metrics import metrics
from claimguard.evaluation.runner import evaluate, validate_split


def main(home, epochs=3, lr=2e-5, seed=42, corpus='drip_r', profile=None):
    home = Path(home).resolve()
    torch.set_num_threads(min(4, __import__('os').cpu_count() or 1))
    torch.manual_seed(seed); np.random.seed(seed); random.seed(seed)
    profile = load_profile(home, profile)
    locations = paths(home, corpus)
    training_path = home/'data/drip_r/development/training.jsonl' if corpus=='drip_r' else locations['training']/'train.jsonl'
    validation_path = home/'data/drip_r/development/questions.jsonl' if corpus=='drip_r' else locations['training']/'validation.jsonl'
    train, validation = read_jsonl(training_path), read_jsonl(validation_path)
    if corpus!='drip_r':
        train=[dict(r,relevant_sections=[r['reference']]) for r in train]
        validation=[dict(r,question=r['query'],question_id=f'VAL-{i}',incident_date='2026-11-02',
                         relevant_sections=[r['reference']]) for i,r in enumerate(validation)]
    validate_split(home, corpus, validation, 'development')
    frozen = read_jsonl(locations['evaluation'])
    groups = [{r['scenario_group'] for r in data} for data in (train, validation, frozen)]
    queries = [{r.get('query', r.get('question')).strip().casefold() for r in data} for data in (train, validation, frozen)]
    if any(groups[i]&groups[j] or queries[i]&queries[j] for i,j in ((0,1),(0,2),(1,2))):
        raise ValueError('Training/development/test leakage')
    _, engine = build(home, corpus=corpus, mode='dense', profile=profile)
    model = engine.index.encoder
    chunks = list(engine.index.chunks.values())
    # Mine once from the untrained baseline; exclude ALL relevant sections.
    triplets = []
    for row in train:
        ranking = engine.index.search(row['query'], __import__('datetime').date(2026,11,2), 'dense', top_k=len(chunks))
        positive = next((h.chunk.text for h in ranking if h.chunk.reference() in row['relevant_sections']), None)
        negative = next((h.chunk.text for h in ranking if h.chunk.reference() not in row['relevant_sections']), None)
        if positive is None or negative is None: raise ValueError('Missing positive or eligible hard negative')
        triplets.append(dict(row, positive=positive, negative=negative))
    engine.index.close()
    prefix_query = profile['dense'].get('query_prefix','')
    prefix_passage = profile['dense'].get('passage_prefix','')
    # Rebuild real dense Qdrant vectors for each checkpoint, using the same windows.
    def validation_score():
        from claimguard.indexing.qdrant import PolicyIndex
        from claimguard.retrieval.engine import RetrievalEngine
        model.eval()
        index = PolicyIndex(chunks, model, None, profile=profile)
        evaluator = RetrievalEngine(index, profile=profile)
        measured = []
        try:
            for row in validation:
                if not row['relevant_sections']: continue
                trace = evaluator.retrieve(SearchRequest(query=row['question'], incident_date=row['incident_date'], mode='dense', top_k=10))
                measured.append(metrics([h.chunk.reference() for h in trace['final']], row['relevant_sections']))
        finally: index.close()
        return {k: float(np.mean([m[k] for m in measured])) for k in measured[0]}
    def loss(batch):
        encoded = []
        for key, prefix in [('query',prefix_query), ('positive',prefix_passage), ('negative',prefix_passage)]:
            tokens = model.tokenize([prefix+r[key] for r in batch])
            encoded.append(torch.nn.functional.normalize(model(tokens)['sentence_embedding'], dim=-1))
        a,p,n = encoded
        return torch.relu(.25+(1-(a*p).sum(-1))-(1-(a*n).sum(-1))).mean()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    output = home/'models/experiments'/stamp
    output.mkdir(parents=True, exist_ok=True)
    logs = []
    initial = validation_score()
    best = (initial['mrr@10'], initial['recall@5'])
    best_epoch = 0
    model.save(str(output))
    logs.append({'epoch':0, 'validation_metrics':initial})
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=.01)
    started = time.perf_counter()
    for epoch in range(1, epochs+1):
        model.train(); random.shuffle(triplets); losses = []
        for i in range(0,len(triplets),8):
            optimizer.zero_grad(); value = loss(triplets[i:i+8]); value.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(),1.0)
            optimizer.step(); losses.append(float(value.detach()))
        scores = validation_score()
        record = {'epoch':epoch, 'train_loss':float(np.mean(losses)), 'validation_metrics':scores}
        logs.append(record); print(json.dumps(record), flush=True)
        rank = (scores['mrr@10'], scores['recall@5'])
        if rank > best:
            best = rank; best_epoch = epoch; model.save(str(output))
    # End-to-end gate on development only; test is never consulted for selection.
    if corpus!='drip_r':
        validation_path=locations['reports']/f'development_{stamp}.jsonl'
        from claimguard.datasets.drip_r import write_jsonl
        write_jsonl(validation_path,validation)
    result = evaluate(home, trained=output, corpus=corpus, profile=profile, split='development', dataset=validation_path,
                      modes=['dense','rerank'], publish=False,
                      output=locations['reports']/f'training_validation_{stamp}.json')
    baseline, candidate = result['summary']['E4'], result['summary']['E5']
    eligible = (best_epoch > 0 and candidate['metrics']['mrr@10'] > baseline['metrics']['mrr@10']
                and candidate['metrics']['recall@5'] >= baseline['metrics']['recall@5'] and candidate['latency_p95_ms'] <= 3000)
    manifest = {'corpus':corpus, 'profile':profile, 'checkpoint':str(output.relative_to(home)), 'best_epoch':best_epoch,
        'production_eligible':eligible, 'automatically_promoted':False,
        'selection':'MRR@10 then Recall@5 on development; epoch 0 included; end-to-end quality and latency gate',
        'loss':'cosine triplet margin 0.25; baseline-mined hard negatives excluding all relevant references',
        'seed':seed, 'epochs':epochs, 'learning_rate':lr, 'batch_size':8, 'device':'cpu',
        'training_seconds':time.perf_counter()-started, 'sizes':{'train':len(train),'validation':len(validation),'test':len(frozen)},
        'dataset_sha256':{str(p.relative_to(home)):file_hash(p) for p in (training_path,validation_path,locations['evaluation'])},
        'original_benchmark_scenarios_in_training':0, 'logs':logs,
        'limitations':['Small policy-authored bilingual sample; no independent annotation review',
                       'Shared policy corpus; not a test of unseen-policy generalization',
                       'No refund/compliance decision labels']}
    text = json.dumps(manifest,indent=2)
    (output/'training_manifest.json').write_text(text,encoding='utf-8')
    (locations['reports']/f'training_run_{stamp}.json').write_text(text,encoding='utf-8')
    (locations['reports']/'latest_training.json').write_text(text,encoding='utf-8')
    print(json.dumps({'checkpoint':str(output),'best_epoch':best_epoch,'production_eligible':eligible}),flush=True)
    return manifest


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--home',type=Path,default=ROOT)
    p.add_argument('--epochs',type=int,default=3)
    p.add_argument('--lr',type=float,default=2e-5)
    p.add_argument('--profile',default=None)
    p.add_argument('--corpus',choices=['drip_r','novaretail'],default='drip_r')
    a=p.parse_args()
    main(a.home,a.epochs,a.lr,corpus=a.corpus,profile=a.profile)
