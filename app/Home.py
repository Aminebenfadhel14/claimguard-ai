"""ClaimGuard AI — evidence retrieval, offline first, optional cited drafts."""
import json
import os
from datetime import date
from pathlib import Path
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from pydantic import ValidationError
from claimguard.models import SearchRequest
from claimguard.runtime import build
from claimguard.corpora import paths
from claimguard.datasets.drip_r import read_jsonl
from claimguard.prompts.rag import groq_model, generate, rewrite
from claimguard.settings import load_profile, file_hash
from claimguard.diagnostics import readiness, ModelUnavailable, record_error

HOME = Path(__file__).resolve().parents[1]
load_dotenv(HOME / '.env')
st.set_page_config(page_title='ClaimGuard AI', page_icon=':material/policy:', layout='wide')
st.title('ClaimGuard AI')
st.caption('Assistant de recherche documentaire · Réclamations et politiques · FR / EN')
corpus = st.sidebar.selectbox('Corpus', ['drip_r', 'novaretail'],
    format_func=lambda x: 'DRIP-R · Retours produits' if x == 'drip_r' else 'NovaRetail · Politiques fictives')
profiles = json.loads((HOME / 'configs/retrieval.json').read_text(encoding='utf-8'))
requested_profile = os.getenv('CLAIMGUARD_PROFILE') or profiles['default']
if requested_profile not in profiles['profiles']:
    st.sidebar.warning('Profil configuré inconnu ; utilisation du profil par défaut.')
    requested_profile = profiles['default']
profile_name = st.sidebar.selectbox('Profil de recherche', list(profiles['profiles']),
    index=list(profiles['profiles']).index(requested_profile),
    format_func=lambda p: profiles['profiles'][p]['label'])
profile = load_profile(HOME, profile_name)
locations = paths(HOME, corpus)
state_key = corpus + '_' + profile['fingerprint'][:12]
trace_key = 'trace_' + state_key
status = readiness(HOME, corpus, profile)
st.sidebar.subheader('Disponibilité locale')
for component, present in status['models'].items():
    label = {'dense': 'Embeddings', 'sparse': 'BM25', 'reranker': 'Reranker'}[component]
    st.sidebar.caption(f'{label} : '+('prêt' if present else 'à préparer'))
st.sidebar.caption(f"Corpus : {status['documents']} documents")
st.sidebar.caption('Groq : ' + ('configuré' if status['groq_configured'] else 'facultatif, non configuré'))
if trace_key in st.session_state:
    st.sidebar.success('Moteur prêt · index chargé')
else:
    st.sidebar.info('Index chargé à la première recherche')
if not status['available_modes']:
    st.warning('Les modèles locaux doivent être préparés avant la première recherche.')
    st.code(f'.\\.venv\\Scripts\\python.exe scripts/prepare_models.py --profiles {profile_name}', language='powershell')
elif len(status['available_modes']) < 4:
    st.warning('Certains modèles sont absents. Modes disponibles : ' + ', '.join(status['available_modes']))
if corpus == 'drip_r':
    st.info('DRIP-R : instantané de benchmark, sans dates de validité connues. Les sources ne permettent pas de garantir un remboursement ni de décrire les politiques actuelles.')
else:
    st.info('NovaRetail : politiques fictives et versionnées. La date de l’incident détermine les versions recherchées.')


@st.cache_resource(max_entries=3)
def services(selected_corpus, selected_profile, selected_mode, fingerprint):
    return build(HOME, corpus=selected_corpus, profile=selected_profile, mode=selected_mode)


def hit_table(hits):
    return pd.DataFrame([{'Rang': i, 'Référence': h.chunk.reference(),
        'Section': h.chunk.section_title or h.chunk.section, 'Score de classement': h.score,
        'Étape': h.stage} for i, h in enumerate(hits, 1)])


