"""Thin HTTP interface over the shared RAG core (not part of the course material).

GET /api/status, POST /api/ask, GET /api/evaluation; serves the compiled React page from frontend/dist.
"""
import threading
from datetime import date

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from claimguard.config import REPORTS, ROOT, app_collection, groq_model_name, settings
from claimguard.report import load, runs


class AskBody(BaseModel):
    question: str = Field(min_length=3, max_length=6000)
    as_of: date | None = None


def document_view(document, rank):
    m = document.metadata
    return {'rank': rank, 'chunk_id': str(m.get('_id')), 'citation': m['citation'], 'reference': m['reference'],
            'title': m['paragraph_title'], 'section_title': m['section_title'], 'regulation': m['regulation'],
            'version': m['version'], 'version_date': m['version_date'], 'valid_until': m['valid_until'],
            'source': m['source'], 'url': m['url'], 'start_index': m['start_index'],
            'rerank_score': m.get('rerank_score'), 'text': document.page_content}


def create_app(rag_factory=None):
    app = FastAPI(title='ClaimGuard AI', version='3.0.0')
    state = {'rag': None, 'error': None}
    lock = threading.Lock()

    def get_rag():
        with lock:  # models are loaded once, on the first question
            if state['rag'] is None:
                if rag_factory:
                    state['rag'] = rag_factory()
                else:
                    from claimguard.rag import RAG
                    state['rag'] = RAG(app_collection())
            return state['rag']

    @app.get('/api/status')
    def status():
        import os
        return {'collection': app_collection(), 'settings': settings()['app'], 'loaded': state['rag'] is not None,
                'groq_configured': bool(os.getenv('GROQ_API_KEY')), 'groq_model': groq_model_name()}

    @app.post('/api/ask')
    def ask(body: AskBody):
        try:
            rag = get_rag()
        except Exception as error:
            raise HTTPException(503, f'Index ou modèles indisponibles ({type(error).__name__}). '
                                     'Lancez Qdrant (docker compose up -d) puis « python -m claimguard ingest ».') from None
        cfg = settings()['app']
        as_of = (body.as_of or date.today()).isoformat()
        try:
            result = rag.ask(body.question, mode=cfg['mode'], rerank=cfg['rerank'], rewrite=cfg['rewrite'],
                             k=cfg['k'], n_candidates=cfg['n_candidates'], as_of=as_of)
        except Exception as error:
            raise HTTPException(503, f'Recherche impossible : {type(error).__name__}') from None
        answer = result.answer.model_dump() if result.answer else None
        if answer:
            answer['citations'] = result.citations
        return {'question': result.question, 'search_query': result.search_query, 'as_of': as_of,
                'documents': [document_view(d, i) for i, d in enumerate(result.documents, 1)],
                'answer': answer, 'warnings': result.warnings, 'generation_error': result.generation_error,
                'rewrite_error': result.rewrite_error, 'timings_ms': result.timings_ms}

    @app.get('/api/evaluation')
    def evaluation():
        strip = lambda run: {k: v for k, v in run.items() if k not in ('per_question', 'queries')}
        generation = load(REPORTS / 'generation.json')
        return {'test': [strip(r) for r in runs('test')], 'development': [strip(r) for r in runs('development')],
                'selection': load(REPORTS / 'selection.json'),
                'generation': {k: v for k, v in generation.items() if k != 'rows'} if generation else None,
                'results_markdown': 'reports/v3/RESULTS.md'}

    dist = ROOT / 'frontend/dist'
    if (dist / 'index.html').exists():
        app.mount('/assets', StaticFiles(directory=dist / 'assets'), name='assets')

        @app.get('/', include_in_schema=False)
        def index():
            return FileResponse(dist / 'index.html')
    else:
        @app.get('/', include_in_schema=False)
        def missing():
            return HTMLResponse('<p>Interface non compilée : <code>cd frontend; npm install; npm run build</code>. '
                                'API : <a href="/docs">/docs</a>.</p>')
    return app


app = create_app()
