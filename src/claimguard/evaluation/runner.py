"""Versioned, section-level evaluation without modifying the frozen test or baseline."""
import hashlib
import json
import statistics
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from claimguard.models import SearchRequest
from claimguard.runtime import build
from claimguard.settings import load_profile, file_hash
from claimguard.corpora import paths
from claimguard.datasets.drip_r import read_jsonl
from claimguard.evaluation.metrics import metrics

EXPERIMENTS = {'dense': 'E1', 'sparse': 'E2', 'hybrid': 'E3', 'rerank': 'E4'}


def archive_baseline(home, corpus):
    import shutil
    reports = paths(home, corpus)['reports']
    destination = reports / 'baselines/v1'
    if destination.exists(): return
    destination.mkdir(parents=True)
    for name in ('retrieval_results.json', 'RESULTS.md', 'training_run.json', 'dense_finetuning_comparison.json'):
        src = reports / name
        if src.exists(): shutil.copyfile(src, destination / name)


def aggregate(rows):
    answerable = [r for r in rows if 'metrics' in r]
    result = {'answerable_questions': len(answerable), 'unanswerable_questions': len(rows)-len(answerable),
              'metrics': {}, 'task_macro_metrics': {}, 'by_language': {},
              'abstention_accuracy': None, 'abstention_note': 'Retrieval only; LLM abstention is not evaluated.'}
    if not answerable: return result
    result['metrics'] = {k: statistics.mean(r['metrics'][k] for r in answerable) for k in answerable[0]['metrics']}
    groups = defaultdict(list)
    languages = defaultdict(list)
    for r in answerable:
        groups[r['scenario_group']].append(r)
        languages[r['language']].append(r)
    result['task_macro_metrics'] = {k: statistics.mean(statistics.mean(r['metrics'][k] for r in group) for group in groups.values()) for k in result['metrics']}
    result['task_groups'] = len(groups)
    result['by_language'] = {lang: {'count': len(group), 'metrics': {k: statistics.mean(r['metrics'][k] for r in group) for k in result['metrics']}} for lang, group in languages.items()}
    durations = [r['latency_ms'] for r in rows]
    result.update(latency_mean_ms=statistics.mean(durations), latency_median_ms=statistics.median(durations),
                  latency_p95_ms=sorted(durations)[max(0, __import__('math').ceil(.95*len(durations))-1)])
    return result


def validate_split(home, corpus, questions, split):
    if split != 'development': return
    frozen = read_jsonl(paths(home, corpus)['evaluation'])
    test_groups = {r['scenario_group'] for r in frozen}
    test_queries = {r['question'].strip().casefold() for r in frozen}
    for r in questions:
        if r['scenario_group'] in test_groups or r['question'].strip().casefold() in test_queries:
            raise ValueError('Development/test leakage')
        if r.get('scenario_id') or r.get('task_id'):
            raise ValueError('Original benchmark situations are evaluation-only')


def evaluate(home, trained=None, corpus='novaretail', profile=None, split='test', dataset=None,
             modes=None, output=None, publish=True):
    home = Path(home).resolve()
    locations = paths(home, corpus)
    profile = load_profile(home, profile) if not isinstance(profile, dict) else dict(profile)
    # Tuned dictionaries must have their own identity.
    profile['fingerprint'] = hashlib.sha256(json.dumps({k:v for k,v in profile.items() if k!='fingerprint'}, sort_keys=True).encode()).hexdigest()
    if split=='development' and corpus!='drip_r' and dataset is None:
        raise ValueError('Provide --dataset for a separate NovaRetail development set; frozen test cannot be used for tuning.')
    data = Path(dataset) if dataset else (home/'data/drip_r/development/questions.jsonl' if split=='development' and corpus=='drip_r' else locations['evaluation'])
    questions = read_jsonl(data)
    validate_split(home, corpus, questions, split)
    archive_baseline(home, corpus)
    rows, summary = [], {}
    started = time.perf_counter()
    for label, embedding, selected_modes in [('baseline', None, modes or list(EXPERIMENTS))] + ([('fine_tuned', trained, ['dense', 'rerank'])] if trained else []):
        # Load once for the experiment suite; production loads per selected mode.
        _, engine = build(home, embedding=embedding, corpus=corpus, mode='rerank', profile=profile)
        try:
            for mode in selected_modes:
                experiment = EXPERIMENTS[mode] if label=='baseline' else ('FT_DENSE' if mode=='dense' else 'E5')
                engine.retrieve(SearchRequest(query=questions[0]['question'], incident_date=questions[0]['incident_date'], mode=mode, top_k=10))
                measured = []
                for q in questions:
                    req = SearchRequest(query=q['question'], incident_date=q['incident_date'], mode=mode, top_k=10)
                    t = time.perf_counter()
                    trace = engine.retrieve(req)
                    elapsed = (time.perf_counter()-t)*1000
                    refs = [h.chunk.reference() for h in trace['final']]
                    row = {'experiment': experiment, 'question_id': q['question_id'], 'scenario_group': q.get('scenario_group', q['question_id']),
                           'language': q.get('language', 'en'), 'expected': q['relevant_sections'], 'ranked_sections': refs,
                           'latency_ms': elapsed, 'top_score': trace['final'][0].score if trace['final'] else None}
                    if q['relevant_sections']: row['metrics'] = metrics(refs, q['relevant_sections'])
                    measured.append(row)
                summary[experiment] = aggregate(measured) | {'mode': mode, 'embedding': label}
                rows.extend(measured)
                print(json.dumps({'experiment': experiment, **summary[experiment]}, ensure_ascii=True), flush=True)
        finally: engine.index.close()
    source_hashes = {p.name:file_hash(p) for p in locations['policies'].glob('*') if p.is_file()}
    result = {'schema_version': 2, 'created_at': datetime.now(timezone.utc).isoformat(), 'corpus': corpus, 'split': split,
              'dataset_sha256': file_hash(data), 'profile': profile, 'profile_fingerprint': profile['fingerprint'],
              'ranking_unit': 'section', 'seed': 42, 'total_seconds': time.perf_counter()-started,
              'source_sha256': source_hashes,
              'benchmark': 'Project-authored provisional relevance labels; independent human review required.',
              'latency_protocol': 'CPU; one warmup per mode; excludes model/index loading and LLM',
              'summary': summary, 'per_question': rows}
    if trained:
        checkpoint = Path(trained).resolve()
        result['trained_checkpoint'] = {'path':str(checkpoint),
            'weights_sha256':{p.name:file_hash(p) for p in checkpoint.glob('*.safetensors')}}
    run_dir = locations['reports']/'runs'
    run_dir.mkdir(parents=True, exist_ok=True)
    output = Path(output) if output else run_dir/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'_'+split+'_'+profile['name']+'.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    if publish and split=='test':
        (locations['reports']/'latest.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    return result
