from claimguard.models import Hit
from claimguard.retrieval.fusion import rrf

class RetrievalEngine:
    def __init__(self, index, reranker=None):
        self.index, self.reranker = index, reranker
    def retrieve(self, req, access=('public','internal')):
        args=dict(query=req.query, incident_date=req.incident_date, top_k=20, access=access, category=req.category)
        dense=self.index.search(**args,mode='dense') if req.mode!='sparse' else []
        sparse=self.index.search(**args,mode='sparse') if req.mode!='dense' else []
        fused=rrf([dense,sparse],k=60) if req.mode in {'hybrid','rerank'} else []
        ranked=[]
        if req.mode=='rerank':
            if self.reranker is None: raise RuntimeError('CrossEncoder required for rerank mode')
            scores=self.reranker.predict([(req.query,h.chunk.text) for h in fused[:20]],show_progress_bar=False)
            ranked=sorted([Hit(chunk=h.chunk,score=float(s),stage='reranker') for h,s in zip(fused[:20],scores)],
                          key=lambda h:(-h.score,h.chunk.chunk_id))
        final={'dense':dense,'sparse':sparse,'hybrid':fused,'rerank':ranked}[req.mode][:req.top_k]
        return {'query':req.query,'dense':dense,'sparse':sparse,'rrf':fused,'reranker':ranked,'final':final}
