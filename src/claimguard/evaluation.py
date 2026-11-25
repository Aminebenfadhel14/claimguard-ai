"""Retrieval evaluation following labs 05-Evaluation/Retrieval Evaluation (01, 02, 03).

Two benchmarks, never mixed:

* ``documents``: questions generated from the indexed regulations, each with a verified supporting
  passage; qrels = Qdrant chunk ids sharing 5 consecutive words with that passage (course method).
* ``cfpb``: real CFPB complaints with weak labels (CFPB category -> paragraph, configs/cfpb.json, no
  legal review). Qrels = ids of the chunks of the labelled paragraphs.

Answer generation is evaluated separately (``evaluate_generation``) and never enters retrieval metrics.
"""
import hashlib
import json
import math
import re
import statistics
import time
from datetime import datetime, timezone

from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from claimguard.config import (BENCHMARK, DATA, REPORTS, collection_name, groq_model_name, qdrant_url, read_jsonl,
                               settings, write_json, write_jsonl)
from claimguard.rag import MODES, doc_id, in_force

STRATEGIES = [(mode, rerank) for mode in MODES for rerank in (False, True)]


def strategy_name(mode, rerank):
    return f"{mode}{'+rerank' if rerank else ''}"


# --------------------------------------------------------------------------- metrics (notebook 03)
def precision(k, q_rels, q_ret):
    """Relevant retrieved chunks among the first k, divided by k (notebook formula, ids deduplicated)."""
    q_ret = list(dict.fromkeys(q_ret))[:k]
    return sum(doc in set(q_rels) for doc in q_ret) / k


def recall(k, q_rels, q_ret):
    """Relevant chunks found in the first k, divided by the number of relevant chunks (0 if none)."""
    q_rels = set(q_rels)
    q_ret = list(dict.fromkeys(q_ret))[:k]
    return sum(doc in q_rels for doc in q_ret) / len(q_rels) if q_rels else 0.0


def mrr(k, q_rels, q_ret):
    q_ret = list(dict.fromkeys(q_ret))[:k]
    return next((1 / rank for rank, doc in enumerate(q_ret, 1) if doc in set(q_rels)), 0.0)


def ndcg(k, q_rels, q_ret):
    q_rels, q_ret = set(q_rels), list(dict.fromkeys(q_ret))[:k]
    dcg = sum(1 / math.log2(i + 2) for i, doc in enumerate(q_ret) if doc in q_rels)
    ideal = sum(1 / math.log2(i + 2) for i in range(min(k, len(q_rels))))
    return dcg / ideal if ideal else 0.0


def hit(k, q_rels, q_ret):
    """1 if at least one relevant chunk is in the first k (independent of the number of relevant chunks)."""
    return float(any(doc in set(q_rels) for doc in list(dict.fromkeys(q_ret))[:k]))


def score(k, q_rels, q_ret):
    return {f'precision@{k}': precision(k, q_rels, q_ret), f'recall@{k}': recall(k, q_rels, q_ret),
            f'hit@{k}': hit(k, q_rels, q_ret),
            f'mrr@{k}': mrr(k, q_rels, q_ret), f'ndcg@{k}': ndcg(k, q_rels, q_ret)}


# --------------------------------------------------------------------------- questions (script 01)
class Question(BaseModel):
    question: str
    passage: str     # exact passage copied from the regulation
    paragraph: str   # letter of the paragraph where the passage is, e.g. "b"
    answer: str


class QuestionList(BaseModel):
    questions: list[Question]


QUESTION_PROMPT = '''
You are creating a benchmark to evaluate a RAG system on US federal consumer-finance regulations.

Read the regulation paragraphs below and generate {n} questions.

Rules:
- The answer must be written in the text.
- Copy the passage that contains the answer EXACTLY, word for word (1 to 3 sentences).
- Give the letter of the paragraph of the passage (the letter after "=== PARAGRAPH").
- The question must mention the regulation or the subject of the section, so it is clear which
  regulation it is about, but must not quote the section number.
- Do not ask about citations, Federal Register references or paragraph numbers.

Answer ONLY with JSON in this format:
{{
  "questions": [
    {{
      "question": "...",
      "passage": "exact passage copied from the text",
      "paragraph": "a",
      "answer": "..."
    }}
  ]
}}

Regulation: {source}

{paragraphs}
'''


def normalize(text):
    return re.sub(r'[^a-z0-9]', '', text.lower())   # keep only letters and digits (script 01)


