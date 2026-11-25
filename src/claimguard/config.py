"""Centralised configuration (configs/rag.json) and project paths."""
import json
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')

DATA = ROOT / 'data/cfpb'
RAW = DATA / 'raw'
BENCHMARK = ROOT / 'data/benchmark'
REPORTS = ROOT / 'reports/v3'
MODEL_CACHE = ROOT / 'models'


@lru_cache(maxsize=1)
def settings():
    return json.loads((ROOT / 'configs/rag.json').read_text(encoding='utf-8'))


def cfpb_settings():
    return json.loads((ROOT / 'configs/cfpb.json').read_text(encoding='utf-8'))


def qdrant_url():
    return os.getenv('QDRANT_URL') or settings()['qdrant']['url_default']


def collection_name(chunk_size, chunk_overlap):
    """One collection per chunking configuration: chunk ids and qrels depend on it."""
    return f"{settings()['qdrant']['collection_prefix']}_c{chunk_size}_o{chunk_overlap}"


def app_collection():
    app = settings()['app']
    return collection_name(app['chunk_size'], app['chunk_overlap'])


def groq_model_name():
    return os.getenv('GROQ_MODEL') or settings()['models']['llm_default']


def read_jsonl(path):
    with Path(path).open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='\n') as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
