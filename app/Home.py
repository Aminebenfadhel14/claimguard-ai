"""Local RAG workbench; simulator-private fields never enter agent inputs."""
import json
import os
from datetime import date
from pathlib import Path
import pandas as pd
import streamlit as st
from claimguard.models import SearchRequest
from claimguard.runtime import build
from claimguard.corpora import paths
from claimguard.datasets.drip_r import read_jsonl
from claimguard.prompts.rag import groq_model, generate, rewrite

HOME=Path(__file__).resolve().parents[1]
st.set_page_config(page_title='ClaimGuard AI',page_icon='🛡️',layout='wide')
st.markdown('### ClaimGuard AI')
corpus=st.sidebar.selectbox('Corpus',['drip_r','novaretail'],
    format_func=lambda x:'DRIP-R · Retours produits' if x=='drip_r' else 'NovaRetail · Politiques fictives')
locations=paths(HOME,corpus); trace_key='trace_'+corpus
st.caption('Atelier académique · Recherche avec preuves · Validation humaine requise')
if corpus=='drip_r':
    st.info('DRIP-R : 400 scénarios synthétiques, 40 situations et 2 politiques. Instantané du benchmark : dates d’application inconnues. Les décisions de remboursement ne sont pas annotées.')
else:
    st.info('NovaRetail : corpus fictif distinct. Les règles et résultats DRIP-R ne sont pas appliqués ici.')

@st.cache_resource
def services(selected_corpus):
    return build(HOME,with_reranker=True,corpus=selected_corpus)

def table(hits):
    return pd.DataFrame([{'Rang':i,'Référence':h.chunk.reference(),
        'Localisation':f'lignes {h.chunk.source_line_start}–{h.chunk.source_line_end}' if h.chunk.source_line_start else f'page {h.chunk.page}',
        'Score':h.score,'Étape':h.stage} for i,h in enumerate(hits,1)])

search,policies,explain,evaluation=st.tabs(['Recherche','Politiques','Explication RAG','Évaluation'])
with search:
    st.subheader('Rechercher les règles applicables')
    default='My defective phone was refused for exchange four days after purchase.'; brief=''
    if corpus=='drip_r':
        cases=read_jsonl(HOME/'data/drip_r/agent_cases.jsonl')
        scenario=st.selectbox('Scénario DRIP-R',cases,format_func=lambda r:r['scenario_id']+' · '+r['task_id'])
        default=scenario['complaint']; brief=scenario['agent_brief'];st.caption(brief)
        st.caption('Seuls le message client et le résumé destiné à l’agent sont utilisés. Les informations privées du simulateur restent exclues.')
    with st.form('search_form_'+corpus):
        query=st.text_area('Question ou déclaration client',default,height=150)
        as_of=st.date_input('Date de l’incident' if corpus=='novaretail' else 'Date technique du test (aucune validité historique déduite)',date(2026,11,2),disabled=corpus=='drip_r')
        mode=st.selectbox('Méthode',['rerank','hybrid','dense','sparse'])
        use_llm=st.checkbox('Générer un brouillon avec Groq (clé requise)',value=False)
        submitted=st.form_submit_button('Rechercher',type='primary')
    if submitted:
        request_text=query+('\nAgent brief: '+brief if corpus=='drip_r' and query==default else '')
        st.session_state.pop('answer_'+corpus,None);st.session_state.pop(trace_key,None)
        try:
            with st.spinner('Recherche des passages…'):
                _,engine=services(corpus)
                llm=groq_model() if use_llm else None
                search_query=rewrite(request_text,llm) if llm else request_text
                trace=engine.retrieve(SearchRequest(query=search_query,incident_date=as_of,mode=mode))
                st.session_state[trace_key]=trace
                if llm:
                    prefix='Use only this undated benchmark snapshot; do not claim these are current Amazon policies. ' if corpus=='drip_r' else ''
                    st.session_state['answer_'+corpus]=generate(prefix+request_text,trace['final'],llm)
        except Exception as e:
            st.error('Service indisponible : '+('GROQ_API_KEY absente.' if use_llm and not os.getenv('GROQ_API_KEY') else type(e).__name__))
    if trace_key in st.session_state:
        answer=st.session_state.get('answer_'+corpus)
        if answer:
            st.write(answer.answer);st.caption('Brouillon à vérifier par un employé. Aucun envoi automatique.');st.json(answer.model_dump())
        for h in st.session_state[trace_key]['final']:
            where=f'lignes {h.chunk.source_line_start}–{h.chunk.source_line_end}' if h.chunk.source_line_start else f'page {h.chunk.page}'
            with st.expander(f'{h.chunk.reference()} · {where}',expanded=True):
                st.text(h.chunk.text);st.caption(f'Score {h.score:.4f} · {h.stage} · SHA-256 {h.chunk.file_hash[:12]}…')
        st.caption('Un passage pertinent ne prouve ni l’éligibilité du client ni une violation. Les faits restent à vérifier.')
with policies:
    st.subheader('Documents sources')
    files=sorted(p for p in locations['policies'].glob('*') if p.suffix in {'.md','.txt','.pdf'})
    if files:
        chosen=st.selectbox('Version documentaire',files,format_func=lambda p:p.name)
        if chosen.suffix!='.pdf':st.text(chosen.read_text(encoding='utf-8'))
        st.download_button('Télécharger cette politique',chosen.read_bytes(),file_name=chosen.name)
        st.json(json.loads(chosen.with_suffix(chosen.suffix+'.json').read_text(encoding='utf-8')))
    if corpus=='drip_r':
        st.caption('Numéros de sections et version 1.0 ajoutés localement pour les citations. Textes d’origine conservés à l’identique ; tableaux incomplets non complétés.')
with explain:
    st.subheader('Classements avant et après fusion')
    if trace_key not in st.session_state:st.write('Lancez une recherche pour examiner ses étapes.')
    else:
        trace=st.session_state[trace_key];st.text(trace['query'])
        for name in ('dense','sparse','rrf','reranker','final'):
            st.write(name.upper());st.dataframe(table(trace[name]),hide_index=True,width='stretch')
with evaluation:
    p=locations['reports']/'retrieval_results.json'
    if p.exists():
        report=json.loads(p.read_text(encoding='utf-8'));summaries=report['summary']
        frame=pd.DataFrame([{'Expérience':k,**v['metrics'],'Latence moyenne (ms)':v['latency_mean_ms']} for k,v in summaries.items()])
        st.dataframe(frame,hide_index=True,width='stretch');st.bar_chart(frame.set_index('Expérience')[['recall@1','recall@5','mrr@10']])
        st.caption('Scores de retrieval sur annotations de projet à faire vérifier. Ils ne mesurent pas une décision de conformité. Abstention et génération Groq non validées tant que le test réel n’a pas été exécuté.')
        if corpus=='drip_r':
            st.caption('50 scénarios / 40 situations / 10 profils. 8 cas sans réponse ajoutés par le projet. Les 400 scénarios originaux ne sont pas utilisés pour entraîner le modèle.')
            st.json({k:v.get('task_macro_metrics') for k,v in summaries.items()})
    else:st.write('Exécutez scripts/evaluate.py --corpus '+corpus+' pour produire les mesures.')
    if corpus=='drip_r':
        with st.expander('Audit et provenance du dataset'):
            st.json(json.loads((locations['reports']/'audit.json').read_text(encoding='utf-8')))
