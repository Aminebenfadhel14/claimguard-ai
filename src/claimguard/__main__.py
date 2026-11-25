"""Command line: python -m claimguard <command>

  import-cfpb [--build-only]   official sources -> data/cfpb (raw eCFR XML, annotated complaints)
  ingest [--chunk-size N --chunk-overlap M] [--rebuild] [--all]   index into Qdrant
  ask "question" [--as-of YYYY-MM-DD] [--mode hybrid] [--rerank] [--no-rewrite] [--no-generate]
  questions                    generate the documentary benchmark (lab 05, script 01)
  qrels [--all]                build chunk-level qrels (lab 05, script 02)
  benchmark --suite documents|cfpb --split development|test [--rewrite] [--n-candidates N] [--chunk-size N ...]
  develop                      development grid (chunking x candidates x rewrite, six strategies) + selection
  final                        test runs: course reference configuration and the selected configuration
  generation                   answer generation and abstention on test questions (separate from retrieval)
  report                       reports/v3/RESULTS.md from the measured reports
  serve [--port 8000]          API + web interface
"""
import argparse
import sys
from datetime import date

from claimguard.config import ROOT, app_collection, collection_name, settings


def chunkings(args):
    if getattr(args, 'all', False):
        return settings()['chunking']['development_candidates']
    reference = settings()['chunking']['reference']
    return [{'chunk_size': args.chunk_size or reference['chunk_size'],
             'chunk_overlap': reference['chunk_overlap'] if args.chunk_overlap is None else args.chunk_overlap}]


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m claimguard', description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('import-cfpb')
    p.add_argument('--build-only', action='store_true')
    for name in ('ingest', 'qrels', 'benchmark'):
        p = sub.add_parser(name)
        p.add_argument('--chunk-size', type=int)
        p.add_argument('--chunk-overlap', type=int)
        if name != 'benchmark':
            p.add_argument('--all', action='store_true', help='all development chunking candidates')
        if name == 'ingest':
            p.add_argument('--rebuild', action='store_true')
        if name == 'benchmark':
            p.add_argument('--suite', choices=['documents', 'cfpb'], required=True)
            p.add_argument('--split', choices=['development', 'test'], required=True)
            p.add_argument('--rewrite', action='store_true')
            p.add_argument('--n-candidates', type=int)
    p = sub.add_parser('ask')
    p.add_argument('question')
    p.add_argument('--as-of', default=date.today().isoformat())
    p.add_argument('--mode', choices=['dense', 'sparse', 'hybrid'])
    p.add_argument('--rerank', action='store_true', default=None)
    p.add_argument('--no-rewrite', action='store_true')
    p.add_argument('--no-generate', action='store_true')
    for name in ('questions', 'final', 'generation', 'report'):
        sub.add_parser(name)
    p = sub.add_parser('develop')
    p.add_argument('--force', action='store_true', help='recompute runs already present in reports/v3/runs')
    p = sub.add_parser('serve')
    p.add_argument('--port', type=int, default=8000)
    args = parser.parse_args(argv)

    if args.command == 'import-cfpb':
        from claimguard import cfpb
        from claimguard.config import cfpb_settings
        config = cfpb_settings()
        if not args.build_only:
            cfpb.download(ROOT, config)
        print(cfpb.build(ROOT, config))
        return
    if args.command == 'report':
        from claimguard.report import write_results
        print('Écrit :', write_results())
        return
    if args.command == 'serve':
        import uvicorn
        print(f'ClaimGuard AI : http://127.0.0.1:{args.port}')
        uvicorn.run('claimguard.api:app', host='127.0.0.1', port=args.port)
        return

    from claimguard.rag import RAG, Models, groq_llm
    if args.command == 'ingest':
        from claimguard.ingest import ingest
        models_ = Models(reranker=False)
        for c in chunkings(args):
            ingest(models_, c['chunk_size'], c['chunk_overlap'], rebuild=args.rebuild)
        return
    if args.command == 'questions':
        from claimguard.evaluation import generate_questions
        from claimguard.ingest import load_documents
        generate_questions(groq_llm(), load_documents())
        return
    if args.command == 'qrels':
        from claimguard.config import BENCHMARK, read_jsonl
        from claimguard.evaluation import build_qrels
        questions = read_jsonl(BENCHMARK / 'questions.jsonl')
        for c in chunkings(args):
            _, report = build_qrels(collection_name(c['chunk_size'], c['chunk_overlap']), questions)
            print(report['collection'], 'sans correspondance :', report['no_match'],
                  'correspondance générique seulement :', report['only_generic_match'])
        return

    models_ = Models(reranker=True)
    if args.command == 'ask':
        app = settings()['app']
        rag = RAG(app_collection(), models_)
        result = rag.ask(args.question, mode=args.mode or app['mode'],
                         rerank=app['rerank'] if args.rerank is None else args.rerank,
                         rewrite=app['rewrite'] and not args.no_rewrite, k=app['k'],
                         n_candidates=app['n_candidates'], as_of=args.as_of, generate=not args.no_generate)
        print('Requête de recherche :', result.search_query)
        for i, d in enumerate(result.documents, 1):
            m = d.metadata
            print(f"\n[{i}] {m['citation']} — {m['paragraph_title']} (version {m['version']}, {m['version_date']}) "
                  f"id={d.metadata['_id']}\n{d.page_content[:400]}")
        if result.answer:
            print('\nRéponse :', result.answer.answer)
            print('Abstention :', result.answer.abstained)
            for c in result.citations:
                print(f"  [{c['passage']}] {'vérifiée' if c['verified'] else 'NON vérifiée'} : {c['quote'][:200]}")
        for w in result.warnings:
            print('Avertissement :', w)
        if result.generation_error:
            print('Erreur de génération :', result.generation_error)
        return

    from claimguard.evaluation import evaluate_generation, run_benchmark
    if args.command == 'benchmark':
        c = chunkings(args)[0]
        rag = RAG(collection_name(c['chunk_size'], c['chunk_overlap']), models_)
        run_benchmark(rag, args.suite, args.split, rewrite=args.rewrite, n_candidates=args.n_candidates)
        return
    if args.command == 'develop':
        from claimguard.config import REPORTS
        from claimguard.report import select
        for c in settings()['chunking']['development_candidates']:
            rag = RAG(collection_name(c['chunk_size'], c['chunk_overlap']), models_)
            for n in settings()['retrieval']['n_candidates_development']:
                for rewrite in (False, True):
                    for suite in ('documents', 'cfpb'):
                        tag = f"{suite}_development_{rag.collection}_n{n}_{'rewrite' if rewrite else 'original'}"
                        if (REPORTS / 'runs' / f'{tag}.json').exists() and not args.force:
                            print(f'Déjà mesuré (--force pour recalculer) : {tag}')
                            continue
                        print(f"\n== {suite} development {rag.collection} n={n} rewrite={rewrite}")
                        run_benchmark(rag, suite, 'development', rewrite=rewrite, n_candidates=n)
        print(select()['chosen'])
        return
    if args.command == 'final':
        from claimguard.config import REPORTS
        from claimguard.report import load
        selection = load(REPORTS / 'selection.json')
        if selection is None:
            sys.exit('Sélection absente : lancez « python -m claimguard develop ».')
        reference = settings()['chunking']['reference']
        configs = [(collection_name(reference['chunk_size'], reference['chunk_overlap']),
                    settings()['retrieval']['n_candidates'], False)]
        chosen = selection['chosen']
        if (chosen['collection'], chosen['n_candidates'], chosen['rewrite']) not in configs:
            configs.append((chosen['collection'], chosen['n_candidates'], chosen['rewrite']))
        for collection, n, rewrite in configs:
            rag = RAG(collection, models_)
            for suite in ('documents', 'cfpb'):
                print(f'\n== {suite} test {collection} n={n} rewrite={rewrite}')
                run_benchmark(rag, suite, 'test', rewrite=rewrite, n_candidates=n)
        return
    if args.command == 'generation':
        app = settings()['app']
        rag = RAG(app_collection(), models_)
        options = {'mode': app['mode'], 'rerank': app['rerank'], 'rewrite': app['rewrite'], 'k': app['k'],
                   'n_candidates': app['n_candidates']}
        print(evaluate_generation(rag, options)['summary'])


if __name__ == '__main__':
    main()
