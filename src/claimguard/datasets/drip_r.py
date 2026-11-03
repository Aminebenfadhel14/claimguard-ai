"""Pinned DRIP-R import. Benchmark cases are evaluation-only, never training data."""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from urllib.request import urlopen

REPO = 'hsuvaskakoty/DRIP-R'
REVISION = '02f4c696df2a9170c3bea254ed2d60ea14bd4be4'
HASHES = {
    'README.md': '15f5fa8055805b05f9a6459c88c942d1ee2d8b7a2245c0f3b6114bd25ece74d2',
    'croissant_metadata.json': '83e45a7c5ad765ff25cec3a8588b8f385a0f41dc063d7594a6510806b90e36d3',
    'scenarios.jsonl': '888ad09bee3e7355a146a698db2670da951959dc0c0fad82f14b61568476470c',
    'tasks.jsonl': 'aaabc2bae908d5fc0233eaa857928d6cbe45cd2a2042b4854758c0c342e0e91a',
    'personas.jsonl': '87f117eed05ee822d21f5b8ec8e333efcba5e850b2e8db6edc887e8d08c8c617',
}
HEADINGS = [
    ['Amazon Return Policy', '2025 Holiday Season Extended Return Window', 'Refund Timelines',
     'Return Window', "Items That You Can't Return", 'Initiating a Return', 'Third-Party Seller Returns',
     'Sending Us Your Return', 'Amazon Pharmacy', 'Amazon Business', 'Amazon Luxury Stores',
     'Return Fees', 'Heavy and/or Bulky Items', 'Discounted Purchases', 'Returning a Gift',
     'Global Store Returns', 'Special Delivery Service Returns', 'Product Warranties',
     'Unintended Item(s) in My Return', 'Returning Items Purchased in a Bundle', 'Note:'],
    ['Returns to Third-Party Sellers', 'Request a return', 'Get return instructions',
     'Package your return', 'Ship your return', 'Track your refund', 'Understanding refund delays',
     'Extra-large or heavy items', 'What to do next'],
]

def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]

def write_jsonl(path, rows):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r, ensure_ascii=False, allow_nan=False) + '\n' for r in rows), encoding='utf-8')

def agent_input(row):
    """Explicit allowlist: hidden task/ambiguity/persona/simulator fields never enter retrieval."""
    return {'scenario_id': row['scenario_id'], 'task_id': row['task_id'],
            'complaint': row['first_customer_message'], 'agent_brief': row['detail_agent']}

def query_for(row):
    safe = agent_input(row)
    return safe['complaint'] + '\nAgent brief: ' + safe['agent_brief']

def evaluation_sample(rows):
    groups = {}
    for r in rows:
        groups.setdefault(r['task_id'], []).append(r)
    # Use explicit persona order across all tasks, not ambiguous scenario-id aliases.
    groups = {k: sorted(v, key=lambda r: r['persona']['Persona_id']) for k,v in sorted(groups.items())}
    selected = [v[i % len(v)] for i,v in enumerate(groups.values())]
    selected += [v[(i + 5) % len(v)] for i,v in enumerate(list(groups.values())[:10])]
    return selected

