"""E1-E5 measured retrieval. No invented generation/faithfulness/abstention scores."""
import argparse,hashlib,json,statistics,time,sys
from pathlib import Path
from claimguard.models import SearchRequest
from claimguard.runtime import build
from claimguard.evaluation.metrics import metrics
from claimguard.corpora import paths, CORPORA
from collections import defaultdict

def evaluate(home, trained=None, corpus='novaretail'):
    locations=paths(home,corpus)
    data=locations['evaluation']
    questions=[json.loads(l) for l in data.read_text(encoding='utf-8').splitlines()]
    rows=[]; summary={}; started=time.time()
    for label,embedding,modes in [('baseline',None,['dense','sparse','hybrid','rerank'])]+([('fine_tuned',str(trained),['dense','rerank'] if corpus=='drip_r' else ['rerank'])] if trained else []):
        catalog,engine=build(home,embedding=embedding,with_reranker=True,corpus=corpus)
        for mode in modes:
            experiment={'dense':'E1','sparse':'E2','hybrid':'E3','rerank':'E4'}[mode] if label=='baseline' else ('FT_DENSE' if mode=='dense' else 'E5')
            measurements=[]; durations=[]; unsupported=[]; grouped=defaultdict(list)
            for q in questions:
                req=SearchRequest(query=q['question'],incident_date=q['incident_date'],mode=mode,top_k=10)
                t=time.perf_counter();trace=engine.retrieve(req);elapsed=(time.perf_counter()-t)*1000
                refs=[h.chunk.reference() for h in trace['final']]
                row={'experiment':experiment,'question_id':q['question_id'],'difficulty':q['difficulty'],'scenario_group':q.get('scenario_group',q['question_id']),
                     'expected':q['relevant_sections'],'ranked_sections':refs,'latency_ms':elapsed,
                     'top_score':trace['final'][0].score if trace['final'] else None}
                if q['relevant_sections']:
                    m=metrics(refs,q['relevant_sections']); measurements.append(m);durations.append(elapsed);row['metrics']=m
                    grouped[row['scenario_group']].append(m)
                else:
                    unsupported.append(row)
                rows.append(row)
            summary[experiment]={'mode':mode,'embedding':label,'answerable_questions':len(measurements),
                'metrics':{k:statistics.mean(m[k] for m in measurements) for k in measurements[0]},
                'task_macro_metrics':{k:statistics.mean(statistics.mean(m[k] for m in group) for group in grouped.values()) for k in measurements[0]},
                'task_groups':len(grouped),
                'latency_mean_ms':statistics.mean(durations),'latency_p95_ms':sorted(durations)[int(.95*(len(durations)-1))],
                'unanswerable_questions':len(unsupported),'abstention_accuracy':None,
                'abstention_note':'Not measured: live LLM unavailable. Retrieval scores do not establish answerability.'}
        engine.index.close()
    result={'dataset_sha256':hashlib.sha256(data.read_bytes()).hexdigest(),'total_seconds':time.time()-started,
            'seed':42,'corpus':corpus,'benchmark':'synthetic; project-authored retrieval labels; no independent human annotation',
            'summary':summary,'per_question':rows}
    locations['reports'].mkdir(parents=True,exist_ok=True)
    (locations['reports']/'retrieval_results.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(summary,indent=2))
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--home',type=Path,default=Path('.'));p.add_argument('--trained',type=Path)
    p.add_argument('--corpus',choices=CORPORA,default='novaretail')
    a=p.parse_args();evaluate(a.home.resolve(),a.trained,a.corpus)