def split_of(key):
    """Deterministic development/test assignment by paragraph, so a paragraph is never in both splits."""
    cfg = settings()['benchmark']
    digest = hashlib.sha256(f"{cfg['split_seed']}|{key}".encode()).hexdigest()
    return 'test' if int(digest[:8], 16) / 0xFFFFFFFF < cfg['test_fraction'] else 'development'


def generate_questions(llm, documents, log=print):
    """Questions from the paragraphs in force on benchmark.as_of. Rejections and failures are recorded."""
    cfg = settings()['benchmark']
    day = int(cfg['as_of'].replace('-', ''))
    current = [d for d in documents if d.metadata['valid_from_int'] <= day < d.metadata['valid_until_int']]
    structured = llm.with_structured_output(QuestionList, method='json_mode')
    by_source = {}
    for d in current:
        by_source.setdefault(d.metadata['source'], []).append(d)
    accepted, rejected = [], []
    cache_path = BENCHMARK / 'question_windows.jsonl'
    cache = {r['key']: r for r in read_jsonl(cache_path)} if cache_path.exists() else {}
    for source, paragraphs in by_source.items():
        log(f'Processing: {source}')
        step = cfg['paragraphs_per_call']
        for i in range(0, len(paragraphs), step):
            window = paragraphs[i:i + step]
            text = ''.join(f"\n=== PARAGRAPH {p.metadata['paragraph']} ===\n{p.page_content}\n" for p in window)
            letters = [p.metadata['paragraph'] for p in window]
            prompt = QUESTION_PROMPT.format(n=cfg['questions_per_call'], paragraphs=text,
                                            source=f"{window[0].metadata['regulation']} — "
                                                   f"{window[0].metadata['section_title']}")
            key = hashlib.sha256(f'{groq_model_name()}|{prompt}'.encode()).hexdigest()
            result, errors = None, []
            if key in cache:  # successful window of a previous run (resumable after quota errors)
                result = QuestionList.model_validate(cache[key]['result'])
            for _ in range(0 if result else cfg.get('generation_attempts', 3)):  # json_mode can return invalid JSON
                try:
                    result = structured.invoke(prompt)
                    cache[key] = {'key': key, 'model': groq_model_name(), 'result': result.model_dump()}
                    write_jsonl(cache_path, cache.values())
                    break
                except Exception as error:
                    errors.append(f'{type(error).__name__}: {str(error)[:200]}')
                    time.sleep(cfg.get('groq_pause_seconds', 1))
            if result is None:  # one bad LLM answer must not stop the run; it is recorded
                rejected.append({'source': source, 'paragraphs': letters, 'reason': 'generation_failed',
                                 'errors': errors})
                log(f'  Failed paragraphs {letters}: {errors[-1][:80]}')
                continue
            if errors:
                rejected.append({'source': source, 'paragraphs': letters, 'reason': 'retried_after_error',
                                 'errors': errors})
            for q in result.questions:
                paragraph = next((p for p in window if p.metadata['paragraph'] == q.paragraph.strip('() ')), None)
                if paragraph is None or normalize(q.passage) not in normalize(paragraph.page_content):
                    rejected.append({'source': source, 'paragraphs': letters, 'reason': 'passage_not_found',
                                     'question': q.question, 'paragraph': q.paragraph, 'passage': q.passage})
                    log(f'  Rejected (passage not found): {q.question}')
                    continue
                m = paragraph.metadata
                accepted.append({'query_id': f'D{len(accepted) + 1:03d}', 'question': q.question, 'answer': q.answer,
                                 'source': source, 'cfr_section': m['cfr_section'], 'paragraph': m['paragraph'],
                                 'location': m['citation'], 'reference': m['reference'], 'passage': q.passage,
                                 'split': split_of(m['reference'])})
                log(f'  Added: {q.question}')
            if errors or key not in cache:
                time.sleep(cfg.get('groq_pause_seconds', 1))
    write_jsonl(BENCHMARK / 'questions.jsonl', accepted)
    write_json(BENCHMARK / 'questions_generation.json', {
        'created_at': now(), 'model': groq_model_name(), 'as_of': cfg['as_of'], 'paragraphs': len(current),
        'accepted': len(accepted), 'rejected': rejected,
        'splits': {s: sum(q['split'] == s for q in accepted) for s in ('development', 'test')}})
    log(f'{len(accepted)} questions saved, {len(rejected)} rejected or failed windows')
    return accepted


