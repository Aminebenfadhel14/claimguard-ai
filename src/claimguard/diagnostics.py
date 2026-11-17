"""Offline readiness checks. No implicit downloads, model loading or secrets."""
import json
import logging
import os
import uuid
import traceback
import re
from pathlib import Path
from claimguard.corpora import paths
from claimguard.settings import artifact_dir, load_profile, file_hash


class ModelUnavailable(RuntimeError):
    pass


def check_artifact(home, spec, verify=False):
    directory = artifact_dir(home, spec)
    try:
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        if manifest['name'] != spec['name'] or manifest['revision'] != spec['revision']:
            return False
        if not manifest['files']:
            return False
        for entry in manifest['files']:
            p = directory / entry['path']
            if not p.is_file() or p.stat().st_size != entry['size']:
                return False
            if verify and file_hash(p) != entry['sha256']:
                return False
        return True
    except (OSError, ValueError, KeyError, TypeError):
        return False


def readiness(home, corpus='drip_r', profile=None, verify=False):
    profile = load_profile(home, profile) if not isinstance(profile, dict) else profile
    locations = paths(home, corpus)
    files = [p for p in locations['policies'].glob('*') if p.suffix in {'.txt', '.md', '.pdf'}]
    models = {key: check_artifact(home, profile[key], verify) for key in ('dense', 'sparse', 'reranker')}
    modes = []
    if files:
        if models['dense']: modes.append('dense')
        if models['sparse']: modes.append('sparse')
        if models['dense'] and models['sparse']:
            modes.append('hybrid')
            if models['reranker']: modes.append('rerank')
    return {'corpus': corpus, 'documents': len(files), 'profile': profile['name'],
            'fingerprint': profile['fingerprint'], 'models': models, 'available_modes': modes,
            'groq_configured': bool(os.getenv('GROQ_API_KEY')), 'engine_ready': False,
            'note': 'Ressources vérifiées ; index validé au chargement du moteur.'}


def require_artifact(home, spec):
    if not check_artifact(home, spec):
        raise ModelUnavailable('Modèle local absent ou incomplet : ' + spec['name'] +
                               '. Exécutez .\\.venv\\Scripts\\python.exe scripts/prepare_models.py')
    return artifact_dir(home, spec)


def record_error(home, operation):
    """Record traceback only, without request text or local variables."""
    error_id = uuid.uuid4().hex[:12]
    folder = Path(home) / 'var/logs'
    folder.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger('claimguard.errors')
    logger.setLevel(logging.ERROR)
    handler = logging.FileHandler(folder / 'errors.log', encoding='utf-8')
    try:
        logger.addHandler(handler)
        detail = traceback.format_exc()
        for name in ('GROQ_API_KEY','QDRANT_API_KEY','CLAIMGUARD_API_TOKEN'):
            secret = os.getenv(name)
            if secret: detail = detail.replace(secret, '[REDACTED]')
        detail = re.sub(r'Bearer\s+[^\s\"\']+', 'Bearer [REDACTED]', detail, flags=re.I)
        logger.error('%s operation=%s\n%s', error_id, operation, detail)
    finally:
        logger.removeHandler(handler)
        handler.close()
    return error_id
