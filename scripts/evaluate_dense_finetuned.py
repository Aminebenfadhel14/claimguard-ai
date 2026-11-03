"""Additional embedding-only ablation; fixed checkpoint, no tuning on the test set."""
import json,statistics
from pathlib import Path
from claimguard.runtime import build
from claimguard.models import SearchRequest
from claimguard.evaluation.metrics import metrics
home=Path('.')
_,engine=build(home,embedding=str(home/'models/novaretail-embedding'),corpus='novaretail')
rows=[]
for q in [json.loads(l) for l in (home/'data/evaluation/questions.jsonl').read_text(encoding='utf-8').splitlines()]:
    if not q['relevant_sections']:continue
    trace=engine.retrieve(SearchRequest(query=q['question'],incident_date=q['incident_date'],mode='dense',top_k=10))
    refs=[h.chunk.reference() for h in trace['final']]
    rows.append({'id':q['question_id'],'ranked':refs,'metrics':metrics(refs,q['relevant_sections'])})
summary={k:statistics.mean(r['metrics'][k] for r in rows) for k in rows[0]['metrics']}
baseline=json.loads((home/'reports/retrieval_results.json').read_text(encoding='utf-8'))['summary']['E1']['metrics']
report={'baseline':baseline,'fine_tuned':summary,'delta':{k:summary[k]-baseline[k] for k in summary},'per_question':rows}
(home/'reports/dense_finetuning_comparison.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='per_question'},indent=2))
engine.index.close()
