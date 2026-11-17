"""Local acceptance evidence: real models, API authorization and both corpora."""
import json
import os
import secrets
import socket
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from claimguard.settings import ROOT
from claimguard.runtime import build
from claimguard.models import SearchRequest
from claimguard.api import create_app


def verify():
    results=[]
    original=socket.socket.connect
    def deny(*args,**kwargs): raise AssertionError('Unexpected network connection during offline verification')
    socket.socket.connect=deny
    try:
        for corpus in ('drip_r','novaretail'):
            _,engine=build(ROOT,corpus=corpus,mode='rerank')
            try:
                for mode in ('dense','sparse','hybrid','rerank'):
                    trace=engine.retrieve(SearchRequest(query='defective product return',incident_date='2026-11-02',mode=mode))
                    refs=[h.chunk.reference() for h in trace['final']]
                    assert refs and len(refs)==len(set(refs))
                    results.append({'surface':'engine','corpus':corpus,'mode':mode,'references':refs,'diagnostics':trace['diagnostics']})
            finally: engine.index.close()
        # API creates and caches the requested mode lazily; a temporary test token never leaves this process.
        token=secrets.token_urlsafe(32)
        previous_token=os.environ.get('CLAIMGUARD_API_TOKEN')
        os.environ['CLAIMGUARD_API_TOKEN']=token
        # Windows asyncio implements its self-pipe with a loopback socket pair.
        def local_only(sock,address):
            if isinstance(address,tuple) and address[0] in ('127.0.0.1','::1'):
                return original(sock,address)
            raise AssertionError('Unexpected external connection during API verification')
        socket.socket.connect=local_only
        try:
            with TestClient(create_app()) as client:
                assert client.get('/health').status_code==200
                assert client.get('/ready').status_code==401
                auth={'Authorization':'Bearer '+token}
                assert not client.get('/ready',headers=auth).json()['engine_ready']
                for mode in ('dense','sparse','hybrid','rerank'):
                    response=client.post('/search',headers=auth,json={'query':'gift return policy','incident_date':'2026-11-02','mode':mode})
                    assert response.status_code==200,response.text
                    assert response.json()['final']
                    results.append({'surface':'api','mode':mode,'status_code':response.status_code})
                assert client.get('/ready',headers=auth).json()['engine_ready']
        finally:
            if previous_token is None: os.environ.pop('CLAIMGUARD_API_TOKEN',None)
            else: os.environ['CLAIMGUARD_API_TOKEN']=previous_token
    finally: socket.socket.connect=original
    report={'created_at':datetime.now(timezone.utc).isoformat(),'engine_network_disabled':True,
            'api_external_network_disabled':True,'api_loopback_allowed':'Windows asyncio self-pipe only','results':results}
    (ROOT/'reports/local_acceptance.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'checks':len(results),'offline':True}))


if __name__=='__main__': verify()
