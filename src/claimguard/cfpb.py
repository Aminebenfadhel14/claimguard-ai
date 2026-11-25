"""Import du corpus réel : règlements eCFR + plaintes CFPB.

Deux étapes séparées, pour que le résultat soit reproductible :

1. ``download`` (réseau) : récupère les sources officielles et écrit un instantané brut
   dans ``data/cfpb/raw/`` (XML eCFR, plaintes sélectionnées, manifeste SHA-256).
2. ``build`` (hors ligne) : transforme cet instantané en plaintes annotées (test et développement).

Les XML eCFR bruts sont chargés directement en Documents LangChain par ``claimguard.ingest``
via ``regulation_versions`` : aucun fichier texte intermédiaire.

Les règles d'annotation viennent uniquement de ``configs/cfpb.json``.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

from claimguard.config import read_jsonl, write_jsonl

USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
              'Chrome/130.0 Safari/537.36 ClaimGuard-AI-academic-import')
# Sans en-tête Accept explicite, l'API eCFR répond « 406 Not Acceptable ».
HEADERS = {'User-Agent': USER_AGENT, 'Accept': 'application/json, application/xml, text/xml, */*;q=0.8',
           'Accept-Language': 'en-US,en;q=0.9'}
ECFR = 'https://www.ecfr.gov/api/versioner/v1'
LETTERS = 'abcdefghijklmnopqrstuvwxyz'


# --------------------------------------------------------------------------- réseau
def http_get(url, retries=6, timeout=120):
    """GET avec reprise exponentielle (eCFR limite le débit : HTTP 429)."""
    delay = 2.0
    for attempt in range(retries):
        request = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == retries - 1:
                raise
        except urllib.error.URLError:
            if attempt == retries - 1:
                raise
        time.sleep(delay)
        delay *= 2
    raise RuntimeError('unreachable')


def download_file(url, target: Path, retries=4):
    """Téléchargement en flux d'une archive volumineuse, avec reprise si interrompu."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size > 0:
        return target
    partial = target.with_suffix(target.suffix + '.part')
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=300) as response, partial.open('wb') as out:
                total = int(response.headers.get('Content-Length') or 0)
                done = 0
                while chunk := response.read(1024 * 1024):
                    out.write(chunk)
                    done += len(chunk)
                    if total:
                        print(f'\r  {target.name} : {done / total:6.1%} ({done // 2**20} / {total // 2**20} Mo)',
                              end='', flush=True)
            print()
            partial.replace(target)
            return target
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == retries - 1:
                raise
            time.sleep(5 * (attempt + 1))
    return target


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


# --------------------------------------------------------------------------- eCFR
def ecfr_versions(part, section):
    """Dates (triées) des versions substantielles d'une section, telles que publiées par eCFR."""
    url = f'{ECFR}/versions/title-12.json?' + urllib.parse.urlencode({'part': part, 'section': section})
    data = json.loads(http_get(url))
    dates = sorted({v['date'] for v in data['content_versions'] if v.get('substantive', True) and not v.get('removed')})
    return [d for d in dates if d <= date.today().isoformat()]


def ecfr_xml(version_date, part, section):
    url = f'{ECFR}/full/{version_date}/title-12.xml?' + urllib.parse.urlencode({'part': part, 'section': section})
    return http_get(url)


def _text(element):
    return re.sub(r'\s+', ' ', ''.join(element.itertext())).strip()