# --------------------------------------------------------------------------- qrels (script 02)
def words(text):
    """Lower-case alphanumeric tokens (the course splits on spaces; this also ignores punctuation)."""
    return re.findall(r'[a-z0-9]+', text.lower())


def ngrams(text, n):
    w = words(text)
    return {' '.join(w[i:i + n]) for i in range(len(w) - n + 1)}


def all_points(client, collection, flt=None):
    points, offset = [], None
    while True:
        batch, offset = client.scroll(collection, scroll_filter=flt, limit=256, offset=offset, with_payload=True)
        points += batch
        if offset is None:
            return points


def match_chunks(passage, chunks, frequency, n, limit):
    """(relevant ids, ids matched only through generic n-grams) among ``chunks`` = [(id, text)]."""
    grams = ngrams(passage, n)
    specific = {g for g in grams if frequency.get(g, 0) <= limit}
    relevant, generic_only = [], []
    for identifier, text in chunks:
        shared = grams & ngrams(text, n)
        if shared & specific:
            relevant.append(identifier)
        elif shared:
            generic_only.append(identifier)
    return relevant, generic_only


def build_qrels(collection, questions):
    """Chunks of the question's source and paragraph sharing at least one non-generic 5-gram with the passage.

    A 5-gram present in more than ``generic_ngram_max_chunks`` chunks in force is considered too general
    (boilerplate such as "for purposes of this section") and cannot make a chunk relevant on its own.
    """
    cfg = settings()['benchmark']
    n, limit = cfg['ngram'], cfg['generic_ngram_max_chunks']
    client = QdrantClient(url=qdrant_url())
    frequency = {}
    for point in all_points(client, collection, in_force(cfg['as_of'])):
        for gram in ngrams(point.payload['page_content'], n):
            frequency[gram] = frequency.get(gram, 0) + 1
    qrels, report = {}, {'collection': collection, 'created_at': now(), 'ngram': n, 'generic_limit': limit,
                         'no_match': [], 'only_generic_match': [], 'chunks_per_question': {}}
    for q in questions:
        flt = Filter(must=[FieldCondition(key='metadata.source', match=MatchValue(value=q['source'])),
                           FieldCondition(key='metadata.paragraph', match=MatchValue(value=q['paragraph']))])
        chunks = [(str(c.id), c.payload['page_content']) for c in all_points(client, collection, flt)]
        relevant, generic_only = match_chunks(q['passage'], chunks, frequency, n, limit)
        qrels[q['query_id']] = relevant
        report['chunks_per_question'][q['query_id']] = len(relevant)
        if not relevant:
            report['only_generic_match' if generic_only else 'no_match'].append(q['query_id'])
    client.close()
    write_json(BENCHMARK / f'qrels_{collection}.json', qrels)
    write_json(BENCHMARK / f'qrels_{collection}.report.json', report)
    return qrels, report


def cfpb_questions(split):
    """CFPB complaints: test = Jan.-Feb. 2025, development = train + validation (Nov.-Dec. 2024)."""
    if split == 'test':
        rows = read_jsonl(DATA / 'evaluation/questions.jsonl')
    else:
        rows = read_jsonl(DATA / 'training/train.jsonl') + read_jsonl(DATA / 'training/validation.jsonl')
    return rows


def check_cfpb_leakage():
    test = cfpb_questions('test')
    ids = {r['complaint_id'] for r in test}
    texts = {' '.join(r['question'].split()).casefold() for r in test}
    for r in cfpb_questions('development'):
        if r['complaint_id'] in ids or ' '.join(r['question'].split()).casefold() in texts:
            raise ValueError(f"Fuite entre développement et test : {r['question_id']}")


def check_documents_leakage(questions):
    splits = {}
    for q in questions:
        splits.setdefault(q['reference'], set()).add(q['split'])
    shared = [ref for ref, s in splits.items() if len(s) > 1]
    if shared:
        raise ValueError(f'Paragraphes présents en développement et en test : {shared}')


def cfpb_qrels(collection, questions):
    """Weak qrels: every chunk of the labelled paragraphs (annotation by CFPB category, not legal review)."""
    client = QdrantClient(url=qdrant_url())
    by_reference = {}
    for point in all_points(client, collection):
        by_reference.setdefault(point.payload['metadata']['reference'], []).append(str(point.id))
    client.close()
    missing = sorted({ref for q in questions for ref in q['relevant_sections'] if ref not in by_reference})
    if missing:
        raise ValueError(f'Paragraphes annotés absents de la collection : {missing}')
    return {q['question_id']: sorted({i for ref in q['relevant_sections'] for i in by_reference[ref]})
            for q in questions}


