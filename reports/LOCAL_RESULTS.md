# ClaimGuard AI — validation locale

Architecture conservée : SQLite → Qdrant dense/BM25 → RRF → CrossEncoder → Groq facultatif.

Les chiffres suivants sont mesurés ; les objectifs ne sont pas des résultats garantis. Les annotations de pertinence restent provisoires et nécessitent une revue indépendante.

## drip_r

Profil : `validated` ; version : `section-diversity-v2`.
Jeu de test SHA-256 : `04c7c70f1741ef486a3ba1650f6cfafcb657a16e98eb67b67147cb3c03b6f723`.

| Expérience | Recall@5 avant | Recall@5 après | MRR@10 avant | MRR@10 après | p95 après (ms) |
|---|---:|---:|---:|---:|---:|
| E1 | 0.6967 | 0.6967 | 0.6209 | 0.6209 | 29 |
| E2 | 0.5717 | 0.5717 | 0.5580 | 0.5600 | 3 |
| E3 | 0.7783 | 0.7783 | 0.7145 | 0.7145 | 37 |
| E4 | 0.8367 | 0.8133 | 0.7783 | 0.7847 | 1877 |
| FT_DENSE | 0.6017 | 0.5600 | 0.5832 | 0.5068 | 29 |
| E5 | 0.8167 | 0.8233 | 0.7723 | 0.7857 | 2084 |

Objectifs E4 : Recall@5 ≥ 0,90 : non atteint; MRR@10 ≥ 0,85 : non atteint; p95 ≤ 3 s : atteint.

## novaretail

Profil : `validated` ; version : `section-diversity-v2`.
Jeu de test SHA-256 : `2f56dd7b9c8a513e629d752ed14c4b3566f1b9a38800a496226c474c5382305a`.

| Expérience | Recall@5 avant | Recall@5 après | MRR@10 avant | MRR@10 après | p95 après (ms) |
|---|---:|---:|---:|---:|---:|
| E1 | 0.9853 | 0.9853 | 0.8771 | 0.8771 | 12 |
| E2 | 0.9853 | 0.9853 | 0.9289 | 0.9289 | 2 |
| E3 | 1.0000 | 1.0000 | 0.9277 | 0.9203 | 13 |
| E4 | 0.9926 | 0.9926 | 0.9706 | 0.9706 | 511 |

Objectifs E4 : Recall@5 ≥ 0,90 : atteint; MRR@10 ≥ 0,85 : atteint; p95 ≤ 3 s : atteint.

## Entraînement et sélection

Entraînement CPU réel : 3 époques ; checkpoint retenu : époque 2 ; éligible en production : False. Aucun checkpoint initial écrasé.

Les profils sont choisis sur développement FR/EN, avec les variantes bilingues regroupées et sans scénarios DRIP-R originaux. Le test historique, déjà observé pendant le diagnostic, sert de régression ; il ne constitue pas un nouveau test aveugle.

## Validation technique et limites

- Les ressources des modèles sont préparées explicitement et vérifiées par SHA-256. La recherche et le chargement ont été testés sans réseau externe.
- Les quatre modes, les deux corpus, les filtres temporels et d’accès, la requête de la capture, la diversité des sections et la conservation des preuves après une panne Groq sont couverts par les tests.
- Les outils MCP ont été appelés via le SDK et le transport stdio ; les contrôles API incluent authentification, disponibilité et recherche réelle.
- La latence exclut le chargement initial et le LLM. Elle dépend de la machine Windows et de sa charge ; elle n’est pas un engagement de service.
- Groq réel : non évalué. Le contrôle automatique a refusé le test externe en attente d’autorisation explicite de transmettre les questions synthétiques et leurs extraits de politiques.
- La validation exacte des citations est testée ; la fidélité sémantique et la couverture de chaque affirmation nécessitent une revue humaine.
- Le contrôle visuel interactif a été interrompu par l’activité dans le navigateur ; le parcours Streamlit est vérifié par AppTest. Docker n’a pas été exécuté.

Voir [le guide local](../docs/LOCAL_RUN.md), `reports/local_acceptance.json`, `reports/pytest-local.xml`, les dossiers `runs`, `profile_selection.json` et `latest_training.json`.