def parse_regulation_xml(xml_bytes):
    """XML eCFR → lignes de texte et sections de premier niveau (a), (b), (c)…

    Une ligne = un paragraphe officiel. Les sous-paragraphes (1), (i), (A) restent dans
    la section de premier niveau qui les contient. Le « (i) » romain est distingué de la
    lettre (i) par l'ordre attendu des lettres.
    """
    root = ET.fromstring(xml_bytes)
    heading = _text(root.find('HEAD')) if root.find('HEAD') is not None else root.get('N', '')
    lines = [heading]
    sections = []
    expected = 0
    for element in root:
        if element.tag == 'HEAD':
            continue
        text = _text(element)
        if not text:
            continue
        if element.tag == 'CITA':
            lines.append('Source: ' + text.strip('[]'))
            continue
        match = re.match(r'^\(([a-z])\)\s*', text)
        if match and expected < len(LETTERS) and match.group(1) == LETTERS[expected]:
            title = text[match.end():]
            italic = element.find('I')
            if italic is not None and _text(italic) and text[match.end():].startswith(_text(italic)[:10]):
                title = _text(italic)
            title = re.split(r'—|\.\s|\(\d\)', title, maxsplit=1)[0].strip(' .—')[:90]
            sections.append({'section': match.group(1), 'title': title or f'Paragraph ({match.group(1)})',
                             'start_line': len(lines) + 1})
            expected += 1
        lines.append(text)
    if not sections:
        sections.append({'section': 'a', 'title': heading, 'start_line': 2})
    # Le titre (ligne 1) est rattaché à la première section ; chaque ligne est couverte une fois.
    sections[0]['start_line'] = 1
    for current, following in zip(sections, sections[1:] + [None]):
        current['end_line'] = (following['start_line'] - 1) if following else len(lines)
    return {'heading': heading, 'lines': lines, 'sections': sections}


# --------------------------------------------------------------------------- plaintes
ALIASES = {
    'consumer_complaint_narrative': 'narrative', 'complaint_what_happened': 'narrative', 'narrative': 'narrative',
    'date_received': 'date_received', 'product': 'product', 'sub_product': 'sub_product', 'issue': 'issue',
    'sub_issue': 'sub_issue', 'company': 'company', 'state': 'state', 'complaint_id': 'complaint_id',
    'company_response_to_consumer': 'company_response', 'company_response': 'company_response',
}


def normalize_key(key):
    return re.sub(r'[^a-z0-9]+', '_', (key or '').strip().lower()).strip('_')


def normalize_row(raw):
    row = {}
    for key, value in raw.items():
        name = ALIASES.get(normalize_key(key))
        if name:
            row[name] = (value or '').strip() if isinstance(value, str) else value
    return row


def parse_date(value):
    value = (value or '').strip()[:10]
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y'):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError(f'Date de réception illisible : {value!r}')


def iter_archive_rows(path):
    """Lit les plaintes d'une archive CFPB (.zip contenant CSV ou JSON) sans tout charger en mémoire."""
    csv.field_size_limit(10 ** 8)
    with zipfile.ZipFile(path) as archive:
        members = [m for m in archive.namelist() if m.lower().endswith(('.csv', '.json', '.jsonl'))]
        if not members:
            raise ValueError(f'Aucun fichier CSV/JSON dans {path}')
        for member in members:
            with archive.open(member) as binary:
                if member.lower().endswith('.csv'):
                    text = io.TextIOWrapper(binary, encoding='utf-8-sig', newline='')
                    for raw in csv.DictReader(text):
                        yield normalize_row(raw)
                elif member.lower().endswith('.jsonl'):
                    for line in io.TextIOWrapper(binary, encoding='utf-8'):
                        if line.strip():
                            raw = json.loads(line)
                            yield normalize_row(raw.get('_source', raw))
                else:
                    data = json.load(io.TextIOWrapper(binary, encoding='utf-8'))
                    rows = data if isinstance(data, list) else data.get('hits', {}).get('hits', data.get('data', []))
                    for raw in rows:
                        yield normalize_row(raw.get('_source', raw))


