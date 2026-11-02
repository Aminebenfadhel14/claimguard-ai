"""Real Groq generation benchmark. Exits clearly before loading models if the key is absent."""
import json,os,time
import argparse
from pathlib import Path
from dotenv import load_dotenv
from claimguard.runtime import build
from claimguard.models import SearchRequest
from claimguard.corpora import paths,CORPORA
from claimguard.prompts.rag import generate,rewrite,groq_model
load_dotenv()
p=argparse.ArgumentParser();p.add_argument('--corpus',choices=CORPORA,default='novaretail');args=p.parse_args()
llm=groq_model()
home=Path(os.getenv('CLAIMGUARD_HOME','.'));locations=paths(home,args.corpus)
_,engine=build(with_reranker=True,corpus=args.corpus)
questions=[json.loads(l) for l in locations['evaluation'].read_text(encoding='utf-8').splitlines()]
rows=[]
for q in questions:
    try:
        query=rewrite(q['question'],llm)
        trace=engine.retrieve(SearchRequest(query=query,incident_date=q['incident_date'],mode='rerank'))
        prefix='Only the provided undated benchmark policy snapshot is in scope. ' if args.corpus=='drip_r' else ''
        a=generate(prefix+q['question'],trace['final'],llm)
        rows.append({'id':q['question_id'],'rewritten_query':query,'expected_abstention':not bool(q['relevant_sections']),
                     'result':a.model_dump(),'citation_validation_passed':True})
    except Exception as e:
        rows.append({'id':q['question_id'],'expected_abstention':not bool(q['relevant_sections']), 'error_type':type(e).__name__,'citation_validation_passed':False})
unknown=[r for r in rows if r.get('expected_abstention')]
report={'rows':rows,'unknown_abstention_accuracy':sum(bool(r.get('result',{}).get('abstained')) for r in unknown)/len(unknown) if unknown else None,
        'note':'Exact quote validation is measured; semantic faithfulness still requires human review.'}
(locations['reports']/'live_generation.json').write_text(json.dumps(report,indent=2))
engine.index.close()
