"""Explicit, pinned downloads followed by offline loading and SHA-256 verification."""
import argparse
import json
import os
import shutil
from pathlib import Path
from huggingface_hub import snapshot_download
from claimguard.settings import load_profile, artifact_dir, file_hash, ROOT
from claimguard.diagnostics import check_artifact


def prepare(home, names, offline=False):
    seen = set()
    for name in names:
        profile = load_profile(home, name)
        for kind in ('dense', 'sparse', 'reranker'):
            spec = profile[kind]
            identity = (spec['name'], spec['revision'])
            if identity in seen: continue
            seen.add(identity)
            directory = artifact_dir(home, spec)
            if check_artifact(home, spec, verify=True):
                print('Vérifié :', spec['name'], flush=True)
                continue
            directory.mkdir(parents=True, exist_ok=True)
            patterns = ['*.json', '*.txt', '*.safetensors', 'tokenizer.model', '*.bpe.model']
            # Reuse complete pinned snapshots already on the machine, before networking.
            try:
                snapshot = Path(snapshot_download(spec['name'], revision=spec['revision'],
                                local_files_only=True, allow_patterns=patterns))
                for src in snapshot.rglob('*'):
                    if src.is_file():
                        target = directory / src.relative_to(snapshot)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(src, target)
            except Exception:
                if offline: raise
                snapshot_download(spec['name'], revision=spec['revision'],
                                  local_dir=directory, allow_patterns=patterns)
            # Validate actual tokenizer/weight/stopword loading, not just a folder name.
            if kind == 'dense':
                from sentence_transformers import SentenceTransformer
                model = SentenceTransformer(str(directory), local_files_only=True, device='cpu')
                model.encode(['Local verification'], show_progress_bar=False)
            elif kind == 'reranker':
                from sentence_transformers import CrossEncoder
                model = CrossEncoder(str(directory), local_files_only=True, device='cpu')
                model.predict([('return', 'return policy')], show_progress_bar=False)
            else:
                from langchain_qdrant import FastEmbedSparse
                model = FastEmbedSparse(model_name=spec['name'], specific_model_path=str(directory),
                                        local_files_only=True)
                model.embed_query('return policy')
            manifest = dict(spec)
            manifest['files'] = [{'path': str(p.relative_to(directory)), 'size': p.stat().st_size,
                                  'sha256': file_hash(p)} for p in sorted(directory.rglob('*'))
                                 if p.is_file() and p.name != 'manifest.json' and '.cache' not in p.parts]
            (directory / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
            print('Préparé :', spec['name'], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, default=ROOT)
    parser.add_argument('--profiles', nargs='+', default=['course'])
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    os.environ['HF_HUB_DISABLE_XET'] = '1'
    prepare(args.home.resolve(), args.profiles, args.offline)