def api_metadata(api, rules, period, limit=4000, log=print):
    """Catégories officielles par plainte, via l'API CFPB (qui ne renvoie plus les narratifs).

    Sert uniquement si l'archive des narratifs ne contient pas produit/issue : la jointure
    se fait alors sur ``complaint_id``.
    """
    metadata = {}
    for rule in rules:
        params = [('has_narrative', 'true'), ('no_aggs', 'true'), ('size', '100'),
                  ('date_received_min', period[0]), ('date_received_max', period[1]),
                  ('sort', 'created_date_desc')]
        params += [('product', p) for p in rule['product']]
        if rule['sub_issue']:
            params += [('issue', f'{i}\u2022{s}') for i in rule['issue'] for s in rule['sub_issue']]
        else:
            params += [('issue', i) for i in rule['issue']]
        offset = 0
        while offset < limit:
            url = api + '?' + urllib.parse.urlencode(params + [('frm', str(offset))])
            hits = json.loads(http_get(url))['hits']['hits']
            for hit in hits:
                source = hit['_source']
                metadata[str(source['complaint_id'])] = normalize_row(source) | {'complaint_id': str(source['complaint_id'])}
            if len(hits) < 100:
                break
            offset += 100
            time.sleep(0.3)
        log(f"    {rule['id']} : {sum(1 for m in metadata.values() if rule_matches(rule, m))} plaintes référencées par l'API")
    return metadata


def enrich_rows(rows, metadata):
    """Complète les lignes de l'archive par les catégories de l'API si elles manquent."""
    for row in rows:
        if row.get('product') and row.get('issue'):
            yield row
            continue
        extra = metadata.get(str(row.get('complaint_id', '')).strip())
        if extra:
            yield extra | {k: v for k, v in row.items() if v}


def peek_has_categories(path):
    for row in iter_archive_rows(path):
        return bool(row.get('product') and row.get('issue'))
    return False


def in_period(row, period):
    try:
        return period[0] <= parse_date(row.get('date_received')) <= period[1]
    except ValueError:
        return False


def rule_matches(rule, row):
    if row.get('product') not in rule['product'] or row.get('issue') not in rule['issue']:
        return False
    return not rule['sub_issue'] or row.get('sub_issue') in rule['sub_issue']


def stable_order(seed, complaint_id):
    return hashlib.sha256(f'{seed}|{complaint_id}'.encode()).hexdigest()


def select_complaints(rows, rules, quotas, selection):
    """Sélection déterministe : pour chaque règle, les plaintes au narratif exploitable,
    ordonnées par empreinte de leur identifiant (aucun choix manuel, aucun tri par contenu)."""
    low, high = selection['narrative_min_chars'], selection['narrative_max_chars']
    buckets = {rule['id']: [] for rule in rules}
    for row in rows:
        narrative = row.get('narrative') or ''
        if not (low <= len(narrative) <= high) or not row.get('complaint_id'):
            continue
        for rule in rules:
            if quotas.get(rule['id']) and rule_matches(rule, row):
                buckets[rule['id']].append(row)
                break
    chosen, seen_text = {}, set()
    for rule_id, candidates in buckets.items():
        # L'ordre ne dépend que de l'identifiant : le résultat est le même quel que soit l'ordre de l'archive.
        candidates.sort(key=lambda r: stable_order(selection['seed'], r['complaint_id']))
        unique = []
        for row in candidates:
            fingerprint = hashlib.sha256(re.sub(r'\s+', ' ', row['narrative'].lower()).encode()).hexdigest()
            if fingerprint not in seen_text:  # narratifs dupliqués écartés
                seen_text.add(fingerprint)
                unique.append(row)
        buckets[rule_id] = unique
        chosen[rule_id] = unique[:quotas.get(rule_id, 0)]
    return chosen, {rule_id: len(candidates) for rule_id, candidates in buckets.items()}


def locate_archive(home, location):
    """Archive déjà présente : chemin donné, data/cfpb/raw/downloads/ ou dossier Téléchargements de l'utilisateur."""
    path = Path(location)
    if path.exists():
        return path
    name = Path(urllib.parse.urlparse(str(location)).path).name
    for folder in (Path(home) / 'data/cfpb/raw/downloads', Path.home() / 'Downloads', Path.home() / 'Téléchargements'):
        candidate = folder / name
        if candidate.exists() and zipfile.is_zipfile(candidate):
            return candidate
    return None


