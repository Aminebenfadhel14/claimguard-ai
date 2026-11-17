from claimguard.models import Hit
from claimguard.retrieval.fusion import rrf

class RetrievalEngine:
    def __init__(self, index, reranker=None, profile=None):
        self.index, self.reranker = index, reranker
        self.profile = profile or {}
    def retrieve(self, req, access=('public','internal')):
        import time
        started=time.perf_counter()
        args=dict(query=req.query, incident_date=req.incident_date, top_k=max(req.top_k,self.profile.get('candidate_k',20)), access=access, category=req.category)
        dense=self.index.search(**args,mode='dense') if req.mode!='sparse' else []
        sparse=self.index.search(**args,mode='sparse') if req.mode!='dense' else []
        fused=rrf([dense,sparse],k=self.profile.get('rrf_k',60)) if req.mode in {'hybrid','rerank'} else []
        ranked=[]
        if req.mode=='rerank':
            if self.reranker is None: raise RuntimeError('CrossEncoder required for rerank mode')
            # Cover distinct sections before spending remaining budget on extra windows.
            # Otherwise a long section can crowd all evidence out of the candidate pool.
            representatives=[]; remaining=[]; represented=set()
            for hit in fused:
                reference=hit.chunk.reference()
                if reference in represented: remaining.append(hit)
                else: representatives.append(hit); represented.add(reference)
            candidates=(representatives+remaining)[:max(req.top_k,self.profile.get('rerank_k',20))]
            scores=self.reranker.predict([(req.query,h.chunk.text) for h in candidates],show_progress_bar=False,batch_size=self.profile.get('batch_size',8)) if fused else []
            ranked=sorted([Hit(chunk=h.chunk,score=float(s),stage='reranker') for h,s in zip(candidates,scores)],
                          key=lambda h:(-h.score,h.chunk.chunk_id))
        ordered={'dense':dense,'sparse':sparse,'hybrid':fused,'rerank':ranked}[req.mode]
        seen=set(); final=[]
        for hit in ordered:
            reference=hit.chunk.reference()
            if reference in seen: continue
            seen.add(reference); final.append(hit)
            if len(final)==req.top_k: break
        return {'query':req.query,'dense':dense,'sparse':sparse,'rrf':fused,'reranker':ranked,'final':final,
                'diagnostics':{'profile':self.profile.get('name','custom'),
                    'profile_fingerprint':self.profile.get('fingerprint'), 'index':getattr(self.index,'collection',None),
                    'latency_ms':(time.perf_counter()-started)*1000, 'ranking_unit':'section', 'engine_ready':True}}