# --------------------------------------------------------------------------- rewriting (lab 13), cached
def rewritten_queries(rag, items, log=print):
    """Rewrite each question once with Groq; successful rewrites are cached by text and model.

    A failure falls back to the original question, is reported, and is retried on the next run."""
    path = BENCHMARK / 'rewrites.jsonl'
    cache = {r['key']: r for r in read_jsonl(path)} if path.exists() else {}
    result, failures = {}, []
    for identifier, text in items:
        key = hashlib.sha256(f'{groq_model_name()}|{text}'.encode()).hexdigest()
        if key in cache:
            entry = cache[key]
            result[identifier] = {'query': entry['query'], 'error': None, 'ms': entry['ms']}
            continue
        started = time.perf_counter()
        try:
            query = rag.rewrite(text) or text
            cache[key] = {'key': key, 'model': groq_model_name(), 'query': query,
                          'ms': (time.perf_counter() - started) * 1000}
            write_jsonl(path, cache.values())
            result[identifier] = {'query': query, 'error': None, 'ms': cache[key]['ms']}
        except Exception as error:
            failures.append(identifier)
            result[identifier] = {'query': text, 'error': f'{type(error).__name__}: {str(error)[:200]}', 'ms': None}
            log(f'  Rewrite failed for {identifier}: {type(error).__name__}')
        time.sleep(settings()['benchmark'].get('groq_pause_seconds', 1))
    return result, failures


# --------------------------------------------------------------------------- benchmark (notebook 03)
def now():
    return datetime.now(timezone.utc).isoformat()


def percentile(values, p):
    values = sorted(values)
    return values[max(0, math.ceil(p * len(values)) - 1)] if values else None


def truncation(rag, texts):
    """Share of texts longer than the dense model's maximum sequence length (silently truncated)."""
    model = rag.models.dense._client
    limit = model.max_seq_length
    lengths = [len(model.tokenizer(t, add_special_tokens=True)['input_ids']) for t in texts]
    return {'max_seq_length': limit, 'count': len(lengths), 'truncated': sum(x > limit for x in lengths),
            'median_tokens': statistics.median(lengths) if lengths else None}


def chunk_truncation(rag):
    try:
        client = QdrantClient(url=qdrant_url())
        texts = [p.payload['page_content'] for p in all_points(client, rag.collection)]
        client.close()
    except Exception:  # unit tests use doubles without Qdrant
        return None
    return truncation(rag, texts)


