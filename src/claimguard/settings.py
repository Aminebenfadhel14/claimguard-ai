"""Versioned retrieval profiles shared by UI, CLI, API and MCP."""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


DEFAULT_CORPUS = 'drip_r'


def project_home(home=None):
    """Project root. A relative CLAIMGUARD_HOME (e.g. '.') is relative to the project, not to the shell."""
    if home:
        return Path(home).resolve()
    configured = Path(os.getenv('CLAIMGUARD_HOME') or ROOT)
    if not configured.is_absolute():
        configured = ROOT / configured
    return configured.resolve()


def default_corpus():
    return os.getenv('CLAIMGUARD_CORPUS') or DEFAULT_CORPUS


def load_profile(home=None, name=None):
    home = project_home(home)
    config = json.loads((home / 'configs/retrieval.json').read_text(encoding='utf-8'))
    name = name or os.getenv('CLAIMGUARD_PROFILE') or config['default']
    if name not in config['profiles']:
        raise ValueError('Profil de recherche inconnu')
    profile = dict(config['profiles'][name])
    profile['pipeline_version'] = 'section-diversity-v2'
    profile['name'] = name
    profile['fingerprint'] = hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest()
    return profile


def artifact_dir(home, spec):
    return Path(home) / 'models/cache' / spec['name'].replace('/', '--') / spec['revision']


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()
