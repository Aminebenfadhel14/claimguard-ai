"""Local academic workbench. Business decisions remain outside this Level 1 interface."""
import json
from datetime import date
from pathlib import Path
import pandas as pd
import streamlit as st
from claimguard.models import SearchRequest
from claimguard.runtime import build

HOME=Path(__file__).resolve().parents[1]
st.set_page_config(page_title='ClaimGuard AI',page_icon='🛡️',layout='wide')
st.markdown('### ClaimGuard AI')
st.caption('NovaRetail · Atelier académique · Politiques fictives')
st.info('Recherche documentaire et évaluation. Les conclusions de conformité et décisions humaines du Level 2 ne sont pas encore activées.')
@st.cache_resource
def services():return build(HOME,with_reranker=True)

def table(hits):
    return pd.DataFrame([{'Rang':i,'Référence':h.chunk.reference(),'Page':h.chunk.page,'Score':h.score,'Étape':h.stage} for i,h in enumerate(hits,1)])

search,policies,explain,evaluation=st.tabs(['Recherche','Politiques','Explication RAG','Évaluation'])
with search:
    st.subheader('Rechercher les règles applicables')
    with st.form('search_form'):
        query=st.text_area('Question ou déclaration client','My defective phone was refused for exchange four days after purchase.')
        as_of=st.date_input('Date de l’incident',date(2026,11,2))
        mode=st.selectbox('Méthode',['rerank','hybrid','dense','sparse'])
        submitted=st.form_submit_button('Rechercher',type='primary')
    if submitted:
        try:
            with st.spinner('Recherche des passages…'):
                _,engine=services()
                st.session_state.trace=engine.retrieve(SearchRequest(query=query,incident_date=as_of,mode=mode))
        except Exception as e:st.error('Recherche indisponible : '+type(e).__name__)
    if 'trace' in st.session_state:
        for h in st.session_state.trace['final']:
            with st.expander(f'{h.chunk.reference()} · page {h.chunk.page}',expanded=True):
                st.text(h.chunk.text)
                st.caption(f'Score {h.score:.4f} · {h.stage} · SHA-256 {h.chunk.file_hash[:12]}…')
        st.caption('Passages récupérés. Ceci ne constitue pas une réponse générée ni une décision de conformité.')
with policies:
    st.subheader('Documents sources')
    files=sorted((HOME/'data/policies').glob('*.md'))
    chosen=st.selectbox('Version documentaire',files,format_func=lambda p:p.name)
    st.text(chosen.read_text(encoding='utf-8'))
    st.download_button('Télécharger cette politique',chosen.read_bytes(),file_name=chosen.name)
    st.json(json.loads(chosen.with_suffix('.md.json').read_text()))
with explain:
    st.subheader('Classements avant et après fusion')
    if 'trace' not in st.session_state:st.write('Lancez une recherche pour examiner ses étapes.')
    else:
        for name in ('dense','sparse','rrf','reranker','final'):
            st.write(name.upper())
            st.dataframe(table(st.session_state.trace[name]),hide_index=True,use_container_width=True)
with evaluation:
    p=HOME/'reports/retrieval_results.json'
    if p.exists():
        report=json.loads(p.read_text());summaries=report['summary']
        frame=pd.DataFrame([{ 'Expérience':k,**v['metrics'],'Latence moyenne (ms)':v['latency_mean_ms']} for k,v in summaries.items()])
        st.dataframe(frame,hide_index=True,use_container_width=True)
        st.bar_chart(frame.set_index('Expérience')[['recall@1','recall@5','mrr@10']])
        st.caption('Benchmark synthétique : 68 questions avec réponse, 8 sans réponse. Abstention LLM non mesurée. Voir rapports et limites dans le README.')
    else:st.write('Exécutez scripts/evaluate.py pour produire des résultats réels.')
