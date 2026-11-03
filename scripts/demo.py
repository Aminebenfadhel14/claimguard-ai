import argparse,json
from claimguard.models import SearchRequest
from claimguard.runtime import build
p=argparse.ArgumentParser();p.add_argument('--query',default='My defective phone was refused for exchange four days after purchase.');p.add_argument('--date',default='2026-11-02');p.add_argument('--mode',choices=['dense','sparse','hybrid','rerank'],default='rerank');p.add_argument('--corpus',choices=['novaretail','drip_r'],default='novaretail');a=p.parse_args()
_,engine=build(with_reranker=a.mode=='rerank',corpus=a.corpus)
trace=engine.retrieve(SearchRequest(query=a.query,incident_date=a.date,mode=a.mode))
print(json.dumps({k:[h.model_dump(mode='json') for h in v] if isinstance(v,list) else v for k,v in trace.items()},indent=2))
engine.index.close()
