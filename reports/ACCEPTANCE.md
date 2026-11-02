# État d’acceptation — 2 novembre 2026

Le projet est **partiellement réalisé**. Le moteur de retrieval et l'expérience de fine-tuning sont exécutés et évalués. Le passage complet Level 1 reste ouvert. Level 2 est réservé dans l'architecture et n'est pas présenté comme terminé.

| Exigence | État | Preuve / limite |
|---|---|---|
| Dépôt professeur analysé | Validé | 29 fichiers Python, commit fixé, inventaire SHA |
| Matrice compétences | Validé | docs/01_COURSE_MATRIX.md |
| PDF/TXT/Markdown | Validé | Tests PDF deux pages, tableau, TXT form-feed, Markdown |
| Chunking et métadonnées | Validé | Sections, pages, SHA, IDs stables ; 44 chunks du corpus |
| Mises à jour/versions | Partiel | Ajout version, doublons, conflit immuable, désactivation, dates et diff validés ; migration d'une date de fin ouverte non implémentée |
| Dense | Validé | SentenceTransformer réel, Qdrant, E1 |
| BM25 | Validé | FastEmbedSparse Qdrant/bm25 + sparse Qdrant, E2 |
| Hybride + RRF | Validé | Fusion locale unique k=60, E3, tests formule |
| CrossEncoder | Validé | Modèle exact du lab, E4 et tests réels |
| Réécriture et génération avec sources | Code prêt, non validé en service réel | Groq non configuré ; tests de validation de citations uniquement |
| Au moins 50 questions | Réalisé, revue indépendante restante | 76 annotations synthétiques contrôlées par l'auteur et tests de références |
| Recall/MRR | Validé | 68 questions avec réponse, rapports par question |
| Abstention / faithfulness | Non validé | 8 cas sans réponse disponibles ; pas de résultat LLM inventé |
| Fine-tuning réel | Validé | 3 époques CPU, 60 train/30 validation, checkpoint et logs |
| Baseline vs fine-tuned | Validé | E4/E5 identiques ; dense seul légèrement dégradé sur MRR |
| MCP officiel | Validé | Serveur SDK 1.30.0, transport stdio |
| Au moins deux outils démontrés | Validé | search_policies, get_policy_section, compare_policy_versions ; 3 appels réussis |
| Limites documentées | Validé | RESULTS.md, DATA_STRATEGY.md |
| Classification et analyse métier | Prévu Level 2 | Pas de faux résultat de conformité |
| Identification de politiques | Retrieval validé | Applicabilité métier sur faits vérifiés reste à construire |
| Conditions et recommandations | Prévu Level 2 | Règles, exceptions, provenance et décisions humaines à implémenter |
| Historique des décisions humaines | Prévu Level 2 | Catalogue documentaire auditée seulement |
| Streamlit | Partiel | Atelier académique recherche/politiques/explication/évaluation, formulaire réel testé ; 7 pages métier non réalisées |
| API et accès | Partiel | API de recherche locale, secret requis, filtres côté serveur ; pas de comptes multi-utilisateurs/RBAC métier |
| Tests | Validé pour périmètre livré | 16 tests réussis + démonstration MCP + interaction Streamlit |
| Windows / Docker | Préparé, non exécuté | PowerShell, Dockerfile, Compose fournis ; hôte de validation Linux sans Docker |
| Git | Dépôt local | Aucun dépôt GitHub distant n'est annoncé |

## Blocage observé

`GROQ_API_KEY` n'est pas configurée. `scripts/live_rag_check.py` a été exécuté et échoue explicitement avant tout appel. Ajouter la clé **localement** à `.env`, puis relancer le script. Il vérifiera les citations, mesurera l'abstention sur les cas sans réponse et enregistrera les erreurs sans les masquer dans le dénominateur.

Le Level 2 est différé conformément à l'ordre demandé : validation du Level 1 avant les fonctions métier avancées. La revue indépendante des annotations et les tests de génération restent des critères de passage.
