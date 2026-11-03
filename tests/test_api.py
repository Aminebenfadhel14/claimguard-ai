from fastapi.testclient import TestClient
from claimguard.api import create_app

class Engine:
    def retrieve(self,req,access):
        assert access==('public','internal')
        return {'query':req.query,'final':[]}

BODY={'query':'exchange policy','incident_date':'2026-11-02'}
def test_api_fails_closed(monkeypatch):
    monkeypatch.delenv('CLAIMGUARD_API_TOKEN',raising=False)
    with TestClient(create_app(Engine())) as c:
        assert c.post('/search',json=BODY).status_code==503
    monkeypatch.setenv('CLAIMGUARD_API_TOKEN','test-secret')
    with TestClient(create_app(Engine())) as c:
        assert c.post('/search',json=BODY).status_code==401
        assert c.post('/search',json=BODY,headers={'Authorization':'Bearer test-secret'}).status_code==200
        assert c.post('/search',json=BODY|{'top_k':1000},headers={'Authorization':'Bearer test-secret'}).status_code==422
