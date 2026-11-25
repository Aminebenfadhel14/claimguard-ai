"""Configuration selection on development runs and RESULTS.md generated from measured reports only."""
import json

from claimguard.config import BENCHMARK, REPORTS, settings, write_json
from claimguard.evaluation import STRATEGIES, strategy_name


def load(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def runs(split):
    return [r for r in (load(p) for p in sorted((REPORTS / 'runs').glob(f'*_{split}_*.json'))) if r]


def run_key(run):
    return run['collection'], run['n_candidates'], run['rewrite']


def select():
    """Apply the selection rule declared in configs/rag.json to the development runs."""
    cfg = settings()['benchmark']['selection']
    metrics, tie = cfg['metrics'], cfg['tie_break']
    paired = {}
    for run in runs('development'):
        paired.setdefault(run_key(run), {})[run['suite']] = run
    reference = settings()['chunking']['reference']
    candidates = []
    for (collection, n, rewrite), suites in paired.items():
        if set(suites) != {'documents', 'cfpb'}:
            continue
        for mode, rerank in STRATEGIES:
            name = strategy_name(mode, rerank)
            values = [suites[s]['results'][name]['metrics'] for s in ('documents', 'cfpb')]
            primary = [values[0][metrics['documents']], values[1][metrics['cfpb']]]
            simplicity = (rerank, rewrite, collection != f"claimguard_c{reference['chunk_size']}_o{reference['chunk_overlap']}",
                          n != settings()['retrieval']['n_candidates'])
            candidates.append({'collection': collection, 'n_candidates': n, 'rewrite': rewrite, 'mode': mode,
                               'rerank': rerank, 'score': sum(primary) / 2,
                               'tie_break': sum(v[tie] for v in values) / 2,
                               'documents': primary[0], 'cfpb': primary[1], 'simplicity': simplicity})
    if not candidates:
        raise SystemExit('Aucune paire de runs de développement (documents + cfpb) : lancez « develop ».')
    candidates.sort(key=lambda c: (-round(c['score'], 6), -round(c['tie_break'], 6), c['simplicity']))
    chosen = candidates[0]
    selection = {'rule': cfg['rule'], 'amendment': cfg.get('amendment'), 'metrics': metrics, 'chosen': {k: v for k, v in chosen.items() if k != 'simplicity'},
                 'ranking': [{k: v for k, v in c.items() if k != 'simplicity'} for c in candidates]}
    write_json(REPORTS / 'selection.json', selection)
    return selection


def fmt(value, digits=3):
    return '—' if value is None else f'{value:.{digits}f}'


def table(run, k):
    keys = [f'precision@{k}', f'recall@{k}', f'hit@{k}', f'mrr@{k}', f'ndcg@{k}']
    if run['suite'] == 'cfpb':
        keys.append(f'paragraph_recall@{k}')
    lines = ['| Stratégie | ' + ' | '.join(keys) + ' | Latence p50 | Latence p95 |',
             '|---|' + '---:|' * (len(keys) + 2)]
    for mode, rerank in STRATEGIES:
        name = strategy_name(mode, rerank)
        r = run['results'][name]
        lines.append(f'| {name} | ' + ' | '.join(fmt(r['metrics'].get(key)) for key in keys)
                     + f" | {fmt(r['latency_ms']['p50'], 0)} ms | {fmt(r['latency_ms']['p95'], 0)} ms |")
    return lines


def describe(run):
    return (f"collection `{run['collection']}`, {run['n_candidates']} candidats, k={run['k']}, "
            f"réécriture {'Groq (' + run['llm'] + ')' if run['rewrite'] else 'désactivée'} ; "
            f"{run['questions_evaluated']}/{run['questions_total']} questions évaluées")


def effects(dev, metrics):
    """Mean effect of one factor on the development runs, all other factors held equal."""
    reference = settings()['chunking']['reference']
    ref_collection = f"claimguard_c{reference['chunk_size']}_o{reference['chunk_overlap']}"
    ref_n = settings()['retrieval']['n_candidates']
    index = {(r['suite'], r['collection'], r['n_candidates'], r['rewrite']): r for r in dev}

    def mean(run, strategies, metric):
        values = [run['results'][s]['metrics'][metric] for s in strategies]
        return sum(values) / len(values)

    names = [strategy_name(m, r) for m, r in STRATEGIES]
    plain = [n for n in names if '+rerank' not in n]
    reranked = [n for n in names if '+rerank' in n]
    lines = ['## Analyse sur le développement (effets moyens mesurés)', '',
             f"Chaque ligne compare deux runs qui ne diffèrent que par un facteur (autres facteurs : "
             f"`{ref_collection}`, {ref_n} candidats, sans réécriture), moyenne sur les stratégies indiquées. "
             f"Mesures : documents {metrics['documents']}, CFPB {metrics['cfpb']}.", '',
             '| Facteur | Stratégies | Documents A → B | CFPB A → B |', '|---|---|---:|---:|']
    comparisons = [
        ('Réécriture Groq (non → oui)', names, (ref_collection, ref_n, False), (ref_collection, ref_n, True)),
        ('Réécriture Groq (non → oui), sans reranking', plain, (ref_collection, ref_n, False), (ref_collection, ref_n, True)),
        ('Réécriture Groq (non → oui), avec reranking', reranked, (ref_collection, ref_n, False), (ref_collection, ref_n, True)),
        (f'Candidats ({ref_n} → 40), avec reranking', reranked, (ref_collection, ref_n, False), (ref_collection, 40, False)),
        ('Découpage (1000/100 → 500/50)', names, (ref_collection, ref_n, False), ('claimguard_c500_o50', ref_n, False)),
    ]
    for label, strategies, a, b in comparisons:
        cells = []
        for suite in ('documents', 'cfpb'):
            ra, rb = index.get((suite, *a)), index.get((suite, *b))
            cells.append(f"{fmt(mean(ra, strategies, metrics[suite]))} → {fmt(mean(rb, strategies, metrics[suite]))}"
                         if ra and rb else '—')
        lines.append(f"| {label} | {', '.join(strategies)} | {cells[0]} | {cells[1]} |")
    for suite in ('documents', 'cfpb'):
        run = index.get((suite, ref_collection, ref_n, False))
        if run:
            pairs = [f"{n}: {fmt(run['results'][n]['metrics'][metrics[suite]])} → "
                     f"{fmt(run['results'][n + '+rerank']['metrics'][metrics[suite]])}" for n in plain]
            lines.append(f"| CrossEncoder (sans → avec), {suite} | — | {'; '.join(pairs) if suite == 'documents' else ''} | "
                         f"{'; '.join(pairs) if suite == 'cfpb' else ''} |")
    return lines + ['']


def write_results():
    cfg = settings()
    k = cfg['retrieval']['k']
    lines = ['# Résultats mesurés — ClaimGuard AI v3', '',
             'Document généré par `python -m claimguard report` à partir des fichiers de `reports/v3/` ; '
             'aucun nombre n’est saisi à la main.', '',
             f"Cours : {cfg['course']['repository']} — révision `{cfg['course']['revision']}` "
             f"({', '.join(cfg['course']['folders'])}).", '',
             f"Modèles : `{cfg['models']['dense']}`, `{cfg['models']['sparse']}`, `{cfg['models']['reranker']}`.", '',
             '**Non comparable aux rapports v2** (`reports/archive/v2_sections/`) : l’unité de mesure passe de la '
             'section au chunk Qdrant, les chunks et la chaîne de recherche ont changé, et un nouveau benchmark '
             'documentaire est ajouté.', '']
    generation = load(BENCHMARK / 'questions_generation.json')
    if generation:
        reasons = {}
        for r in generation['rejected']:
            reasons[r['reason']] = reasons.get(r['reason'], 0) + 1
        lines += ['## Benchmark documentaire (méthode du cours)', '',
                  f"{generation['accepted']} questions générées par `{generation['model']}` à partir des "
                  f"{generation['paragraphs']} paragraphes en vigueur le {generation['as_of']} ; passage justificatif "
                  f"vérifié dans le paragraphe source. Rejets ou échecs : {reasons or 'aucun'}. "
                  f"Répartition par paragraphe : {generation['splits']}.", '']
    selection = load(REPORTS / 'selection.json')
    test_runs = runs('test')
    for suite, title in (('documents', 'Test — benchmark documentaire'), ('cfpb', 'Test — plaintes CFPB réelles')):
        for run in [r for r in test_runs if r['suite'] == suite]:
            lines += [f'## {title}', '', describe(run) + '.', '']
            if run['questions_without_qrels']:
                label = ('Plaintes hors périmètre (aucun paragraphe annoté), exclues des métriques de recherche et '
                         'utilisées pour l’abstention' if suite == 'cfpb'
                         else 'Questions sans chunk pertinent (signalées, exclues des moyennes)')
                lines += [f"{label} : {len(run['questions_without_qrels'])} — "
                          f"{', '.join(run['questions_without_qrels'])}.", '']
            if run['rewrite_failures']:
                lines += [f"Réécritures échouées (texte original utilisé) : {len(run['rewrite_failures'])}.", '']
            lines += table(run, k) + ['']
            if suite == 'cfpb':
                lines += [run['annotation'], '', run['date_filter'], '']
                rules = sorted({r for v in run['results'].values() for r in v.get('recall_by_rule', {})})
                lines += [f'recall@{k} (chunk) par règle d’annotation :', '',
                          '| Stratégie | ' + ' | '.join(rules) + ' |', '|---|' + '---:|' * len(rules)]
                for name, value in run['results'].items():
                    lines.append(f'| {name} | ' + ' | '.join(fmt(value['recall_by_rule'].get(r)) for r in rules) + ' |')
                lines.append('')
            t, c = run['truncation']['queries'], run['truncation'].get('chunks')
            lines += [f"Requêtes plus longues que la limite du modèle dense ({t['max_seq_length']} tokens, tronquées) : "
                      f"{t['truncated']}/{t['count']} (médiane {t['median_tokens']} tokens)."
                      + (f" Chunks tronqués par le modèle dense : {c['truncated']}/{c['count']} (médiane {c['median_tokens']} tokens)." if c else ''), '']
    if selection:
        c = selection['chosen']
        lines += ['## Sélection sur le développement', '', selection['rule'], '', selection.get('amendment') or '', '',
                  f"Configuration retenue (avant le test) : `{c['collection']}`, {c['n_candidates']} candidats, "
                  f"réécriture {'oui' if c['rewrite'] else 'non'}, {strategy_name(c['mode'], c['rerank'])} — "
                  f"développement : documents {selection['metrics']['documents']} {fmt(c['documents'])}, "
                  f"CFPB {selection['metrics']['cfpb']} {fmt(c['cfpb'])}.", '',
                  f"| Rang | Collection | Candidats | Réécriture | Stratégie | {selection['metrics']['documents']} docs | "
                  f"{selection['metrics']['cfpb']} CFPB | Moyenne |",
                  '|---:|---|---:|---|---|---:|---:|---:|']
        for i, r in enumerate(selection['ranking'], 1):
            lines.append(f"| {i} | {r['collection']} | {r['n_candidates']} | {'oui' if r['rewrite'] else 'non'} | "
                         f"{strategy_name(r['mode'], r['rerank'])} | {fmt(r['documents'])} | {fmt(r['cfpb'])} | {fmt(r['score'])} |")
        lines.append('')
    dev = runs('development')
    if dev and selection:
        lines += effects(dev, selection['metrics'])
    if dev:
        lines += ['## Développement — détail des runs', '']
        for run in dev:
            lines += [f"### {run['suite']} — {describe(run)}", ''] + table(run, k) + ['']
    gen = load(REPORTS / 'generation.json')
    lines += ['## Génération (évaluée séparément de la recherche)', '']
    if gen:
        s = gen['summary']
        lines += [f"Modèle `{gen['model']}`, options {gen['options']}, {s['total']} questions de test. "
                  f"Échecs de génération : {s['generation_failures']} ; échecs de réécriture : {s['rewrite_failures']} ; "
                  f"passages conservés en cas d’échec : {'oui' if s['passages_kept_on_generation_error'] else 'non'}. "
                  f"Citations retrouvées mot pour mot : {fmt(s['citation_verified_rate'])}.", '',
                  '| Groupe | Questions | Échecs | Taux d’abstention | Réponse avec citation vérifiée |', '|---|---:|---:|---:|---:|']
        for group, g in s['groups'].items():
            lines.append(f"| {group} | {g['count']} | {g['failures']} | {fmt(g['abstention_rate'])} | "
                         f"{fmt(g['answered_with_verified_citation'])} |")
        lines += ['', f"Documents : nombres de la réponse de référence présents dans la réponse générée : "
                      f"{fmt(s['groups']['documents'].get('reference_numbers_in_answer'))} (indicateur lexical).", '']
        lines += [f'- {n}' for n in gen['notes']] + ['']
    else:
        lines += ['Non évaluée (`python -m claimguard generation`).', '']
    lines += ['## Limites', '',
              '- Corpus réduit : 8 sections réglementaires (11 versions) ; échantillons de test modestes, '
              'écarts de quelques points non significatifs.',
              '- Questions documentaires générées par un LLM à partir des textes : plus faciles que des plaintes réelles.',
              '- Le hit@5 documentaire est proche de 1 pour toutes les stratégies : ce benchmark discrimine peu ; '
              'la sélection est surtout décidée par le benchmark CFPB, lui-même à labels faibles.',
              '- Labels CFPB faibles (catégorie -> paragraphe) ; date de réception utilisée comme date de référence.',
              '- Une part importante des plaintes dépasse la fenêtre de 256 tokens du modèle dense (fin tronquée) ; '
              'la réécriture supprime cette troncature mais n’améliore pas les mesures sur le développement.',
              '- Sur les plaintes hors périmètre, une partie des réponses ne s’abstient pas et cite des passages '
              'existants mais non applicables : la vérification des citations ne détecte pas ce cas.',
              '- Le quota journalier Groq de `openai/gpt-oss-20b` a été épuisé pendant la génération des questions ; '
              'questions, réécritures et réponses ont toutes été produites avec `openai/gpt-oss-120b` '
              '(`reasoning_effort=low`).',
              '- Mesures CPU sur une seule machine ; la latence Groq dépend d’un service externe.', '']
    (REPORTS / 'RESULTS.md').write_text('\n'.join(lines), encoding='utf-8')
    return REPORTS / 'RESULTS.md'
