"""Offline runtime; token windows and indexes are derived from the catalog."""
import hashlib
import os
from pathlib import Path
from functools import lru_cache
from dotenv import load_dotenv
from claimguard.storage.catalog import Catalog
from claimguard.indexing.qdrant import PolicyIndex
from claimguard.retrieval.engine import RetrievalEngine
from claimguard.corpora import paths
from claimguard.settings import ROOT, load_profile, file_hash, project_home, default_corpus
from claimguard.diagnostics import require_artifact

BASE_MODEL = 'sentence-transformers/all-MiniLM-L6-v2'
BASE_REVISION = '1110a243fdf4706b3f48f1d95db1a4f5529b4d41'
RERANKER_REVISION = '1427fd652930e4ba29e8149678df786c240d8825'
RERANKER_MODEL = 'cross-encoder/mmarco-mMiniLMv2-L12-H384-v1'


@lru_cache(maxsize=1)
def initialize_libraries():
    """Initialize native CPU libraries once, before API/MCP worker threads."""
    import torch
    import sentence_transformers
    import langchain_qdrant
    torch.set_num_threads(min(4, os.cpu_count() or 1))


def token_windows(chunks, tokenizer, size, overlap):
    """Keep exact source substrings and section references; never mutate SQLite."""
    result = []
    if not 0 <= overlap < size:
        raise ValueError('Invalid token window overlap')
    for chunk in chunks:
        offsets = tokenizer(chunk.text, add_special_tokens=False, return_offsets_mapping=True,
                            truncation=False)['offset_mapping']
        for start in range(0, len(offsets), size - overlap):
            end = min(start + size, len(offsets))
            text = chunk.text[offsets[start][0]:offsets[end-1][1]]
            identity = f'{chunk.chunk_id}|tokens-v1|{size}|{overlap}|{start}|{text}'
            result.append(chunk.model_copy(update={'text': text,
                'chunk_id': hashlib.sha256(identity.encode()).hexdigest()}))
            if end == len(offsets): break
    return result


def build(home=None, embedding=None, with_reranker=False, corpus=None, mode=None, profile=None):
    home = project_home(home)
    load_dotenv(home / '.env')
    initialize_libraries()
    from sentence_transformers import SentenceTransformer, CrossEncoder
    from transformers import AutoTokenizer
    from langchain_qdrant import FastEmbedSparse
    profile = load_profile(home, profile) if not isinstance(profile, dict) else dict(profile)
    mode = mode or ('rerank' if with_reranker else 'hybrid')
    if mode not in {'dense', 'sparse', 'hybrid', 'rerank'}:
        raise ValueError('Unknown retrieval mode')
    encoder = sparse = reranker = None
    tokenizer = None
    if mode != 'sparse':
        dense_path = Path(embedding).resolve() if embedding else require_artifact(home, profile['dense'])
        encoder = SentenceTransformer(str(dense_path), device='cpu', local_files_only=True)
        encoder.max_seq_length = profile['dense']['max_tokens']
        weights = sorted(dense_path.glob('*.safetensors')) + sorted(dense_path.glob('*.bin'))
        encoder.model_name_or_path = str(dense_path) + '|' + '|'.join(file_hash(p) for p in weights)
        tokenizer = encoder.tokenizer
    else:
        from claimguard.diagnostics import check_artifact
        from claimguard.settings import artifact_dir
        if check_artifact(home, profile['dense']):
            tokenizer = AutoTokenizer.from_pretrained(str(artifact_dir(home, profile['dense'])), local_files_only=True)
    if mode != 'dense':
        sparse_path = require_artifact(home, profile['sparse'])
        sparse = FastEmbedSparse(model_name=profile['sparse']['name'], specific_model_path=str(sparse_path),
                                cache_dir=str(home / 'models/fastembed'), local_files_only=True)
    if mode == 'rerank':
        reranker = CrossEncoder(str(require_artifact(home, profile['reranker'])), device='cpu',
                                local_files_only=True, max_length=profile['reranker']['max_tokens'])
    locations = paths(home, corpus or default_corpus())
    catalog = Catalog(locations['var'])
    for p in sorted(locations['policies'].glob('*')):
        if p.suffix.lower() in {'.md', '.txt', '.pdf'}: catalog.ingest(p)
    chunks = catalog.chunks()
    if tokenizer is not None and profile.get('chunk_tokens'):
        chunks = token_windows(chunks, tokenizer, profile['chunk_tokens'], profile['chunk_overlap'])
    index = PolicyIndex(chunks, encoder, sparse, url=os.getenv('QDRANT_URL') or None, profile=profile)
    return catalog, RetrievalEngine(index, reranker, profile=profile)
