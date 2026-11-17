"""Academic search API. Single local service identity; not a multi-tenant complaint service."""
import os,secrets
from pathlib import Path
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI,Depends,Header,HTTPException
from claimguard.models import SearchRequest
from claimguard.runtime import build
from claimguard.settings import ROOT, project_home, default_corpus
from claimguard.diagnostics import readiness, record_error

def authorized(authorization: str | None=Header(default=None)):
    expected=os.getenv('CLAIMGUARD_API_TOKEN')
    if not expected: raise HTTPException(503,'API authentication is not configured')
    token=(authorization or '').removeprefix('Bearer ')
    if not secrets.compare_digest(token,expected): raise HTTPException(401,'Authentication required')
    return 'local-service'

def create_app(engine=None):
    home=project_home()
    load_dotenv(home/'.env')
    @asynccontextmanager
    async def lifespan(app):
        if engine is None:
            from claimguard.runtime import initialize_libraries
            initialize_libraries()
        app.state.engines={}
        app.state.engine=engine
        yield
        for loaded in app.state.engines.values(): loaded.index.close()
    app=FastAPI(title='ClaimGuard AI — academic search API',lifespan=lifespan)
    @app.get('/health')
    def health():return {'status':'ok'}
    @app.get('/ready',dependencies=[Depends(authorized)])
    def ready():
        status=readiness(home,default_corpus())
        status['engine_ready']=bool(app.state.engines) or engine is not None
        return status
    @app.post('/search',dependencies=[Depends(authorized)])
    def search(req: SearchRequest):
        try:
            selected=app.state.engine
            if selected is None:
                if req.mode not in app.state.engines:
                    _,app.state.engines[req.mode]=build(home,mode=req.mode)
                selected=app.state.engines[req.mode]
            result=selected.retrieve(req,access=('public','internal'))
            return {k:[h.model_dump(mode='json') for h in v] if isinstance(v,list) else v for k,v in result.items()}
        except Exception:
            error_id=record_error(home,'api_search')
            raise HTTPException(503,{'message':'Retrieval service unavailable','error_id':error_id}) from None
    return app
app=create_app()
