"""Retrieve policy evidence for all 400 visible inputs, without asserting a compliance verdict."""
import argparse
import json
import time
from pathlib import Path
from claimguard.datasets.drip_r import read_jsonl, agent_input, query_for, write_jsonl
from claimguard.models import SearchRequest
from claimguard.runtime import build

def main(home):
    rows=read_jsonl(home/'data/external/drip_r/scenarios.jsonl')
    _,engine=build(home,corpus='drip_r',with_reranker=True)
    results=[];start=time.perf_counter()
    try:
        for i,row in enumerate(rows,1):
            trace=engine.retrieve(SearchRequest(query=query_for(row),incident_date='2026-11-02',mode='rerank',top_k=5))
            hits=[{'reference':h.chunk.reference(),'chunk_id':h.chunk.chunk_id,'text':h.chunk.text,
                   'score':h.score,'source_file':h.chunk.source_file,'source_line_start':h.chunk.source_line_start,
                   'source_line_end':h.chunk.source_line_end,'sha256':h.chunk.file_hash} for h in trace['final']]
            results.append({**agent_input(row),'retrieved_evidence':hits,
                'status':'EVIDENCE_RETRIEVED_ONLY','compliance_decision':None,
                'note':'Snapshot retrieval only. No verified purchase facts, LLM analysis or final decision.'})
            if i%50==0:print(f'Retrieved {i}/{len(rows)}',flush=True)
    finally:engine.index.close()
    out=home/'reports/drip_r';write_jsonl(out/'scenario_retrieval.jsonl',results)
    (out/'batch_run.json').write_text(json.dumps({'corpus':'drip_r','scenarios_processed':len(results),
        'seconds':time.perf_counter()-start,'mode':'baseline hybrid + reranker',
        'original_private_fields_exposed':False,'llm_generation_executed':False,
        'compliance_decisions_produced':0},indent=2),encoding='utf-8')

if __name__=='__main__':main(Path(__file__).resolve().parents[1])