def run_benchmark(rag, suite, split, rewrite=False, n_candidates=None, k=None, log=print):
    """Six strategies (dense / sparse / hybrid, with and without CrossEncoder) on one split."""
    cfg = settings()
    k = k or cfg['retrieval']['k']
    n_candidates = n_candidates or cfg['retrieval']['n_candidates']
    collection = rag.collection
    if suite == 'documents':
        questions = read_jsonl(BENCHMARK / 'questions.jsonl')
        check_documents_leakage(questions)
        questions = [q for q in questions if q['split'] == split]
        qrels_path = BENCHMARK / f'qrels_{collection}.json'
        qrels = json.loads(qrels_path.read_text(encoding='utf-8'))
        items = [(q['query_id'], q['question'], cfg['benchmark']['as_of'], qrels.get(q['query_id'], []), {})
                 for q in questions]
    elif suite == 'cfpb':
        check_cfpb_leakage()
        questions = cfpb_questions(split)
        qrels = cfpb_qrels(collection, questions)
        items = [(q['question_id'], q['question'], q['incident_date'], qrels[q['question_id']],
                  {'relevant_paragraphs': q['relevant_sections'], 'rule_id': q['rule_id']}) for q in questions]
    else:
        raise ValueError('suite : documents ou cfpb')

    queries = {i: {'query': text, 'error': None, 'ms': None} for i, text, *_ in items}
    rewrite_failures = []
    if rewrite:
        queries, rewrite_failures = rewritten_queries(rag, [(i, text) for i, text, *_ in items], log)
    evaluated = [it for it in items if it[3]]
    without_qrels = [it[0] for it in items if not it[3]]

    results, per_question = {}, []
    warm = evaluated[0] if evaluated else items[0]
    for mode, rerank in STRATEGIES:
        name = strategy_name(mode, rerank)
        rag.retrieve(queries[warm[0]]['query'], mode=mode, rerank=rerank, k=k, n_candidates=n_candidates,
                     as_of=warm[2])  # warm-up, not measured
        totals, latencies = {}, []  # accumulators reset for EACH strategy (bug of the course notebook)
        for identifier, text, as_of, q_rels, extra in evaluated:
            started = time.perf_counter()
            documents = rag.retrieve(queries[identifier]['query'], mode=mode, rerank=rerank, k=k,
                                     n_candidates=n_candidates, as_of=as_of)
            latencies.append((time.perf_counter() - started) * 1000)
            q_ret = [doc_id(d) for d in documents]
            metrics = score(k, q_rels, q_ret)
            if suite == 'cfpb':
                found = {d.metadata['reference'] for d in documents} & set(extra['relevant_paragraphs'])
                metrics[f'paragraph_recall@{k}'] = len(found) / len(set(extra['relevant_paragraphs']))
            for key, value in metrics.items():
                totals[key] = totals.get(key, 0.0) + value
            per_question.append({'strategy': name, 'query_id': identifier, 'retrieved': q_ret,
                                 'retrieved_references': [d.metadata['reference'] for d in documents],
                                 'relevant': sorted(q_rels), 'metrics': metrics, 'latency_ms': latencies[-1]}
                                | ({'rule_id': extra['rule_id']} if suite == 'cfpb' else {}))
        count = len(evaluated)
        results[name] = {'mode': mode, 'rerank': rerank, 'questions': count,
                         'metrics': {key: value / count for key, value in totals.items()} if count else {},
                         'latency_ms': {'mean': statistics.mean(latencies) if latencies else None,
                                        'p50': percentile(latencies, .5), 'p95': percentile(latencies, .95)}}
        for key, value in results[name]['metrics'].items():
            if not 0 <= value <= 1:
                raise AssertionError(f'{key} hors de [0, 1] pour {name} : {value}')
        log(f"{name:16s} " + '  '.join(f'{key} {value:.3f}' for key, value in results[name]['metrics'].items()))

    if suite == 'cfpb':
        by_rule = {}
        for row in per_question:
            by_rule.setdefault(row['strategy'], {}).setdefault(row['rule_id'], []).append(row['metrics'][f'recall@{k}'])
        for name, rules in by_rule.items():
            results[name]['recall_by_rule'] = {r: statistics.mean(v) for r, v in sorted(rules.items())}
    rewrite_ms = [q['ms'] for q in queries.values() if q.get('ms')]
    report = {
        'schema': 'claimguard-retrieval-v3', 'created_at': now(), 'suite': suite, 'split': split,
        'collection': collection, 'chunking': collection.rsplit('_', 2)[1:], 'k': k, 'n_candidates': n_candidates,
        'rewrite': rewrite, 'llm': groq_model_name() if rewrite else None,
        'course': cfg['course'], 'models': cfg['models'],
        'unit': 'chunk (identifiant de point Qdrant)',
        'questions_total': len(items), 'questions_evaluated': len(evaluated),
        'questions_without_qrels': without_qrels, 'rewrite_failures': rewrite_failures,
        'rewrite_latency_ms': {'mean': statistics.mean(rewrite_ms) if rewrite_ms else None,
                               'p95': percentile(rewrite_ms, .95)},
        'truncation': {'queries': truncation(rag, [queries[i]['query'] for i, *_ in items]),
                       'chunks': chunk_truncation(rag)},
        'latency_protocol': 'CPU, après chargement des modèles et une requête d’échauffement par stratégie ; '
                            'hors appels LLM (réécriture mesurée à part).',
        'results': results, 'per_question': per_question,
        'queries': {i: q['query'] for i, q in queries.items()} if rewrite else None,
    }
    if suite == 'cfpb':
        report['annotation'] = ('Labels faibles : correspondance catégorie CFPB -> paragraphe (configs/cfpb.json), '
                                'sans revue juridique. Qrels = tous les chunks des paragraphes annotés. Les plaintes '
                                'hors périmètre (aucun paragraphe annoté) sont exclues des métriques de recherche.')
        report['date_filter'] = ('Version en vigueur à la date de réception de la plainte par la CFPB '
                                 '(date_received) : ce n’est pas la date des faits, inconnue.')
    tag = f"{suite}_{split}_{collection}_n{n_candidates}_{'rewrite' if rewrite else 'original'}"
    write_json(REPORTS / 'runs' / f'{tag}.json', report)
    return report


