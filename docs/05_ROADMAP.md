# Plan de développement et critères de passage

| Phase | Travail et fichiers | Validation requise |
|---|---|---|
| 1 | Matrice, inventaire SHA, architecture, stratégies dans docs/ | Chaque technique rattachée au code réellement lu |
| 2 | Audit scripts/audit_tickets.py, corpus et sidecars, schemas | Comptages réels, absence d'identifiants dans rapports, références cohérentes |
| 3 | ingestion/, storage/, indexing/, prompts/ | PDF/TXT/MD, pages/sections, doublons, mises à jour, dense, citations ; appel LLM réel requis |
| 4 | BM25, RRF, moteur de retrieval, CrossEncoder | Scores réels, comparaison classements, filtres temporels/accès, erreur de service gérée |
| 5 | 76 questions, metrics.py, evaluate.py | Recall@1/3/5/10, MRR@10, nDCG, latences ; abstention à mesurer avec LLM |
| 6 | training/finetune.py, modèles et logs | Au moins un entraînement réel ; résultats E1–E5, checkpoint vérifiable |
| 7 | mcp/server.py et client.py | initialize/list_tools/call_tool via transport stdio, au moins deux outils |
| Passage Level 1 | Rapport d'acceptation documenté | Ne pas cocher génération ni abstention sans exécution LLM ; revue humaine des annotations |
| 8 | classification/, compliance/, recommendations/ | Schémas multi-label, règles sur preuves vérifiées, exceptions, recommandation justifiée |
| 9 | FastAPI, Streamlit, historique SQLite, revue humaine | Isolation utilisateur/cas, RBAC, décisions persistées, aucun envoi automatique |
| 10 | Rapport final et soutenance | Tests intégration, scénario historique, sans preuve, injection, E1–E5, limites |

## Étapes de reprise précises

1. Fournir localement `GROQ_API_KEY` dans `.env` et exécuter `scripts/live_rag_check.py` pour la génération, réécriture, citations et abstention.
2. Revoir les 76 annotations avec une personne indépendante ; enregistrer corrections et accord inter-annotateurs. Relancer benchmark après changement de vérité terrain.
3. Valider le passage Level 1 sur les preuves d'exécution, sans assimiler un test avec faux LLM à un appel réel.
4. Implémenter ensuite classification structurée, moteur déterministe de conditions, preuves déclarées/vérifiées, gestion de décisions humaines et interface métier. Réutiliser RetrievalEngine.

Le livrable courant privilégie un socle académique vérifiable. Le statut final de chaque exigence et les blocages figurent dans `reports/ACCEPTANCE.md`.