search, documents, explain, evaluation = st.tabs(['Recherche', 'Documents', 'Explication RAG', 'Évaluations'])
with search:
    st.subheader('Trouver les règles pertinentes')
    default = 'My defective phone was refused for exchange four days after purchase.'
    brief = ''
    if corpus == 'drip_r':
        case_path = HOME / 'data/drip_r/agent_cases.jsonl'
        if case_path.exists():
            cases = read_jsonl(case_path)
            scenario = st.selectbox('Exemple du benchmark', cases,
                format_func=lambda r: r['scenario_id'] + ' · ' + r['task_id'])
            default, brief = scenario['complaint'], scenario['agent_brief']
            with st.expander('Contexte visible par l’agent'):
                st.write(brief)
                st.caption('Les champs privés du simulateur ne sont jamais utilisés.')
    modes = status['available_modes'] or ['rerank', 'hybrid', 'dense', 'sparse']
    preferred = 'rerank' if 'rerank' in modes else modes[-1]
    with st.form('search_' + state_key):
        query = st.text_area('Question ou réclamation en français ou en anglais', default, height=150)
        as_of = st.date_input('Date de l’incident' if corpus == 'novaretail' else 'Date technique du benchmark',
                             date(2026, 11, 2), disabled=corpus == 'drip_r')
        mode = st.selectbox('Méthode', modes, index=modes.index(preferred),
            format_func=lambda m: {'dense': 'Sémantique · Dense', 'sparse': 'Mots-clés · BM25',
                'hybrid': 'Hybride · Dense + BM25 + RRF', 'rerank': 'Hybride + reranking'}[m])
        use_llm = st.checkbox('Rédiger un brouillon sourcé avec Groq', disabled=not status['groq_configured'])
        submitted = st.form_submit_button('Rechercher', type='primary', disabled=not status['available_modes'])
    if submitted:
        st.session_state.pop(trace_key, None)
        st.session_state.pop('answer_' + state_key, None)
        st.session_state['warnings_' + state_key] = []
        request_text = query + ('\nAgent brief: ' + brief if corpus == 'drip_r' and query == default else '')
        try:
            request = SearchRequest(query=request_text, incident_date=as_of, mode=mode)
            with st.spinner('Chargement local et recherche des passages…'):
                _, engine = services(corpus, profile_name, mode, profile['fingerprint'])
                llm = None
                if use_llm:
                    try:
                        llm = groq_model()
                        rewritten = rewrite(request_text, llm)
                        request = SearchRequest(query=rewritten, incident_date=as_of, mode=mode)
                    except Exception:
                        error_id = record_error(HOME, 'rewrite')
                        st.session_state['warnings_' + state_key].append(f'Réécriture indisponible ; recherche du texte original. Référence : {error_id}')
                trace = engine.retrieve(request)
                st.session_state[trace_key] = trace
            if use_llm and llm:
                try:
                    with st.spinner('Rédaction du brouillon avec citations…'):
                        prefix = 'Use only this undated benchmark snapshot. ' if corpus == 'drip_r' else ''
                        st.session_state['answer_' + state_key] = generate(prefix + request_text, trace['final'], llm)
                except Exception:
                    error_id = record_error(HOME, 'generation')
                    st.session_state['warnings_' + state_key].append(f'Brouillon indisponible. Les passages retrouvés restent consultables. Référence : {error_id}')
            st.rerun()
        except ModelUnavailable as exc:
            record_error(HOME, 'model_loading')
            st.error(str(exc))
        except ValidationError:
            st.error('La question doit contenir entre 3 et 6 000 caractères. Vérifiez aussi les paramètres de recherche.')
        except Exception:
            error_id = record_error(HOME, 'retrieval')
            st.error(f'La recherche n’a pas abouti. Vérifiez le diagnostic local et les journaux var/logs/errors.log. Référence : {error_id}')
    if trace_key in st.session_state:
        for warning in st.session_state.get('warnings_' + state_key, []): st.warning(warning)
        trace = st.session_state[trace_key]
        st.caption(f"{len(trace['final'])} sections distinctes · {trace['diagnostics']['latency_ms'] / 1000:.2f} s · profil {profile_name}")
        answer = st.session_state.get('answer_' + state_key)
        if answer:
            st.subheader('Brouillon à vérifier')
            st.write(answer.answer)
            if answer.missing_information: st.write('Informations manquantes : ' + '; '.join(answer.missing_information))
            with st.expander('Citations du brouillon'): st.json(answer.model_dump())
        if not trace['final']: st.warning('Aucun passage ne correspond aux filtres de recherche.')
        for i, hit in enumerate(trace['final'], 1):
            chunk = hit.chunk
            with st.container(border=True):
                st.markdown(f'**{i}. {chunk.section_title or chunk.metadata.title}**')
                st.caption(chunk.reference() + ' · ' + chunk.source_file + ' · version ' + chunk.metadata.version)
                st.text(chunk.text)
                where = f'lignes {chunk.source_line_start}–{chunk.source_line_end} (section source)' if chunk.source_line_start else f'page {chunk.page}'
                st.caption(f'{where} · score {hit.score:.4f} · {hit.stage} · SHA-256 {chunk.file_hash[:12]}')
        st.caption('Les scores servent au classement et ne sont pas des probabilités. Les faits et toute décision métier doivent être validés par un humain.')

with documents:
    st.subheader('Documents sources')
    files = sorted(p for p in locations['policies'].glob('*') if p.suffix in {'.md', '.txt', '.pdf'})
    if files:
        chosen = st.selectbox('Document et version', files, format_func=lambda p: p.name)
        if chosen.suffix != '.pdf': st.text(chosen.read_text(encoding='utf-8'))
        st.download_button('Télécharger la source', chosen.read_bytes(), file_name=chosen.name)
        with st.expander('Provenance et métadonnées'):
            st.json(json.loads(chosen.with_suffix(chosen.suffix + '.json').read_text(encoding='utf-8')))
    else: st.warning('Aucun document source disponible.')