# --------------------------------------------------------------------------- generation (separate)
def evaluate_generation(rag, options, log=print):
    """Answers with the application pipeline on test questions. Errors stay in the denominator."""
    cfg = settings()['benchmark']['generation_sample']
    documents = [q for q in read_jsonl(BENCHMARK / 'questions.jsonl') if q['split'] == 'test'][:cfg['documents']]
    complaints = cfpb_questions('test')
    in_scope = [q for q in complaints if q['relevant_sections']]
    in_scope = in_scope[::max(1, len(in_scope) // cfg['cfpb_in_scope'])][:cfg['cfpb_in_scope']]
    out_scope = [q for q in complaints if not q['relevant_sections']][:cfg['cfpb_out_of_scope']]
    cases = ([('documents', q['query_id'], q['question'], settings()['benchmark']['as_of'], q) for q in documents]
             + [('cfpb_in_scope', q['question_id'], q['question'], q['incident_date'], q) for q in in_scope]
             + [('cfpb_out_of_scope', q['question_id'], q['question'], q['incident_date'], q) for q in out_scope])
    rows = []
    for group, identifier, question, as_of, source in cases:
        result = rag.ask(question, as_of=as_of, **options)
        row = {'group': group, 'id': identifier, 'search_query': result.search_query,
               'rewrite_error': result.rewrite_error, 'generation_error': result.generation_error,
               'retrieved': [d.metadata['reference'] for d in result.documents],
               'passages_kept_on_error': bool(result.documents) if result.generation_error else None,
               'warnings': result.warnings, 'timings_ms': result.timings_ms}
        if result.answer:
            row |= {'answer': result.answer.answer, 'abstained': result.answer.abstained,
                    'citations': result.citations,
                    'verified_citations': sum(c['verified'] for c in result.citations)}
            if group == 'documents':
                expected = set(re.findall(r'\d+', source['answer']))
                row['reference_numbers_in_answer'] = (expected <= set(re.findall(r'\d+', result.answer.answer))
                                                      if expected else None)
        rows.append(row)
        log(f"{group:18s} {identifier}: " + ('ERREUR ' + result.generation_error if result.generation_error else
                                            f"abstention={row['abstained']} citations vérifiées={row['verified_citations']}/{len(row['citations'])}"))
        time.sleep(settings()['benchmark'].get('groq_pause_seconds', 1))

    def rate(group, predicate, among=None):
        selected = [r for r in rows if r['group'] == group and (among is None or among(r))]
        return (sum(bool(predicate(r)) for r in selected) / len(selected)) if selected else None

    answered = lambda r: 'answer' in r
    citations = [c for r in rows for c in r.get('citations', [])]
    summary = {
        'total': len(rows), 'generation_failures': sum(bool(r['generation_error']) for r in rows),
        'rewrite_failures': sum(bool(r['rewrite_error']) for r in rows),
        'passages_kept_on_generation_error': all(r['passages_kept_on_error'] for r in rows if r['generation_error']),
        'citation_verified_rate': (sum(c['verified'] for c in citations) / len(citations)) if citations else None,
        'groups': {}}
    for group in ('documents', 'cfpb_in_scope', 'cfpb_out_of_scope'):
        summary['groups'][group] = {
            'count': sum(r['group'] == group for r in rows),
            'failures': sum(r['group'] == group and bool(r['generation_error']) for r in rows),
            'abstention_rate': rate(group, lambda r: r.get('abstained')),
            'answered_with_verified_citation': rate(group, lambda r: not r.get('abstained') and r.get('verified_citations')),
        }
    summary['groups']['documents']['reference_numbers_in_answer'] = rate(
        'documents', lambda r: r.get('reference_numbers_in_answer'),
        among=lambda r: r.get('reference_numbers_in_answer') is not None)
    report = {'created_at': now(), 'model': groq_model_name(), 'collection': rag.collection, 'options': options,
              'summary': summary, 'rows': rows,
              'notes': ['Taux d’abstention et de réponses citées calculés sur toutes les questions du groupe, '
                        'échecs de génération inclus au dénominateur.',
                        'Une citation vérifiée prouve seulement que les mots cités figurent dans le passage.',
                        '« reference_numbers_in_answer » est un indicateur lexical (nombres de la réponse de '
                        'référence présents), pas un jugement de justesse.']}
    write_json(REPORTS / 'generation.json', report)
    return report
