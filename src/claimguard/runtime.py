import os
from pathlib import Path
from dotenv import load_dotenv
from claimguard.storage.catalog import Catalog
from claimguard.indexing.qdrant import PolicyIndex
from claimguard.retrieval.engine import RetrievalEngine

BASE_MODEL='sentence-transformers/all-MiniLM-L6-v2'
BASE_REVISION='1110a243fdf4706b3f48f1d95db1a4f5529b4d41'
RERANKER_REVISION='1427fd652930e4ba29e8149678df786c240d8825'
RERANKER_MODEL='cross-encoder/mmarco-mMiniLMv2-L12-H384-v1'

def build(home=None, embedding=None, with_reranker=False):
    load_dotenv()
    import torch
    from sentence_transformers import SentenceTransformer, CrossEncoder
    from langchain_qdrant import FastEmbedSparse
    torch.set_num_threads(min(4,os.cpu_count() or 1))
    home=Path(home or os.getenv('CLAIMGUARD_HOME','.')).resolve()
    catalog=Catalog(home/'var')
    for p in sorted((home/'data/policies').glob('*')):
        if p.suffix.lower() in {'.md','.txt','.pdf'}: catalog.ingest(p)
    model_name=embedding or os.getenv('EMBEDDING_MODEL',BASE_MODEL)
    encoder=SentenceTransformer(model_name,device='cpu',revision=BASE_REVISION if model_name==BASE_MODEL else None)
    # Stable identity used to separate Qdrant collections for differently trained models.
    encoder.model_name_or_path=str(model_name)
    sparse=FastEmbedSparse(model_name='Qdrant/bm25')
    index=PolicyIndex(catalog.chunks(),encoder,sparse,url=os.getenv('QDRANT_URL') or None)
    reranker=CrossEncoder(os.getenv('RERANKER_MODEL',RERANKER_MODEL),device='cpu',revision=RERANKER_REVISION if os.getenv('RERANKER_MODEL',RERANKER_MODEL)==RERANKER_MODEL else None) if with_reranker else None
    return catalog, RetrievalEngine(index,reranker)
