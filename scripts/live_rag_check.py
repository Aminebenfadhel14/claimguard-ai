"""Real optional Groq check. Errors remain in the denominator; never invents scores."""
import argparse
import json
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from claimguard.settings import ROOT, load_profile, file_hash
from claimguard.runtime import build
from claimguard.models import SearchRequest
from claimguard.corpora import paths
from claimguard.datasets.drip_r import read_jsonl
from claimguard.prompts.rag import generate, rewrite, groq_model
from claimguard.diagnostics import record_error


def run(corpus, sample=None, profile=None):
    load_dotenv(ROOT/'.env')
    locations=paths(ROOT,corpus)
    output=locations['reports']/'latest_generation.json'
    if not os.getenv('GROQ_API_KEY'):
        result={'status':'not_evaluated','reason':'GROQ_API_KEY absent','rows':[], 'unknown_abstention_accuracy':None}
        output.write_text(json.dumps(result,indent=2),encoding='utf-8')
        print('Groq non configuré : génération réelle non évaluée.')
        return result
    llm=groq_model()
    _,engine=build(ROOT,mode='rerank',corpus=corpus,profile=profile)
    questions=read_jsonl(locations['evaluation'])
    if sample is not None:
        questions=[q for q in questions if q['relevant_sections']][:sample]+[q for q in questions if not q['relevant_sections']]
    rows=[]
    try:
        for q in questions:
            row={'id':q['question_id'],'expected_abstention':not bool(q['relevant_sections'])}
            try:
                # Failure of a provider rewrite does not prevent retrieval of the original.
                search_query=q['question']
                try: search_query=rewrite(search_query,llm)
                except Exception: row['rewrite_error_id']=record_error(ROOT,'live_rewrite')
                trace=engine.retrieve(SearchRequest(query=search_query,incident_date=q['incident_date'],mode='rerank'))
                prefix='Only the provided undated benchmark policy snapshot is in scope. ' if corpus=='drip_r' else ''
                answer=generate(prefix+q['question'],trace['final'],llm)
                row.update(result=answer.model_dump(),citation_validation_passed=True)
            except Exception as exc:
                row.update(error_type=type(exc).__name__,error_id=record_error(ROOT,'live_generation'),citation_validation_passed=False)
            rows.append(row)
            print(json.dumps({'id':row['id'],'success':'result' in row}),flush=True)
    finally: engine.index.close()
    unknown=[r for r in rows if r['expected_abstention']]
    report={'status':'evaluated','created_at':datetime.now(timezone.utc).isoformat(), 'corpus':corpus,
            'sample_answerable':sample,'dataset_sha256':file_hash(locations['evaluation']), 'profile':load_profile(ROOT,profile),
            'rows':rows, 'successful_generations':sum('result' in r for r in rows),
            'unknown_abstention_accuracy':sum(bool(r.get('result',{}).get('abstained')) for r in unknown)/len(unknown) if unknown else None,
            'note':'Exact quotations validated; semantic faithfulness and claim coverage require independent review. Errors remain in the denominator.'}
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--corpus',choices=['novaretail','drip_r'],default='drip_r')
    p.add_argument('--profile',default=None)
    p.add_argument('--sample',type=int,help='Number of answerable cases; all unanswerable cases are retained')
    a=p.parse_args()
    run(a.corpus,a.sample,a.profile)
