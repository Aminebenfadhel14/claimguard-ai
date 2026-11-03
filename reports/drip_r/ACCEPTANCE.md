# État de livraison — adaptation DRIP-R

Les preuves sont les fichiers produits par l'exécution, et non une checklist déclarative seule.

| Exigence | État | Preuve / limite |
|---|---|---|
| Télécharger DRIP-R dans le projet | Réalisé | `data/external/drip_r/`, empreintes vérifiées |
| Audit du dataset | Réalisé | `audit.json` : 400 scénarios, 40 situations, 10 profils, 2 politiques |
| Parsing et métadonnées | Testé | Textes exacts, 30 sections locales, lignes d'origine, dates inconnues explicites |
| PDF/TXT/Markdown du socle | Tests conservés | Les tests PDF d'origine passent ; DRIP-R est livré en JSONL/TXT |
| Isolation NovaRetail / DRIP-R | Testé | Catalogues et sorties distincts, aucune règle NovaRetail dans les hits DRIP-R |
| Dense, BM25, RRF, CrossEncoder | Exécuté | E1–E4 et tests avec les vrais modèles |
| Questions annotées | 50 + 8 | Annotations de projet provisoires ; revue indépendante encore nécessaire |
| Recall@1/3/5/10 et MRR@10 | Calculés | `retrieval_results.json`, moyennes par scénario et par situation |
| Fine-tuning | Exécuté | 3 époques, 60 exemples train / 30 validation, checkpoint et logs |
| Comparaison baseline / fine-tuned | Réalisée | E4/E5 et dense seul ; baisse observée, aucun gain revendiqué |
| Protection du benchmark | Testée | Aucun scénario original dans l'entraînement ; champs privés exclus du RAG |
| Serveur MCP et client | Testés | Deux outils appelés avec succès dans `mcp_demo.json` |
| Streamlit | Testé | Recherche réelle et changement de corpus sans sources résiduelles |
| Réécriture et génération Groq | Code intégré, non validé en réel | Absence de `GROQ_API_KEY` dans `live_rag_check.txt` |
| Abstention et faithfulness | Non mesurées | Aucun score fabriqué |
| Comparaison historique DRIP-R | Non applicable aux données fournies | Un seul instantané sans dates de validité |
| Classification / conformité Level 2 complète | En attente | Le retrieval ne remplace pas une décision métier |
| Traitement des 400 scénarios | Exécuté | 2 000 références vérifiées ; preuves uniquement, aucun verdict |
| Suite de tests | 29 réussis | `pytest_results.xml` et `tests_final.txt` |
| Exécution Windows / Docker | Non effectuée | Commandes fournies ; validation faite sur Linux/Python 3.12 |

Les scores DRIP-R ne sont pas comparables directement à ceux de NovaRetail : corpus, questions et annotations différents. Les 400 scénarios ne sont pas 400 problèmes indépendants. Les preuves de recherche pour l'ensemble du dataset sont produites par `scripts/drip_batch.py`, sans verdict de conformité.
