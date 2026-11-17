"""ClaimGuard AI — local web API for the React interface.

Mirrors the Streamlit workbench (Recherche, Documents, Explication RAG, Évaluations)
on top of the same offline retrieval engine. Bound to 127.0.0.1 by the launcher;
single local user, no multi-tenant authentication.

Run:  python -m uvicorn claimguard.web:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import json
import os
import threading
from collections import OrderedDict
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Callable, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from claimguard.corpora import CORPORA, paths
from claimguard.diagnostics import ModelUnavailable, readiness, record_error
from claimguard.models import SearchRequest
from claimguard.settings import ROOT, file_hash, load_profile

SOURCE_SUFFIXES = {'.md', '.txt', '.pdf'}
CORPUS_INFO = {
    'drip_r': {
        'label': 'DRIP-R · Retours produits',
        'short': 'DRIP-R',
        'dated': False,
        'note': ("Instantané de benchmark, sans dates de validité connues. Les sources ne "
                 "permettent pas de garantir un remboursement ni de décrire les politiques actuelles."),
    },
    'novaretail': {
        'label': 'NovaRetail · Politiques fictives',
        'short': 'NovaRetail',
        'dated': True,
        'note': "Politiques fictives et versionnées. La date de l’incident détermine les versions recherchées.",
    },
}
MODE_LABELS = {
    'dense': 'Sémantique · Dense',
    'sparse': 'Mots-clés · BM25',
    'hybrid': 'Hybride · Dense + BM25 + RRF',
    'rerank': 'Hybride + reranking',
}
EXPERIMENT_LABELS = {
    'E1': 'Dense', 'E2': 'BM25', 'E3': 'Hybride RRF', 'E4': 'Hybride + reranking',
    'FT_DENSE': 'Fine-tuning · Dense', 'E5': 'Fine-tuning · Hybride + reranking',
}
DEFAULT_QUERY = 'My defective phone was refused for exchange four days after purchase.'
DEFAULT_DATE = date(2026, 11, 2)


class WebSearchRequest(BaseModel):
    corpus: Literal['drip_r', 'novaretail'] = 'drip_r'
    profile: str | None = None
    query: str = Field(min_length=3, max_length=6000)
    incident_date: date = DEFAULT_DATE
    mode: Literal['dense', 'sparse', 'hybrid', 'rerank'] = 'rerank'
    top_k: int = Field(default=5, ge=1, le=20)
    category: str | None = None
    agent_brief: str | None = Field(default=None, max_length=4000)
    use_llm: bool = False


class LoadRequest(BaseModel):
    corpus: Literal['drip_r', 'novaretail'] = 'drip_r'
    profile: str | None = None
    mode: Literal['dense', 'sparse', 'hybrid', 'rerank'] = 'rerank'


class EngineCache:
    """Loaded engines keyed by (corpus, profile, mode). Loading is serialized per key."""

    def __init__(self, builder: Callable, max_entries: int = 3):
        self.builder, self.max_entries = builder, max_entries
        self.engines: OrderedDict[tuple, object] = OrderedDict()
        self.locks: dict[tuple, threading.Lock] = {}
        self.guard = threading.Lock()

    def get(self, corpus, profile, mode):
        key = (corpus, profile, mode)
        with self.guard:
            if key in self.engines:
                self.engines.move_to_end(key)
                return self.engines[key]
            lock = self.locks.setdefault(key, threading.Lock())
        with lock:
            with self.guard:
                if key in self.engines:
                    return self.engines[key]
            engine = self.builder(corpus=corpus, profile=profile, mode=mode)
            with self.guard:
                self.engines[key] = engine
                while len(self.engines) > self.max_entries:
                    _, old = self.engines.popitem(last=False)
                    _close(old)
            return engine

    def loaded(self):
        with self.guard:
            return [{'corpus': c, 'profile': p, 'mode': m} for c, p, m in self.engines]

    def close(self):
        with self.guard:
            for engine in self.engines.values():
                _close(engine)
            self.engines.clear()


def _close(engine):
    index = getattr(engine, 'index', None)
    if index is not None and hasattr(index, 'close'):
        try:
            index.close()
        except Exception:
            pass


def default_builder(home: Path):
    def builder(corpus, profile, mode):
        from claimguard.runtime import build
        _, engine = build(home, corpus=corpus, profile=profile, mode=mode)
        return engine
    return builder


def serialize_hit(hit, rank: int) -> dict:
    chunk = hit.chunk
    meta = chunk.metadata
    return {
        'rank': rank,
        'chunk_id': chunk.chunk_id,
        'reference': chunk.reference(),
        'policy_id': meta.policy_id,
        'version': meta.version,
        'title': meta.title,
        'category': meta.category,
        'access_level': meta.access_level,
        'section': chunk.section,
        'section_title': chunk.section_title,
        'text': chunk.text,
        'source_file': chunk.source_file,
        'page': chunk.page,
        'line_start': chunk.source_line_start,
        'line_end': chunk.source_line_end,
        'file_hash': chunk.file_hash,
        'score': float(hit.score),
        'stage': hit.stage,
    }


def create_app(builder: Callable | None = None, home: Path | str | None = None,
               static_dir: Path | str | None = None) -> FastAPI:
    load_dotenv(ROOT / '.env')
    home = Path(home or os.getenv('CLAIMGUARD_HOME') or ROOT)
    if not home.is_absolute():
        # « . » dans .env désigne la racine du projet, pas le dossier courant du terminal.
        home = ROOT / home
    home = home.resolve()
    if not (home / 'configs/retrieval.json').exists():
        home = ROOT
    load_dotenv(home / '.env')
    cache = EngineCache(builder or default_builder(home))

    @asynccontextmanager
    async def lifespan(app):
        if builder is None:
            from claimguard.runtime import initialize_libraries
            initialize_libraries()
        yield
        cache.close()

    app = FastAPI(title='ClaimGuard AI — Web API', version='1.0.0', lifespan=lifespan)
    app.state.cache = cache
    app.add_middleware(
        CORSMiddleware,
        allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
        allow_methods=['GET', 'POST'],
        allow_headers=['Content-Type'],
    )

    # ---------- helpers ----------
    def profiles_config():
        return json.loads((home / 'configs/retrieval.json').read_text(encoding='utf-8'))

    def resolve_profile(name: str | None) -> dict:
        try:
            return load_profile(home, name or None)
        except ValueError:
            raise HTTPException(400, 'Profil de recherche inconnu') from None

    def corpus_paths(corpus: str) -> dict:
        if corpus not in CORPORA:
            raise HTTPException(400, 'Corpus inconnu')
        return paths(home, corpus)

    def source_files(corpus: str) -> list[Path]:
        folder = corpus_paths(corpus)['policies']
        return sorted(p for p in folder.glob('*') if p.is_file() and p.suffix.lower() in SOURCE_SUFFIXES)

    def find_source(corpus: str, name: str) -> Path:
        for p in source_files(corpus):
            if p.name == name:
                return p
        raise HTTPException(404, 'Document inconnu')

    def sidecar(path: Path) -> dict:
        side = path.with_suffix(path.suffix + '.json')
        return json.loads(side.read_text(encoding='utf-8')) if side.exists() else {}

    def catalog(corpus: str):
        from claimguard.storage.catalog import Catalog
        locations = corpus_paths(corpus)
        cat = Catalog(locations['var'])
        for p in source_files(corpus):
            cat.ingest(p)
        return cat

    # ---------- configuration & status ----------
    @app.get('/api/health')
    def health():
        return {'status': 'ok'}

    @app.get('/api/config')
    def config():
        cfg = profiles_config()
        requested = os.getenv('CLAIMGUARD_PROFILE') or cfg['default']
        if requested not in cfg['profiles']:
            requested = cfg['default']
        return {
            'corpora': [{'id': c, **CORPUS_INFO[c]} for c in ('drip_r', 'novaretail')],
            'default_corpus': 'drip_r',
            'profiles': [{'id': k, 'label': v.get('label', k)} for k, v in cfg['profiles'].items()],
            'default_profile': requested,
            'modes': [{'id': k, 'label': v} for k, v in MODE_LABELS.items()],
            'default_query': DEFAULT_QUERY,
            'default_date': DEFAULT_DATE.isoformat(),
            'groq_configured': bool(os.getenv('GROQ_API_KEY')),
            'groq_model': os.getenv('GROQ_MODEL', 'openai/gpt-oss-20b') if os.getenv('GROQ_API_KEY') else None,
        }

    @app.get('/api/status')
    def status(corpus: str = 'drip_r', profile: str | None = None):
        prof = resolve_profile(profile)
        corpus_paths(corpus)
        result = readiness(home, corpus, prof)
        loaded = [e for e in cache.loaded() if e['corpus'] == corpus and e['profile'] == prof['name']]
        result['loaded_modes'] = [e['mode'] for e in loaded]
        result['engine_ready'] = bool(loaded)
        result['profile_label'] = prof.get('label', prof['name'])
        return result

    @app.post('/api/engine/load')
    def load_engine(req: LoadRequest):
        prof = resolve_profile(req.profile)
        try:
            cache.get(req.corpus, prof['name'], req.mode)
        except ModelUnavailable as exc:
            record_error(home, 'model_loading')
            raise HTTPException(409, str(exc)) from None
        except Exception:
            error_id = record_error(home, 'engine_load')
            raise HTTPException(503, {'message': 'Chargement du moteur impossible', 'error_id': error_id}) from None
        return {'loaded': True, 'corpus': req.corpus, 'profile': prof['name'], 'mode': req.mode}

    # ---------- benchmark cases ----------
    @app.get('/api/cases')
    def cases(corpus: str = 'drip_r', q: str = '', limit: int = Query(50, ge=1, le=400),
              offset: int = Query(0, ge=0)):
        corpus_paths(corpus)
        path = home / 'data/drip_r/agent_cases.jsonl'
        if corpus != 'drip_r' or not path.exists():
            return {'total': 0, 'items': []}
        rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
        needle = q.strip().lower()
        if needle:
            rows = [r for r in rows if needle in (r['scenario_id'] + ' ' + r['task_id'] + ' '
                                                   + r['complaint'] + ' ' + r.get('agent_brief', '')).lower()]
        return {'total': len(rows), 'items': rows[offset:offset + limit]}

    # ---------- search ----------
    @app.post('/api/search')
    def search(req: WebSearchRequest):
        prof = resolve_profile(req.profile)
        status_now = readiness(home, req.corpus, prof)
        if not status_now['available_modes']:
            raise HTTPException(409, 'Les modèles locaux doivent être préparés : python scripts/prepare_models.py --profiles '
                                + prof['name'])
        if req.mode not in status_now['available_modes']:
            raise HTTPException(409, 'Mode indisponible avec les modèles présents. Modes disponibles : '
                                + ', '.join(status_now['available_modes']))
        brief = (req.agent_brief or '').strip()
        request_text = req.query + ('\nAgent brief: ' + brief if req.corpus == 'drip_r' and brief else '')
        incident = req.incident_date if CORPUS_INFO[req.corpus]['dated'] else DEFAULT_DATE
        warnings: list[str] = []
        try:
            search_req = SearchRequest(query=request_text, incident_date=incident, mode=req.mode,
                                       top_k=req.top_k, category=req.category or None)
        except ValidationError:
            raise HTTPException(422, 'La question doit contenir entre 3 et 6 000 caractères.') from None
        try:
            engine = cache.get(req.corpus, prof['name'], req.mode)
            llm = None
            rewritten = None
            if req.use_llm:
                from claimguard.prompts.rag import groq_model, rewrite
                try:
                    llm = groq_model()
                    rewritten = rewrite(request_text, llm)
                    search_req = SearchRequest(query=rewritten, incident_date=incident, mode=req.mode,
                                               top_k=req.top_k, category=req.category or None)
                except Exception:
                    error_id = record_error(home, 'rewrite')
                    warnings.append(f'Réécriture indisponible ; recherche du texte original. Référence : {error_id}')
            trace = engine.retrieve(search_req, access=('public', 'internal'))
        except ModelUnavailable as exc:
            record_error(home, 'model_loading')
            raise HTTPException(409, str(exc)) from None
        except HTTPException:
            raise
        except Exception:
            error_id = record_error(home, 'retrieval')
            raise HTTPException(503, {'message': 'La recherche n’a pas abouti. Consultez var/logs/errors.log.',
                                      'error_id': error_id}) from None

        answer = None
        if req.use_llm and llm is not None:
            from claimguard.prompts.rag import generate
            try:
                prefix = 'Use only this undated benchmark snapshot. ' if req.corpus == 'drip_r' else ''
                generated = generate(prefix + request_text, trace['final'], llm)
                by_id = {h.chunk.chunk_id: h.chunk for h in trace['final']}
                answer = generated.model_dump(mode='json')
                for c in answer['citations']:
                    chunk = by_id.get(c['chunk_id'])
                    c['reference'] = chunk.reference() if chunk else None
            except Exception:
                error_id = record_error(home, 'generation')
                warnings.append('Brouillon indisponible. Les passages retrouvés restent consultables. '
                                f'Référence : {error_id}')
        elif req.use_llm and not os.getenv('GROQ_API_KEY'):
            warnings.append('Groq non configuré : ajoutez GROQ_API_KEY dans .env pour rédiger un brouillon.')

        stages = {}
        for stage in ('dense', 'sparse', 'rrf', 'reranker', 'final'):
            stages[stage] = [serialize_hit(h, i) for i, h in enumerate(trace.get(stage, []), 1)]
        diagnostics = dict(trace.get('diagnostics', {}))
        return {
            'corpus': req.corpus, 'profile': prof['name'], 'mode': req.mode,
            'incident_date': incident.isoformat(),
            'query': trace.get('query', search_req.query),
            'original_query': request_text,
            'rewritten_query': rewritten,
            'stages': stages,
            'diagnostics': diagnostics,
            'answer': answer,
            'warnings': warnings,
        }

    # ---------- documents ----------
    @app.get('/api/documents')
    def documents(corpus: str = 'drip_r'):
        items = []
        for p in source_files(corpus):
            meta = sidecar(p)
            items.append({
                'name': p.name, 'format': p.suffix.lower().lstrip('.'), 'size': p.stat().st_size,
                'policy_id': meta.get('policy_id'), 'title': meta.get('title'), 'version': meta.get('version'),
                'category': meta.get('category'), 'department': meta.get('department'),
                'access_level': meta.get('access_level'), 'language': meta.get('language'),
                'effective_date': meta.get('effective_date'), 'effective_until': meta.get('effective_until'),
                'temporal_basis': meta.get('temporal_basis', 'effective_date'),
                'has_sections': p.with_suffix(p.suffix + '.sections.json').exists(),
            })
        return {'corpus': corpus, 'items': items}

    @app.get('/api/categories')
    def categories(corpus: str = 'drip_r'):
        return sorted({sidecar(p).get('category') for p in source_files(corpus)} - {None})

    @app.get('/api/documents/{name}')
    def document(name: str, corpus: str = 'drip_r'):
        path = find_source(corpus, name)
        sections_path = path.with_suffix(path.suffix + '.sections.json')
        sections = json.loads(sections_path.read_text(encoding='utf-8'))['sections'] if sections_path.exists() else None
        text = None if path.suffix.lower() == '.pdf' else path.read_text(encoding='utf-8')
        return {'name': path.name, 'metadata': sidecar(path), 'text': text, 'sections': sections,
                'sha256': file_hash(path), 'size': path.stat().st_size}

    @app.get('/api/documents/{name}/download')
    def download(name: str, corpus: str = 'drip_r'):
        path = find_source(corpus, name)
        return FileResponse(path, filename=path.name)

    @app.get('/api/policies/{policy_id}/versions')
    def versions(policy_id: str, corpus: str = 'drip_r'):
        try:
            return {'policy_id': policy_id, 'versions': catalog(corpus).versions(policy_id)}
        except Exception:
            error_id = record_error(home, 'catalog_versions')
            raise HTTPException(503, {'message': 'Catalogue indisponible', 'error_id': error_id}) from None

    @app.get('/api/policies/{policy_id}/compare')
    def compare(policy_id: str, a: str, b: str, corpus: str = 'drip_r'):
        try:
            diff = catalog(corpus).compare(policy_id, a, b)
        except KeyError:
            raise HTTPException(404, 'Politique ou version inconnue') from None
        except Exception:
            error_id = record_error(home, 'catalog_compare')
            raise HTTPException(503, {'message': 'Comparaison impossible', 'error_id': error_id}) from None
        return {'policy_id': policy_id, 'versions': [a, b], 'diff': diff}

    # ---------- evaluation ----------
    def load_report(corpus: str):
        locations = corpus_paths(corpus)
        latest = locations['reports'] / 'latest.json'
        report_path = latest if latest.exists() else locations['reports'] / 'retrieval_results.json'
        if not report_path.exists():
            return None, None, locations
        return report_path, json.loads(report_path.read_text(encoding='utf-8')), locations

    @app.get('/api/evaluation')
    def evaluation(corpus: str = 'drip_r', profile: str | None = None):
        prof = resolve_profile(profile)
        report_path, report, locations = load_report(corpus)
        if report is None:
            return {'available': False}
        current = {p.name: file_hash(p) for p in locations['policies'].glob('*') if p.is_file()}
        summary = []
        for key, value in report['summary'].items():
            summary.append({'id': key, 'label': EXPERIMENT_LABELS.get(key, key), 'metrics': value['metrics'],
                            'latency_mean_ms': value.get('latency_mean_ms'),
                            'latency_p95_ms': value.get('latency_p95_ms'),
                            'mode': value.get('mode'), 'embedding': value.get('embedding'),
                            'answerable_questions': value.get('answerable_questions'),
                            'unanswerable_questions': value.get('unanswerable_questions')})
        comparisons = []
        baseline = locations['reports'] / 'baselines/v1/retrieval_results.json'
        if baseline.exists() and report_path.name == 'latest.json':
            old = json.loads(baseline.read_text(encoding='utf-8'))
            for key, value in report['summary'].items():
                if key not in old['summary']:
                    continue
                for metric in ('recall@5', 'mrr@10'):
                    before = old['summary'][key]['metrics'][metric]
                    after = value['metrics'][metric]
                    comparisons.append({'id': key, 'label': EXPERIMENT_LABELS.get(key, key), 'metric': metric,
                                        'before': before, 'after': after, 'delta': after - before})
        protocol = {k: v for k, v in report.items() if k not in ('summary', 'per_question')}
        return {
            'available': True,
            'corpus': corpus,
            'report_path': str(report_path.relative_to(home)).replace('\\', '/'),
            'split': report.get('split', 'test historique'),
            'created_at': report.get('created_at'),
            'profile_matches': report.get('profile_fingerprint') == prof['fingerprint'],
            'sources_changed': bool(report.get('source_sha256')) and report['source_sha256'] != current,
            'summary': summary,
            'primary': next((s for s in summary if s['id'] == 'E4'), None),
            'comparisons': comparisons,
            'protocol': protocol,
            'experiments': [s['id'] for s in summary],
            'targets': {'recall@5': 0.90, 'mrr@10': 0.85, 'latency_p95_s': 3.0},
        }

    @app.get('/api/evaluation/questions')
    def evaluation_questions(corpus: str = 'drip_r', experiment: str = 'E4'):
        _, report, _ = load_report(corpus)
        if report is None:
            return {'items': []}
        rows = [r for r in report.get('per_question', []) if r.get('experiment') == experiment]
        return {'experiment': experiment, 'items': rows}

    @app.get('/api/evaluation/chart')
    def evaluation_chart(corpus: str = 'drip_r'):
        path = corpus_paths(corpus)['reports'] / 'retrieval_comparison.png'
        if not path.exists():
            raise HTTPException(404, 'Graphique absent')
        return FileResponse(path, media_type='image/png')

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        detail = exc.detail
        body = detail if isinstance(detail, dict) else {'message': str(detail)}
        return JSONResponse(status_code=exc.status_code, content={'detail': body})

    # ---------- React build (single-port mode) ----------
    dist = Path(static_dir) if static_dir else home / 'frontend/dist'
    if static_dir is None and not (dist / 'index.html').exists():
        dist = ROOT / 'frontend/dist'
    if not (dist / 'index.html').exists():
        from fastapi.responses import HTMLResponse

        @app.get('/', include_in_schema=False)
        def missing_frontend():
            return HTMLResponse('<h1>ClaimGuard AI</h1><p>Interface React non compilée : '
                                'lancez <code>python scripts/run_web.py --build</code>. '
                                'API disponible sur <a href="/docs">/docs</a>.</p>')
    else:
        app.mount('/assets', StaticFiles(directory=dist / 'assets'), name='assets')

        @app.get('/{path:path}', include_in_schema=False)
        def spa(path: str):
            if path.startswith('api/'):
                raise HTTPException(404, 'Route API inconnue')
            candidate = (dist / path).resolve()
            if path and candidate.is_file() and dist.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(dist / 'index.html')

    return app


app = create_app()
