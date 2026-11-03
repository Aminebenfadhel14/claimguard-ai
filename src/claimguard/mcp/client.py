"""A real initialize -> list_tools -> call_tool demonstration over subprocess stdio."""
import asyncio,json,os,sys
import argparse
from claimguard.corpora import paths, CORPORA
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def demonstrate(corpus='novaretail'):
    home=Path(os.getenv('CLAIMGUARD_HOME','.')).resolve()
    params=StdioServerParameters(command=sys.executable,args=['-m','claimguard.mcp.server'],env=dict(os.environ)|{'CLAIMGUARD_CORPUS':corpus})
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            listed=await session.list_tools()
            names=[x.name for x in listed.tools]
            assert {'search_policies','get_policy_section'}<=set(names)
            calls=[]
            operations=[
                ('search_policies',{'query':'My defective phone was refused for exchange four days after purchase.', 'incident_date':'2026-11-02','top_k':3}),
                ('get_policy_section',{'policy_id':'RETURN-001','version':'2.0','section':'4.2'}),
                ('compare_policy_versions',{'policy_id':'RETURN-001','version_a':'1.0','version_b':'2.0'})]
            if corpus=='drip_r':
                operations=[('search_policies',{'query':'How should I return a gift without the order number?', 'incident_date':'2026-11-02','top_k':3}),
                    ('get_policy_section',{'policy_id':'DRIP-001','version':'1.0','section':'1.15'})]
            for name,args in operations:
                result=await session.call_tool(name,args)
                assert not result.isError, result
                calls.append({'tool':name,'arguments':args,'result':result.model_dump(mode='json')})
    report={'corpus':corpus,'transport':'stdio','discovered_tools':names,'successful_calls':len(calls),'calls':calls}
    (paths(home,corpus)['reports']/'mcp_demo.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'tools':names,'successful_calls':len(calls)}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--corpus',choices=CORPORA,default='novaretail')
    asyncio.run(demonstrate(p.parse_args().corpus))
