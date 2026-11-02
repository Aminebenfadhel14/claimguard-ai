"""A real initialize -> list_tools -> call_tool demonstration over subprocess stdio."""
import asyncio,json,os,sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def demonstrate():
    home=Path(os.getenv('CLAIMGUARD_HOME','.')).resolve()
    params=StdioServerParameters(command=sys.executable,args=['-m','claimguard.mcp.server'],env=dict(os.environ))
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            listed=await session.list_tools()
            names=[x.name for x in listed.tools]
            assert {'search_policies','get_policy_section'}<=set(names)
            calls=[]
            for name,args in [
                ('search_policies',{'query':'My defective phone was refused for exchange four days after purchase.', 'incident_date':'2026-11-02','top_k':3}),
                ('get_policy_section',{'policy_id':'RETURN-001','version':'2.0','section':'4.2'}),
                ('compare_policy_versions',{'policy_id':'RETURN-001','version_a':'1.0','version_b':'2.0'})]:
                result=await session.call_tool(name,args)
                assert not result.isError, result
                calls.append({'tool':name,'arguments':args,'result':result.model_dump(mode='json')})
    report={'transport':'stdio','discovered_tools':names,'successful_calls':len(calls),'calls':calls}
    (home/'reports/mcp_demo.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'tools':names,'successful_calls':len(calls)}))
if __name__=='__main__':asyncio.run(demonstrate())
