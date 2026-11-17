import hashlib
import os
import uuid
from qdrant_client import QdrantClient, models as qm
from claimguard.models import Chunk, Hit

class PolicyIndex:
    """Named dense/sparse vectors; IDF applied once by Qdrant, RRF once by caller."""
    def __init__(self, chunks, encoder, sparse, url=None, profile=None):
        self.chunks={x.chunk_id:x for x in chunks}
        self.encoder, self.sparse = encoder, sparse
        self.profile = profile or {}
        signature = '|'.join(sorted(self.chunks)) + str(getattr(encoder,'model_name_or_path','sparse-only')) + str(self.profile)
        self.collection = 'policies_' + hashlib.sha256(signature.encode()).hexdigest()[:16]
        self.client = QdrantClient(url=url,api_key=os.getenv('QDRANT_API_KEY') or None, timeout=30) if url else QdrantClient(':memory:')
        texts=[f'{x.metadata.policy_id} {x.metadata.title}\n' +
               (f'{x.section_title or x.section}\n' if self.profile.get('section_titles',False) else '') + x.text for x in chunks]
        if not texts: raise ValueError('Cannot index an empty corpus')
        prefix=self.profile.get('dense',{}).get('passage_prefix','')
        vectors=encoder.encode([prefix+t for t in texts],normalize_embeddings=True,show_progress_bar=False) if encoder else None
        sparse_vectors=sparse.embed_documents(texts) if sparse else None
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(self.collection,
                vectors_config={'dense':qm.VectorParams(size=len(vectors[0]),distance=qm.Distance.COSINE)} if encoder else {},
                sparse_vectors_config={'bm25':qm.SparseVectorParams(modifier=qm.Modifier.IDF)} if sparse else {})
        self.client.upsert(self.collection,points=[qm.PointStruct(
            id=str(uuid.UUID(x.chunk_id[:32])),
            vector=({'dense':vectors[i].tolist()} if encoder else {}) | ({'bm25':qm.SparseVector(indices=sparse_vectors[i].indices,values=sparse_vectors[i].values)} if sparse else {}),
            payload={'chunk_id':x.chunk_id,'access':x.metadata.access_level,'category':x.metadata.category,
                     'start':x.metadata.effective_date.toordinal() if x.metadata.effective_date else 1,
                     'end':(x.metadata.effective_until.toordinal() if x.metadata.effective_until else 3652059)})
            for i,x in enumerate(chunks)],wait=True)
    def search(self, query, incident_date, mode, top_k=20, access=('public','internal'), category=None):
        conditions=[qm.FieldCondition(key='access',match=qm.MatchAny(any=list(access))),
                    qm.FieldCondition(key='start',range=qm.Range(lte=incident_date.toordinal())),
                    qm.FieldCondition(key='end',range=qm.Range(gt=incident_date.toordinal()))]
        if category: conditions.append(qm.FieldCondition(key='category',match=qm.MatchValue(value=category)))
        if mode=='dense':
            if self.encoder is None: raise RuntimeError('Dense model not loaded')
            prefix=self.profile.get('dense',{}).get('query_prefix','')
            vector=self.encoder.encode(prefix+query,normalize_embeddings=True).tolist(); name='dense'
        elif mode=='sparse':
            if self.sparse is None: raise RuntimeError('Sparse model not loaded')
            s=self.sparse.embed_query(query); vector=qm.SparseVector(indices=s.indices,values=s.values); name='bm25'
        else: raise ValueError('Index mode must be dense or sparse')
        points=self.client.query_points(self.collection,query=vector,using=name,
                    query_filter=qm.Filter(must=conditions),limit=top_k).points
        return [Hit(chunk=self.chunks[p.payload['chunk_id']],score=p.score,stage=mode) for p in points
                if mode!='sparse' or p.score>0]
    def close(self): self.client.close()
