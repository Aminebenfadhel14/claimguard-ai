"""E1-E5 measured retrieval. No invented generation/faithfulness/abstention scores."""
import argparse,hashlib,json,statistics,time,sys
from pathlib import Path
from claimguard.models import SearchRequest
from claimguard.runtime import build
from claimguard.evaluation.metrics import metrics

def evaluate(home, trained=None):
    data=home/'data/evaluation/questions.jsonl'
    questions=[json.loads(l) for l in data.read_text().splitlines()]
    rows=[]; summary={}; started=time.time()
    for label,embedding,modes in [('baseline',None,['dense','sparse','hybrid','rerank'])]+([('fine_tuned',str(trained),['rerank'])] if trained else []):
        catalog,engine=build(home,embedding=embedding,with_reranker=True)
        for mode in modes:
            experiment={'dense':'E1','sparse':'E2','hybrid':'E3','rerank':'E4'}[mode] if label=='baseline' else 'E5'
            measurements=[]; durations=[]; unsupported=[]
            for q in questions:
                req=SearchRequest(query=q['question'],incident_date=q['incident_date'],mode=mode,top_k=10)
                t=time.perf_counter();trace=engine.retrieve(req);elapsed=(time.perf_counter()-t)*1000
                refs=[h.chunk.reference() for h in trace['final']]
                row={'experiment':experiment,'question_id':q['question_id'],'difficulty':q['difficulty'],
                     'expected':q['relevant_sections'],'ranked_sections':refs,'latency_ms':elapsed,
                     'top_score':trace['final'][0].score if trace['final'] else None}
                if q['relevant_sections']:
                    m=metrics(refs,q['relevant_sections']); measurements.append(m);durations.append(elapsed);row['metrics']=m
                else:
                    unsupported.append(row)
                rows.append(row)
            summary[experiment]={'mode':mode,'embedding':label,'answerable_questions':len(measurements),
                'metrics':{k:statistics.mean(m[k] for m in measurements) for k in measurements[0]},
                'latency_mean_ms':statistics.mean(durations),'latency_p95_ms':sorted(durations)[int(.95*(len(durations)-1))],
                'unanswerable_questions':len(unsupported),'abstention_accuracy':None,
                'abstention_note':'Not measured: live LLM unavailable. Retrieval scores do not establish answerability.'}
        engine.index.close()
    result={'dataset_sha256':hashlib.sha256(data.read_bytes()).hexdigest(),'total_seconds':time.time()-started,
            'seed':42,'benchmark':'synthetic, author-reviewed; no independent human annotation',
            'summary':summary,'per_question':rows}
    (home/'reports/retrieval_results.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(summary,indent=2))
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--home',type=Path,default=Path('.'));p.add_argument('--trained',type=Path)
    a=p.parse_args();evaluate(a.home.resolve(),a.trained)
