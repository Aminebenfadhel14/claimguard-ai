import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
home=Path('.')
r=json.loads((home/'reports/retrieval_results.json').read_text(encoding='utf-8'))
s=r['summary']; labels=list(s)
fig,ax=plt.subplots(figsize=(9,4.8),layout='constrained')
x=np.arange(len(labels));w=.24
for n,(key,label,color) in enumerate([('recall@1','Recall@1','#4361ee'),('recall@5','Recall@5','#0f9d92'),('mrr@10','MRR@10','#f1a340')]):
    values=[s[k]['metrics'][key] for k in labels]
    bars=ax.bar(x+(n-1)*w,values,width=w,label=label,color=color)
    ax.bar_label(bars,labels=[f'{v:.3f}' for v in values],fontsize=8,padding=3)
ax.set(xticks=x,xticklabels=labels,ylim=(0,1.12),ylabel='Score',title='ClaimGuard AI — 68 questions avec réponse')
ax.spines[['top','right']].set_visible(False);ax.legend(loc='lower right');ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
fig.savefig('reports/retrieval_comparison.png',dpi=180);fig.savefig('reports/retrieval_comparison.svg');plt.close(fig)
training=json.loads(Path('reports/training_run.json').read_text(encoding='utf-8'))
fig,ax=plt.subplots(figsize=(7,3.7),layout='constrained')
ax.plot([v['epoch'] for v in training['logs']],[v['validation_loss'] for v in training['logs']],marker='o',label='Validation')
ax.plot([v['epoch'] for v in training['logs'][1:]],[v['train_loss'] for v in training['logs'][1:]],marker='s',label='Entraînement')
ax.set(xlabel='Époque',ylabel='Perte triplet',title='Fine-tuning réel — CPU, seed 42');ax.legend();ax.grid(alpha=.2)
fig.savefig('reports/training_curve.png',dpi=180);plt.close(fig)
lines=['# Résultats expérimentaux — ClaimGuard AI','',
'Exécution du 2 novembre 2026. Corpus fictif NovaRetail : 11 versions documentaires, 44 chunks dont les préambules. Test : 76 questions, dont 68 avec réponse et 8 sans réponse. Annotation par l’auteur, contrôle automatique des références, sans revue humaine indépendante.','',
'| Expérience | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR@10 | Latence moyenne ms |',
'|---|---:|---:|---:|---:|---:|---:|']
for k,v in s.items():
    m=v['metrics'];lines.append('| '+k+' | '+' | '.join(f'{m[t]:.4f}' for t in ['recall@1','recall@3','recall@5','recall@10','mrr@10'])+f" | {v['latency_mean_ms']:.2f} |")
lines+=['','E1 : dense ; E2 : BM25 ; E3 : dense + BM25 + RRF ; E4 : hybride + CrossEncoder ; E5 : embeddings fine-tunés + hybride + même CrossEncoder.',
'','![Comparaison](retrieval_comparison.png)','',
'## Lecture des résultats',
'- E3 atteint Recall@5 = 1,0000. Le reranker améliore le premier résultat et le MRR, mais réduit légèrement Recall@5 à 0,9926. Il n’est donc pas meilleur sur tous les critères.',
'- E4 et E5 produisent les mêmes métriques agrégées : aucune amélioration de la chaîne complète n’est démontrée par ce fine-tuning.',
'- Le petit corpus et les candidats top-20 laissent une grande partie du classement final au CrossEncoder. Un résultat élevé sur ce corpus ne constitue pas une validation sur des plaintes réelles.',
'- Les latences sont des mesures locales CPU avec modèles déjà chargés ; elles excluent le chargement et les appels LLM, et ne constituent pas un test de charge. Les différences E4/E5 ne prouvent pas un gain de vitesse.',
'','## Fine-tuning',f"Base : {training['base_model']}. Triplet cosine margin 0,25 ; 3 époques ; batch 8 ; lr 2e-5 ; weight decay 0,01 ; seed 42 ; CPU. 60 exemples train, 30 validation. Checkpoint retenu : époque {training['best_epoch']}, choisi sur validation uniquement. Durée mesurée : {training['training_seconds']:.2f} s.",
'','![Pertes](training_curve.png)']
ab=json.loads(Path('reports/dense_finetuning_comparison.json').read_text(encoding='utf-8'))
lines+=['','## Comparaison du modèle dense seul','| Modèle | Recall@1 | Recall@5 | MRR@10 |','|---|---:|---:|---:|']
for key,name in [('baseline','Pré-entraîné'),('fine_tuned','Fine-tuné')]:
    m=ab[key];lines.append(f"| {name} | {m['recall@1']:.4f} | {m['recall@5']:.4f} | {m['mrr@10']:.4f} |")
lines+=['','Cette comparaison isole les embeddings. Aucun hyperparamètre n’a été ajusté après observation du test.',
'','## Échecs et limites','Q021 : une contestation de scan « livré » remonte après la règle de retard. Q033 : une demande en français remonte après l’accusé de réception. Q040 : le contrôle d’accès de l’enquête remonte après la règle de conduite. Q061 : le cas multithématique échange + comportement classe d’abord une règle de rupture de stock. Les classements complets figurent dans retrieval_results.json.',
'','Les 8 questions sans réponse ont été soumises aux retrieveurs, mais aucune précision d’abstention n’est annoncée : elle exige la génération LLM réelle. Faithfulness et implication logique des citations ne sont pas mesurées. Le test ne couvre pas suffisamment le français, les très longs documents, les scans, les politiques réelles contradictoires ni les attaques adversariales.',
'','## Preuves et reproductibilité','- `retrieval_results.json` : scores et classements par question, SHA du test, temps.',
'- `dense_finetuning_comparison.json` : ablation dense seule.',
'- `training_run.json` : hyperparamètres, pertes, SHA des trois splits.',
'- `checkpoint_manifest.json` : fichiers du checkpoint et SHA-256.',
'- `pytest_results.xml`, `tests_final.txt` : 16 tests réussis, dont modèles réels et Qdrant local.',
'- `mcp_demo.json` : trois outils découverts et trois appels client–serveur réussis.',
'- `streamlit_interaction.txt` : formulaire de recherche et cinq cartes sources vérifiés avec Streamlit AppTest.',
'- `live_rag_check.txt` : blocage explicite dû à l’absence de GROQ_API_KEY.',
'- `environment-linux.lock.txt` : environnement complet observé ; Windows et Docker non exécutés.']
Path('reports/RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
