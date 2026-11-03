"""Generate a report solely from persisted experimental measurements."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

root=Path(__file__).resolve().parents[1]; out=root/'reports/drip_r'
result=json.loads((out/'retrieval_results.json').read_text(encoding='utf-8')); summary=result['summary']
training=json.loads((out/'training_run.json').read_text(encoding='utf-8'))
labels=list(summary);x=np.arange(len(labels));width=.25
fig,ax=plt.subplots(figsize=(10,4.8),layout='constrained')
for i,(key,label,color) in enumerate([('recall@1','Recall@1','#3655a4'),('recall@5','Recall@5','#008f86'),('mrr@10','MRR@10','#de8f32')]):
    values=[summary[k]['metrics'][key] for k in labels]
    bars=ax.bar(x+(i-1)*width,values,width=width,label=label,color=color)
    ax.bar_label(bars,labels=[f'{v:.3f}' for v in values],fontsize=7,padding=3)
ax.set(xticks=x,xticklabels=labels,ylim=(0,1.16),ylabel='Score',title='DRIP-R · 50 scénarios, annotations de projet provisoires')
ax.legend(loc='lower right');ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
fig.savefig(out/'retrieval_comparison.png',dpi=170);plt.close(fig)
fig,ax=plt.subplots(figsize=(7,3.8),layout='constrained')
ax.plot([v['epoch'] for v in training['logs']],[v['validation_loss'] for v in training['logs']],marker='o',label='Validation')
ax.plot([v['epoch'] for v in training['logs'][1:]],[v['train_loss'] for v in training['logs'][1:]],marker='s',label='Entraînement')
ax.set(xlabel='Époque',ylabel='Perte triplet',title='Adaptation des embeddings aux politiques DRIP-R');ax.legend();ax.grid(alpha=.2)
fig.savefig(out/'training_curve.png',dpi=170);plt.close(fig)

lines=['# ClaimGuard AI — résultats DRIP-R','',
'Source : `hsuvaskakoty/DRIP-R`, révision `02f4c696df2a9170c3bea254ed2d60ea14bd4be4`. Exécution du 2 novembre 2026.',
'','## Données et protocole',
'400 scénarios synthétiques, issus de 40 situations et de 10 profils. Deux textes de politiques uniques sont conservés octet pour octet, divisés en 30 sections locales. Les numéros de sections et la version 1.0 sont ajoutés par le projet. Les dates de validité et la pagination PDF originales sont inconnues.',
'','Le test annoté contient 50 scénarios originaux (40 situations, 10 profils équilibrés) et 8 questions sans réponse créées pour le projet. Les labels de pertinence ont été rédigés par le modèle assistant avant les expériences, sans revue humaine indépendante. Ce ne sont pas les annotations humaines de DRIP-R, qui ne sont pas publiées.',
'','Les requêtes ne contiennent que le message client et le résumé destiné à l’agent. Le détail de la situation, les ambiguïtés attendues et les informations privées du simulateur sont exclus. Le champ explicite task_id est utilisé pour regrouper les variantes.',
'','## Mesures réellement calculées','',
'| Expérience | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR@10 | Latence moyenne (ms) |',
'|---|---:|---:|---:|---:|---:|---:|']
for key,v in summary.items():
    lines.append('| '+key+' | '+' | '.join(f"{v['metrics'][m]:.4f}" for m in ('recall@1','recall@3','recall@5','recall@10','mrr@10'))+f" | {v['latency_mean_ms']:.2f} |")
lines+=['','E1 : dense ; E2 : BM25 ; E3 : RRF ; E4 : hybride et CrossEncoder ; FT_DENSE : embeddings adaptés seuls ; E5 : embeddings adaptés, hybride et même CrossEncoder.',
'','![Comparaison](retrieval_comparison.png)','',
'Les moyennes par situation (40 groupes, poids égal par task_id) sont aussi enregistrées dans retrieval_results.json. La latence est locale CPU, hors chargement des modèles et hors LLM. Les références répétées à une même section ne sont comptées qu’une fois.',
'','## Fine-tuning',
f"Entraînement réel : {training['epochs']} époques, 60 questions rédigées pour le projet et 30 autres pour validation ; perte triplet cosine (marge 0,25), batch 8, lr 2e-5, seed 42, CPU. Durée : {training['training_seconds']:.2f} secondes. Checkpoint retenu : époque {training['best_epoch']}, choisi sur validation.",
'','Aucun des 400 scénarios originaux n’a servi à entraîner les embeddings. L’entraînement adapte le modèle au texte des politiques ; il ne constitue pas un entraînement supervisé aux décisions de remboursement. Les politiques sont partagées entre entraînement et test : aucune généralisation à des politiques inconnues n’est revendiquée.',
'','![Perte](training_curve.png)','',
f"Variation du MRR dense : {summary['E1']['metrics']['mrr@10']:.4f} → {summary['FT_DENSE']['metrics']['mrr@10']:.4f}.",
f"Variation du MRR de la chaîne complète : {summary['E4']['metrics']['mrr@10']:.4f} → {summary['E5']['metrics']['mrr@10']:.4f}.",
'','Ces observations portent uniquement sur ce petit benchmark annoté provisoirement. Aucun réglage n’est sélectionné sur les résultats du test.',
'','La baisse de la perte de validation ne garantit pas une amélioration du classement des réclamations. Le modèle pré-entraîné reste le défaut de l’application ; le checkpoint adapté est conservé pour la comparaison académique.',
'','## Échecs observés (E4)','']
failures=sorted([r for r in result['per_question'] if r['experiment']=='E4' and r.get('metrics',{}).get('recall@5',1)<1],key=lambda r:r['metrics']['recall@5'])
for r in failures[:8]:
    lines.append(f"- {r['question_id']} : Recall@5={r['metrics']['recall@5']:.3f}. Attendu : {', '.join(r['expected'])}. Classement : {', '.join(r['ranked_sections'][:5])}.")
if not failures:lines.append('Aucun échec de Recall@5 sur ces annotations ; cela ne valide pas la correction des annotations ni une décision métier.')
lines+=['','## Limites et éléments non validés',
'- Deux documents seulement et beaucoup de questions sur les mêmes clauses générales : benchmark peu représentatif d’une grande entreprise.',
'- Les tableaux des exceptions et de certains frais sont incomplets dans les sources. Aucun montant, catégorie ou condition manquante n’a été inventé.',
'- Les déclarations clients ne sont pas des faits vérifiés ; aucune décision de conformité ou de remboursement n’est produite par le batch.',
'- Les 8 questions sans réponse sont exclues des moyennes de retrieval. Aucune précision d’abstention, qualité sémantique des citations ou faithfulness n’est annoncée.',
'- GROQ_API_KEY absente : réécriture et génération LLM réelles non validées. Le code est disponible via scripts/live_rag_check.py --corpus drip_r.',
'- Les politiques DRIP-R sont des instantanés fournis par le benchmark, pas une preuve des règles Amazon actuelles ni une source à fusionner avec les politiques NovaRetail.',
'- Les fonctions métier avancées de Level 2 restent en attente de validation du socle LLM.',
'','## Preuves',
'audit.json, annotation_manifest.json, retrieval_results.json, training_run.json, checkpoint_manifest.json, mcp_demo.json et pytest_results.xml. Le jeu de test est identifié par son SHA-256 dans les rapports.']
batch_file=out/'batch_run.json'
if batch_file.exists():
    batch=json.loads(batch_file.read_text(encoding='utf-8'))
    lines+=['','## Traitement du dataset complet',
        f"Les {batch['scenarios_processed']} scénarios ont été soumis à la recherche hybride avec reranking. Durée CPU mesurée hors chargement : {batch['seconds']:.2f} secondes. Les cinq passages par scénario, leurs scores, références, lignes et empreintes figurent dans scenario_retrieval.jsonl.",
        '','Il s’agit de preuves récupérées, sans génération LLM, sans utilisation des informations privées et sans décision de conformité. Aucun score supervisé n’est attribué aux 350 scénarios non annotés.']
(out/'RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(out/'RESULTS.md')
