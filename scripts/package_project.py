"""Package source, local Git history, datasets, checkpoints and execution evidence."""
import argparse
from pathlib import Path
import zipfile

def package(root, output):
    root=Path(root).resolve();output=Path(output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
    excluded={'.venv','var','__pycache__','.pytest_cache'}
    files=[]
    for p in sorted(root.rglob('*')):
        if not p.is_file() or p.is_symlink() or p==output:continue
        rel=p.relative_to(root)
        if any(part in excluded or part.endswith('.egg-info') for part in rel.parts):continue
        if p.name=='.env' or (p.name.startswith('.env.') and p.name!='.env.example'):continue
        if p.suffix in {'.zip','.pyc','.tmp'}:continue
        files.append(p)
    temporary=output.with_suffix('.zip.tmp')
    with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:z.write(p,Path(root.name)/p.relative_to(root))
    with zipfile.ZipFile(temporary) as z:
        failure=z.testzip()
        if failure:raise ValueError('Archive CRC failure: '+failure)
        names=set(z.namelist())
        required=['data/external/drip_r/scenarios.jsonl','models/drip-r-policy-embedding/model.safetensors',
            'reports/drip_r/retrieval_results.json','reports/drip_r/scenario_retrieval.jsonl',
            'reports/drip_r/pytest_results.xml','reports/drip_r/mcp_demo.json']
        assert all(root.name+'/'+x in names for x in required)
        assert not any('/.venv/' in x or '/var/' in x or x.endswith('/.env') for x in names)
    temporary.replace(output)
    print({'archive':str(output),'files':len(files),'size_bytes':output.stat().st_size})

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=root.parent/'deliverables/claimguard-ai.zip')
    package(root,p.parse_args().output)
