"""Render measured local release evidence without changing historical reports."""
import json
from pathlib import Path
from claimguard.settings import ROOT
from claimguard.corpora import paths


def render():
    lines=['# ClaimGuard AI — validation locale', '',
           'Architecture conservée : SQLite → Qdrant dense/BM25 → RRF → CrossEncoder → Groq facultatif.', '',
           'Les chiffres suivants sont mesurés ; les objectifs ne sont pas des résultats garantis. Les annotations de pertinence restent provisoires et nécessitent une revue indépendante.', '']
    for corpus in ('drip_r','novaretail'):
        reports=paths(ROOT,corpus)['reports']
        latest=reports/'latest.json'
        if not latest.exists(): continue
        result=json.loads(latest.read_text(encoding='utf-8'))
        baseline=json.loads((reports/'baselines/v1/retrieval_results.json').read_text(encoding='utf-8'))
        lines.extend([f'## {corpus}', '', f"Profil : `{result['profile']['name']}` ; version : `{result['profile']['pipeline_version']}`.",
                      f"Jeu de test SHA-256 : `{result['dataset_sha256']}`.", '',
                      '| Expérience | Recall@5 avant | Recall@5 après | MRR@10 avant | MRR@10 après | p95 après (ms) |',
                      '|---|---:|---:|---:|---:|---:|'])
        for label,value in result['summary'].items():
            old=baseline['summary'].get(label,{}).get('metrics',{})
            before_r=f"{old['recall@5']:.4f}" if 'recall@5' in old else '—'
            before_m=f"{old['mrr@10']:.4f}" if 'mrr@10' in old else '—'
            m=value['metrics']
            lines.append(f"| {label} | {before_r} | {m['recall@5']:.4f} | {before_m} | {m['mrr@10']:.4f} | {value['latency_p95_ms']:.0f} |")
        e4=result['summary']['E4']
        goals={'Recall@5 ≥ 0,90':e4['metrics']['recall@5']>=.9,
               'MRR@10 ≥ 0,85':e4['metrics']['mrr@10']>=.85,'p95 ≤ 3 s':e4['latency_p95_ms']<=3000}
        lines+=['', 'Objectifs E4 : '+ '; '.join(k+' : '+('atteint' if v else 'non atteint') for k,v in goals.items())+'.', '']
    training=ROOT/'reports/drip_r/latest_training.json'
    if training.exists():
        t=json.loads(training.read_text(encoding='utf-8'))
        lines+=['## Entraînement et sélection', '',
                f"Entraînement CPU réel : {t['epochs']} époques ; checkpoint retenu : époque {t['best_epoch']} ; éligible en production : {t['production_eligible']}. Aucun checkpoint initial écrasé.", '',
                'Les profils sont choisis sur développement FR/EN, avec les variantes bilingues regroupées et sans scénarios DRIP-R originaux. Le test historique, déjà observé pendant le diagnostic, sert de régression ; il ne constitue pas un nouveau test aveugle.', '']
    lines+=['## Validation technique et limites', '',
            '- Les ressources des modèles sont préparées explicitement et vérifiées par SHA-256. La recherche et le chargement ont été testés sans réseau externe.',
            '- Les quatre modes, les deux corpus, les filtres temporels et d’accès, la requête de la capture, la diversité des sections et la conservation des preuves après une panne Groq sont couverts par les tests.',
            '- Les outils MCP ont été appelés via le SDK et le transport stdio ; les contrôles API incluent authentification, disponibilité et recherche réelle.',
            '- La latence exclut le chargement initial et le LLM. Elle dépend de la machine Windows et de sa charge ; elle n’est pas un engagement de service.',
            '- Groq réel : non évalué. Le contrôle automatique a refusé le test externe en attente d’autorisation explicite de transmettre les questions synthétiques et leurs extraits de politiques.',
            '- La validation exacte des citations est testée ; la fidélité sémantique et la couverture de chaque affirmation nécessitent une revue humaine.',
            '- Le contrôle visuel interactif a été interrompu par l’activité dans le navigateur ; le parcours Streamlit est vérifié par AppTest. Docker n’a pas été exécuté.', '',
            'Voir [le guide local](../docs/LOCAL_RUN.md), `reports/local_acceptance.json`, `reports/pytest-local.xml`, les dossiers `runs`, `profile_selection.json` et `latest_training.json`.', '']
    (ROOT/'reports/LOCAL_RESULTS.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__=='__main__': render()