# --------------------------------------------------------------------------- étape 1 : download
def download(home, config, archives=None, log=print):
    home = Path(home)
    raw = home / 'data/cfpb/raw'
    (raw / 'ecfr').mkdir(parents=True, exist_ok=True)
    manifest = {'created_at': datetime.now(timezone.utc).isoformat(), 'regulations': [], 'complaints': {}}

    log('1/2 Règlements eCFR')
    # Source de chaque version, par ordre de priorité :
    #   1. un fichier data/cfpb/raw/ecfr/<section>_<date>.xml déjà présent (téléchargé depuis un navigateur :
    #      eCFR refuse les requêtes Python avec HTTP 406, mais pas les navigateurs) ;
    #   2. sinon l'API eCFR (versioner), si elle répond.
    missing = []
    for spec in config['regulations']:
        keep = spec.get('keep_versions', 1)
        local = sorted(p.stem.split('_', 1)[1] for p in (raw / 'ecfr').glob(f"{spec['section']}_*.xml"))
        if len(local) >= keep:
            dates, origin = local[-keep:], 'navigateur (fichier XML enregistré depuis ecfr.gov)'
        else:
            try:
                dates, origin = ecfr_versions(spec['part'], spec['section'])[-keep:], 'API eCFR (Python)'
            except urllib.error.HTTPError:
                missing.append(spec)
                continue
        for version_date in dates:
            target = raw / 'ecfr' / f"{spec['section']}_{version_date}.xml"
            url = f"{ECFR}/full/{version_date}/title-12.xml?part={spec['part']}&section={spec['section']}"
            if not target.exists():
                target.write_bytes(ecfr_xml(version_date, spec['part'], spec['section']))
                time.sleep(1.0)
            manifest['regulations'].append({'section': spec['section'], 'date': version_date,
                                            'file': str(target.relative_to(home)).replace('\\', '/'),
                                            'sha256': sha256_file(target), 'retrieved': origin, 'url': url})
            log(f"  {spec['section']} version du {version_date} ({origin})")
    if missing:
        lines = [f"  - § {spec['section']} : ouvrir {ECFR}/versions/title-12?part={spec['part']}&section={spec['section']} "
                 f"pour les dates, puis enregistrer {ECFR}/full/<date>/title-12.xml?part={spec['part']}"
                 f"&section={spec['section']} sous data/cfpb/raw/ecfr/{spec['section']}_<date>.xml"
                 for spec in missing]
        raise SystemExit('eCFR refuse les requêtes Python (HTTP 406). Enregistrez ces textes depuis un navigateur '
                         '(clic droit > Enregistrer sous), puis relancez :\n' + '\n'.join(lines))

    log('2/2 Plaintes CFPB (archives officielles des narratifs)')
    selection = config['selection']
    sources = archives or config['sources']['complaints']['archives']
    selected_rows = []
    for split_group, location in sources.items():
        path = locate_archive(home, location)
        if path is None:
            path = raw / 'downloads' / Path(urllib.parse.urlparse(location).path).name
            log(f'  Téléchargement {location}')
            try:
                download_file(location, path)
            except urllib.error.URLError as exc:
                raise SystemExit(f'Téléchargement refusé ({exc}). Ouvrez ce lien dans votre navigateur, '
                                 f'laissez le fichier dans Téléchargements, puis relancez :\n  {location}') from None
        if split_group == 'development':
            quotas = {r['id']: selection['per_rule']['train'] + selection['per_rule']['validation'] for r in config['label_rules']}
            rules = config['label_rules']
        else:
            quotas = {r['id']: selection['per_rule']['test'] for r in config['label_rules']}
            quotas |= {r['id']: selection['out_of_scope_per_rule']['test'] for r in config['out_of_scope_rules']}
            rules = config['label_rules'] + config['out_of_scope_rules']
        period = config['sources']['complaints']['periods'][split_group]
        rows = iter_archive_rows(path)
        if not peek_has_categories(path):
            log('  Archive sans catégories : jointure avec les catégories officielles de l\'API CFPB')
            rows = enrich_rows(rows, api_metadata(config['sources']['complaints']['api'], rules, period, log=log))
        rows = (r for r in rows if in_period(r, period))
        log(f'  Lecture de {path.name} …')
        chosen, available = select_complaints(rows, rules, quotas, selection)
        missing = {k: (len(v), quotas[k]) for k, v in chosen.items() if len(v) < quotas[k]}
        if missing:
            raise ValueError(f'Pas assez de plaintes pour certaines règles dans {path.name} : {missing}. '
                             'Vérifiez les libellés produit/issue dans configs/cfpb.json.')
        for rule_id, rows in chosen.items():
            for row in rows:
                selected_rows.append(dict(row, rule_id=rule_id, source_group=split_group,
                                          source_archive=path.name))
        manifest['complaints'][split_group] = {'archive': path.name, 'url': location if '://' in str(location) else None,
                                               'sha256': sha256_file(path), 'candidates_per_rule': available,
                                               'selected_per_rule': {k: len(v) for k, v in chosen.items()}}
        log('  ' + ', '.join(f'{k}: {len(v)}/{available[k]}' for k, v in chosen.items()))
    write_jsonl(raw / 'complaints_selected.jsonl', selected_rows)
    manifest['complaints_file_sha256'] = sha256_file(raw / 'complaints_selected.jsonl')
    (raw / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    return manifest


# --------------------------------------------------------------------------- versions eCFR
def regulation_versions(home, config):
    """Versions of each regulation section in the raw snapshot, ordered by eCFR version date.

    ``date`` is the eCFR version date of the XML file (2017-01-01 is the earliest date offered by the
    eCFR versioner, i.e. "in force at least since"); ``until`` is the date of the next version, if any.
    """
    home = Path(home)
    manifest = json.loads((home / 'data/cfpb/raw/manifest.json').read_text(encoding='utf-8'))
    by_section = {}
    for entry in manifest['regulations']:
        by_section.setdefault(entry['section'], []).append(entry)
    result = []
    for spec in config['regulations']:
        entries = sorted(by_section[spec['section']], key=lambda e: e['date'])
        for index, entry in enumerate(entries):
            path = home / entry['file']
            if sha256_file(path) != entry['sha256']:
                raise ValueError(f'SHA-256 du fichier brut différent du manifeste : {entry["file"]}')
            result.append({'policy_id': spec['policy_id'], 'cfr_section': spec['section'], 'category': spec['category'],
                           'regulation': spec['regulation'], 'version': f'{index + 1}.0', 'date': entry['date'],
                           'until': entries[index + 1]['date'] if index + 1 < len(entries) else None,
                           'file': entry['file'], 'sha256': entry['sha256'],
                           'url': f"https://www.ecfr.gov/on/{entry['date']}/title-12/section-{spec['section']}",
                           'parsed': parse_regulation_xml(path.read_bytes())})
    return result


# --------------------------------------------------------------------------- étape 2 : build
def build(home, config, log=print):
    """Instantané brut → plaintes annotées (questions.jsonl, train/validation). Hors ligne et déterministe."""
    home = Path(home)
    raw, out = home / 'data/cfpb/raw', home / 'data/cfpb'
    versions = {}  # policy_id -> [(version, effective_date, effective_until, sections)]
    for entry in regulation_versions(home, config):
        versions.setdefault(entry['policy_id'], []).append(
            (entry['version'], entry['date'], entry['until'], {x['section'] for x in entry['parsed']['sections']}))
    for policy_id, items in versions.items():
        log(f"  {policy_id} : {len(items)} version(s)")

    def resolve(reference, incident):
        policy_id, section = reference.split('#')
        for version, start, until, sections in versions[policy_id]:
            if start <= incident and (until is None or incident < until):
                if section not in sections:
                    raise ValueError(f'Section absente : {reference} (version {version})')
                return f'{policy_id}@{version}#{section}'
        raise ValueError(f'Aucune version de {policy_id} en vigueur le {incident}')

    rules = {r['id']: r for r in config['label_rules']}
    scope = {r['id']: r for r in config['out_of_scope_rules']}
    rows = read_jsonl(raw / 'complaints_selected.jsonl')
    # Une même plainte type peut être déposée plusieurs fois (ex. lettres de contestation modèles) :
    # tout texte présent dans le test est retiré de l'entraînement et de la validation.
    norm = lambda text: re.sub(r'\s+', ' ', text.strip().casefold())
    test_texts = {norm(r['narrative']) for r in rows if r['source_group'] == 'test'}
    leaked = [r['complaint_id'] for r in rows if r['source_group'] == 'development' and norm(r['narrative']) in test_texts]
    rows = [r for r in rows if r['complaint_id'] not in leaked or r['source_group'] == 'test']
    if leaked:
        log(f'  {len(leaked)} plainte(s) d’entraînement retirée(s) : texte identique à une plainte du test')
    questions = {'test': [], 'train': [], 'validation': []}
    per_rule_dev = {}
    for row in sorted(rows, key=lambda r: (r['rule_id'], stable_order(config['selection']['seed'], r['complaint_id']))):
        incident = parse_date(row['date_received'])
        rule = rules.get(row['rule_id']) or scope[row['rule_id']]
        relevant = [resolve(ref, incident) for ref in rule.get('relevant', [])]
        if row['source_group'] == 'development':
            rank = per_rule_dev.setdefault(row['rule_id'], 0)
            per_rule_dev[row['rule_id']] += 1
            split = 'train' if rank < config['selection']['per_rule']['train'] else 'validation'
        else:
            split = 'test'
        questions[split].append({
            'question_id': f"CFPB-{row['complaint_id']}", 'complaint_id': row['complaint_id'],
            'question': row['narrative'], 'incident_date': incident,
            'product': row.get('product'), 'sub_product': row.get('sub_product'), 'issue': row.get('issue'),
            'sub_issue': row.get('sub_issue'), 'company': row.get('company'), 'state': row.get('state'),
            'company_response': row.get('company_response'),
            'rule_id': row['rule_id'], 'rule_title': rule['title'], 'family': rule.get('family', 'out_of_scope'),
            'relevant_sections': relevant, 'scenario_group': row['rule_id'], 'language': 'en', 'split': split,
            'source': f"CFPB Consumer Complaint Database — {row['source_archive']}",
            'label_method': 'rule-based mapping from official CFPB product/issue/sub-issue (configs/cfpb.json); not legal review'})
    write_jsonl(out / 'evaluation/questions.jsonl', questions['test'])
    write_jsonl(out / 'training/train.jsonl', questions['train'])
    write_jsonl(out / 'training/validation.jsonl', questions['validation'])
    summary = {k: len(v) for k, v in questions.items()}
    summary['out_of_scope_test'] = sum(not q['relevant_sections'] for q in questions['test'])
    summary['removed_duplicates'] = len(leaked)
    (out / 'provenance.json').write_text(json.dumps({
        'built_at': datetime.now(timezone.utc).isoformat(), 'raw_manifest_sha256': sha256_file(raw / 'manifest.json'),
        'config_sha256': sha256_file(home / 'configs/cfpb.json'), 'counts': summary,
        'sources': config['sources'],
        'notes': ['Plaintes réelles, narratifs publiés par la CFPB avec consentement et expurgés (XXXX).',
                  'Les narratifs ne sont pas vérifiés par la CFPB ; ce sont des déclarations de consommateurs.',
                  'Labels de pertinence : correspondance déterministe catégorie CFPB → paragraphe réglementaire, sans revue juridique.',
                  'Split temporel : entraînement/validation nov.–déc. 2024, test janv.–févr. 2025.']},
        indent=2, ensure_ascii=False), encoding='utf-8')
    log('  questions : ' + json.dumps(summary))
    return summary