with explain:
    st.subheader('Comprendre le classement')
    st.write('Question → embeddings et BM25 → fusion RRF → CrossEncoder → sections distinctes → brouillon facultatif.')
    if trace_key not in st.session_state:
        st.info('Lancez une recherche pour examiner ses étapes.')
    else:
        trace = st.session_state[trace_key]
        st.text(trace['query'])
        for stage, label in [('dense', 'Recherche sémantique'), ('sparse', 'Recherche BM25'),
                             ('rrf', 'Fusion RRF'), ('reranker', 'Reranking'), ('final', 'Résultats par section')]:
            with st.expander(label, expanded=stage == 'final'):
                st.dataframe(hit_table(trace[stage]), hide_index=True, width='stretch')
        st.json(trace['diagnostics'])

with evaluation:
    st.subheader('Qualité mesurée')
    latest = locations['reports'] / 'latest.json'
    report_path = latest if latest.exists() else locations['reports'] / 'retrieval_results.json'
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding='utf-8'))
        st.caption(f"Corpus : {corpus} · rapport : {report_path.relative_to(HOME)} · jeu : {report.get('split', 'test historique')}")
        st.caption('Annotations de pertinence rédigées pour le projet ; revue humaine indépendante requise.')
        if report.get('profile_fingerprint') != profile['fingerprint']:
            st.warning('Ce rapport correspond à une autre configuration ou à la version historique. Il ne mesure pas le profil actif.')
        current_sources = {p.name:file_hash(p) for p in locations['policies'].glob('*') if p.is_file()}
        if report.get('source_sha256') and report['source_sha256'] != current_sources:
            st.warning('Les documents ont changé depuis cette évaluation. Relancez le protocole pour mesurer le corpus courant.')
        labels = {'E1': 'Dense', 'E2': 'BM25', 'E3': 'Hybride RRF', 'E4': 'Hybride + reranking',
                  'FT_DENSE': 'Fine-tuning · Dense', 'E5': 'Fine-tuning · Hybride + reranking'}
        primary = report['summary'].get('E4')
        if primary:
            metric_columns = st.columns(3)
            metric_columns[0].metric('Recall@5 · Hybride + reranking', f"{primary['metrics']['recall@5']:.1%}")
            metric_columns[1].metric('MRR@10', f"{primary['metrics']['mrr@10']:.3f}")
            metric_columns[2].metric('Latence p95', f"{primary['latency_p95_ms']/1000:.2f} s" if primary.get('latency_p95_ms') else 'Non mesurée')
        frame = pd.DataFrame([{'Expérience': labels.get(k, k), **v['metrics'],
            'Latence moyenne (ms)': v['latency_mean_ms'], 'Latence p95 (ms)': v.get('latency_p95_ms')}
            for k, v in report['summary'].items()])
        st.dataframe(frame, hide_index=True, width='stretch')
        st.bar_chart(frame.set_index('Expérience')[['recall@5', 'mrr@10']])
        st.caption('Recall@1 mesure la part des sections attendues retrouvée au premier rang. Hit@1 mesure la présence d’une section pertinente au premier rang. Une question peut nécessiter plusieurs sections.')
        baseline = locations['reports'] / 'baselines/v1/retrieval_results.json'
        if baseline.exists() and latest.exists():
            old = json.loads(baseline.read_text(encoding='utf-8'))
            comparisons = []
            for key, value in report['summary'].items():
                if key not in old['summary']: continue
                for metric in ('recall@5', 'mrr@10'):
                    before = old['summary'][key]['metrics'][metric]
                    after = value['metrics'][metric]
                    comparisons.append({'Expérience': labels.get(key, key), 'Mesure': metric,
                                        'Avant': before, 'Après': after, 'Variation': after-before})
            with st.expander('Comparaison avec la livraison initiale'):
                st.caption('Le découpage et la sélection par section ont changé. Les annotations du test historique restent identiques.')
                st.dataframe(pd.DataFrame(comparisons), hide_index=True, width='stretch')
        with st.expander('Protocole et résultats détaillés'):
            st.json({k: v for k, v in report.items() if k != 'per_question'})
        st.info('Objectifs : Recall@5 ≥ 0,90 ; MRR@10 ≥ 0,85 ; p95 ≤ 3 s après chargement. Les résultats affichés sont les mesures réelles.')
    else: st.info('Aucune évaluation enregistrée pour ce corpus.')
    st.caption('Sans exécution Groq, la qualité des réponses et l’abstention ne sont pas évaluées. La présence de citations exactes ne garantit pas à elle seule la justesse d’une réponse.')
