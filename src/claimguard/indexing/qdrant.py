import hashlib
import os
import uuid
from qdrant_client import QdrantClient, models as qm
from claimguard.models import Chunk, Hit

class PolicyIndex:
    """Named dense/sparse vectors; IDF applied once by Qdrant, RRF once by caller."""
    def __init__(self, chunks, encoder, sparse, url=None):
        self.chunks={x.chunk_id:x for x in chunks}
        self.encoder, self.sparse = encoder, sparse
        signature = '|'.join(sorted(self.chunks)) + str(encoder.model_name_or_path)
        self.collection = 'policies_' + hashlib.sha256(signature.encode()).hexdigest()[:16]
        self.client = QdrantClient(url=url,api_key=os.getenv('QDRANT_API_KEY') or None, timeout=30) if url else QdrantClient(':memory:')
        texts=[f'{x.metadata.policy_id} {x.metadata.title}\n{x.text}' for x in chunks]
        if not texts: raise ValueError('Cannot index an empty corpus')
        vectors=encoder.encode(texts,normalize_embeddings=True,show_progress_bar=False)
        sparse_vectors=sparse.embed_documents(texts)
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(self.collection,
                vectors_config={'dense':qm.VectorParams(size=len(vectors[0]),distance=qm.Distance.COSINE)},
                sparse_vectors_config={'bm25':qm.SparseVectorParams(modifier=qm.Modifier.IDF)})
        self.client.upsert(self.collection,points=[qm.PointStruct(
            id=str(uuid.UUID(x.chunk_id[:32])),
            vector={'dense':v.tolist(),'bm25':qm.SparseVector(indices=s.indices,values=s.values)},
            payload={'chunk_id':x.chunk_id,'access':x.metadata.access_level,'category':x.metadata.category,
                     'start':x.metadata.effective_date.toordinal() if x.metadata.effective_date else 1,
                     'end':(x.metadata.effective_until.toordinal() if x.metadata.effective_until else 3652059)})
            for x,v,s in zip(chunks,vectors,sparse_vectors)],wait=True)
    def search(self, query, incident_date, mode, top_k=20, access=('public','internal'), category=None):
        conditions=[qm.FieldCondition(key='access',match=qm.MatchAny(any=list(access))),
                    qm.FieldCondition(key='start',range=qm.Range(lte=incident_date.toordinal())),
                    qm.FieldCondition(key='end',range=qm.Range(gt=incident_date.toordinal()))]
        if category: conditions.append(qm.FieldCondition(key='category',match=qm.MatchValue(value=category)))
        if mode=='dense':
            vector=self.encoder.encode(query,normalize_embeddings=True).tolist(); name='dense'
        elif mode=='sparse':
            s=self.sparse.embed_query(query); vector=qm.SparseVector(indices=s.indices,values=s.values); name='bm25'
        else: raise ValueError('Index mode must be dense or sparse')
        points=self.client.query_points(self.collection,query=vector,using=name,
                    query_filter=qm.Filter(must=conditions),limit=top_k).points
        return [Hit(chunk=self.chunks[p.payload['chunk_id']],score=p.score,stage=mode) for p in points
                if mode!='sparse' or p.score>0]
    def close(self): self.client.close()
