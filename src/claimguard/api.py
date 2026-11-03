"""Academic search API. Single local service identity; not a multi-tenant complaint service."""
import os,secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI,Depends,Header,HTTPException
from claimguard.models import SearchRequest
from claimguard.runtime import build

def authorized(authorization: str | None=Header(default=None)):
    expected=os.getenv('CLAIMGUARD_API_TOKEN')
    if not expected: raise HTTPException(503,'API authentication is not configured')
    token=(authorization or '').removeprefix('Bearer ')
    if not secrets.compare_digest(token,expected): raise HTTPException(401,'Authentication required')
    return 'local-service'

def create_app(engine=None):
    @asynccontextmanager
    async def lifespan(app):
        if engine is not None:app.state.engine=engine
        else:_,app.state.engine=build(with_reranker=True)
        yield
        if engine is None:app.state.engine.index.close()
    app=FastAPI(title='ClaimGuard AI — academic search API',lifespan=lifespan)
    @app.get('/health')
    def health():return {'status':'ok'}
    @app.post('/search',dependencies=[Depends(authorized)])
    def search(req: SearchRequest):
        try:
            result=app.state.engine.retrieve(req,access=('public','internal'))
            return {k:[h.model_dump(mode='json') for h in v] if isinstance(v,list) else v for k,v in result.items()}
        except Exception:
            raise HTTPException(503,'Retrieval service unavailable') from None
    return app
app=create_app()