def prepare(home, download=False):
    home = Path(home).resolve(); raw = home/'data/external/drip_r'
    raw.mkdir(parents=True, exist_ok=True)
    files = []
    for name, expected in HASHES.items():
        p = raw/name
        if not p.exists():
            if not download: raise FileNotFoundError(f'{p}; run scripts/prepare_drip_r.py --download')
            with urlopen(f'https://huggingface.co/datasets/{REPO}/resolve/{REVISION}/{name}', timeout=90) as response:
                content = response.read()
            if hashlib.sha256(content).hexdigest() != expected:
                raise ValueError('Downloaded bytes do not match the pinned source: ' + name)
            p.write_bytes(content)
        if hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            raise ValueError('Source checksum mismatch: ' + name)
        files.append({'file': name, 'sha256': expected, 'size_bytes': p.stat().st_size})
    rows, tasks, personas = [read_jsonl(raw/n) for n in ('scenarios.jsonl','tasks.jsonl','personas.jsonl')]
    unique = {}
    for r in rows:
        for p in [r['Policy']['Primary Policy'], *r['Policy']['Related policies']]:
            h = hashlib.sha256(p['text'].encode()).hexdigest()
            unique.setdefault(h, p)
    if len(rows) != 400 or len(unique) != 2: raise ValueError('Unexpected pinned dataset shape')
    out = home/'data/drip_r'; policies = out/'policies'; policies.mkdir(parents=True,exist_ok=True)
    policy_manifest = []
    for number, headings in enumerate(HEADINGS, 1):
        policy = next(p for p in unique.values() if p['text'].splitlines()[0] == headings[0])
        text = policy['text']; lines = text.splitlines(); starts = [lines.index(h)+1 for h in headings]
        policy_id = f'DRIP-{number:03d}'; p = policies/(policy_id+'.txt')
        p.write_bytes(text.encode('utf-8'))
        sections = [{'section': f'{number}.{i+1}', 'title': title, 'start_line': start,
                     'end_line': starts[i+1]-1 if i+1<len(starts) else len(lines)}
                    for i,(title,start) in enumerate(zip(headings,starts))]
        mapping = {'source_sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'sections': sections}
        p.with_suffix('.txt.sections.json').write_text(json.dumps(mapping,indent=2),encoding='utf-8')
        metadata = {'document_id': policy_id+'-SNAPSHOT', 'policy_id': policy_id, 'title': headings[0],
            'category': 'returns' if number==1 else 'seller_returns', 'department': 'Customer support',
            'version': '1.0', 'version_origin': 'project_snapshot', 'effective_date': None,
            'temporal_basis': 'dataset_snapshot', 'language': 'en', 'access_level': 'public',
            'source': f'https://huggingface.co/datasets/{REPO}/blob/{REVISION}/scenarios.jsonl',
            'source_revision': REVISION}
        p.with_suffix('.txt.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
        policy_manifest.append({'file':str(p.relative_to(home)), 'policy_id':policy_id, **mapping,
            'source_json_path': 'Policy.Primary Policy.text' if number==1 else 'Policy.Related policies[0].text',
            'original_url':policy['url'], 'version_note':'1.0 is a local snapshot label, not an Amazon version',
            'page_note':'TXT logical page 1; cite source lines, no original PDF pagination'})
    write_jsonl(out/'agent_cases.jsonl', [agent_input(r) for r in rows])
    warnings = []
    for task in tasks:
        for key,value in task.items():
            if isinstance(value,str) and value.strip().lower() in {'nan','none','null',''}:
                warnings.append({'task_id': task['task_id'], 'field':key, 'value':value})
    audit = {'repository': REPO, 'revision':REVISION, 'source_files':files,
        'scenario_count':len(rows), 'task_count':len(tasks), 'persona_count':len(personas),
        'unique_policy_count':len(unique), 'duplicate_messages':len(rows)-len({r['first_customer_message'] for r in rows}),
        'duplicate_scenario_ids':len(rows)-len({r['scenario_id'] for r in rows}),
        'missing_visible_fields':sum(not r.get(k) for r in rows for k in ('first_customer_message','detail_agent')),
        'scenarios_per_task':dict(Counter(r['task_id'] for r in rows)),
        'placeholder_fields_in_tasks':warnings,
        'placeholder_fields_in_scenarios':[
            {'scenario_id':r['scenario_id'],'task_id':r['task_id'],'field':'task.'+key,'value_repr':repr(value)}
            for r in rows for key,value in r['task'].items()
            if (isinstance(value,str) and value.strip().lower() in {'nan','none','null',''})
               or (isinstance(value,float) and not math.isfinite(value))],
        'license_declared_in_croissant':json.loads((raw/'croissant_metadata.json').read_text(encoding='utf-8'))['license'],
        'policy_manifest':policy_manifest,
        'limitations':['Synthetic benchmark, not real complaint records',
          '400 scenarios are variants of only 40 tasks; group metrics by task_id',
          'No published gold decision or human annotation; do not infer one',
          'Unknown policy effective date and original URLs; snapshot only, no historical applicability',
          'Return Window table omits product categories; fees table has missing conditions; blanks preserved',
          'Agent-facing inputs exclude task metadata, private_info, behavior, and persona attributes',
          'Scenario IDs can contain old task aliases: use explicit task_id',
          'Some source JSONL records contain non-standard NaN tokens; originals preserved, safe agent export contains none',
          'Original benchmark cases reserved for evaluation; training is separately authored from policy passages']}
    reports = home/'reports/drip_r'; reports.mkdir(parents=True,exist_ok=True)
    (reports/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'provenance.json').write_text(json.dumps({'repo':REPO,'revision':REVISION,'files':files},indent=2),encoding='utf-8')
    return audit
