"""Local stdio server using the official MCP Python SDK. No network exposure."""
import os
from datetime import date
from functools import lru_cache
from mcp.server.fastmcp import FastMCP
from claimguard.models import SearchRequest
from claimguard.runtime import build

server=FastMCP('ClaimGuard AI')
# Permissions are fixed by the local process, never supplied by a model tool argument.
ACCESS=('public','internal')
@lru_cache(maxsize=1)
def services():
    return build(with_reranker=True)

@server.tool()
def search_policies(query: str, incident_date: str, category: str | None=None, top_k: int=5) -> dict:
    """Retrieve evidence from the configured corpus. DRIP-R is an undated snapshot, not historical policy advice."""
    req=SearchRequest(query=query,incident_date=incident_date,category=category,top_k=top_k,mode='rerank')
    _,engine=services()
    trace=engine.retrieve(req,access=ACCESS)
    return {'query':query,'incident_date':incident_date,'results':[h.model_dump(mode='json') for h in trace['final']]}

@server.tool()
def get_policy_section(policy_id: str, version: str, section: str) -> dict:
    """Return an exact authorized policy version/section, including pages and hashes."""
    catalog,_=services()
    chunks=[c for c in catalog.chunks(access=ACCESS) if c.metadata.policy_id==policy_id and c.metadata.version==version and c.section==section]
    if not chunks: raise ValueError('Unknown or unauthorized policy section')
    return {'reference':f'{policy_id}@{version}#{section}','chunks':[c.model_dump(mode='json') for c in chunks]}

@server.tool()
def compare_policy_versions(policy_id: str, version_a: str, version_b: str) -> dict:
    """Compare two authorized policy versions without choosing a decision for an incident."""
    catalog,_=services()
    for version in (version_a,version_b):
        if not any(c.metadata.policy_id==policy_id and c.metadata.version==version for c in catalog.chunks(access=ACCESS)):
            raise ValueError('Unknown or unauthorized policy version')
    return {'policy_id':policy_id,'versions':[version_a,version_b],'diff':catalog.compare(policy_id,version_a,version_b)}

if __name__=='__main__':server.run(transport='stdio')
