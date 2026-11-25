# ClaimGuard AI

RAG sur des règlements fédéraux américains de protection du consommateur (12 CFR, textes officiels eCFR), évalué
sur des questions documentaires et sur de vraies plaintes de la CFPB. Les réponses citent leurs sources et
sont des brouillons à valider par un humain, pas un avis juridique.

Projet académique TEK-UP. Version 3 : noyau aligné sur les labs `04-rag` et `05-Evaluation/Retrieval Evaluation`
du cours [AI-Engineering-Course](https://github.com/Nadjib23/AI-Engineering-Course), révision
`fc178ae632816c42dbca8f5c01e97932f0f32502` (enregistrée dans `configs/rag.json` et dans chaque rapport).

## Chaîne unique

```
XML eCFR (data/cfpb/raw/ecfr) -> Document LangChain (un par paragraphe (a), (b)...)
  -> RecursiveCharacterTextSplitter (1000 / 100) -> HuggingFaceEmbeddings + FastEmbedSparse(Qdrant/bm25)
  -> QdrantVectorStore (Qdrant Docker, vecteurs nommés "dense" et "sparse")
  -> recherche RetrievalMode.DENSE | SPARSE | HYBRID (fusion RRF de Qdrant) -> CrossEncoder si activé
  -> contexte numéroté -> ChatPromptTemplate -> ChatGroq -> sortie JSON parsée -> citations vérifiées
```

L'application (API + interface), la CLI et les benchmarks appellent les mêmes fonctions de
[src/claimguard/rag.py](src/claimguard/rag.py).

| Fichier | Rôle |
|---|---|
| [configs/rag.json](configs/rag.json) | Tous les paramètres : modèles, découpage, k, candidats, configuration de l'application, protocole du benchmark |
| [src/claimguard/ingest.py](src/claimguard/ingest.py) | XML -> Documents -> chunks (ids stables) -> création, mise à jour ou reconstruction de la collection |
| [src/claimguard/rag.py](src/claimguard/rag.py) | Modèles chargés une fois, connexion à la collection, recherche, reranking, réécriture, génération, vérification |
| [src/claimguard/evaluation.py](src/claimguard/evaluation.py) | Questions, qrels, benchmark des six stratégies, benchmark CFPB, évaluation de la génération |
| [src/claimguard/report.py](src/claimguard/report.py) | Sélection sur le développement et `reports/v3/RESULTS.md` |
| [src/claimguard/cfpb.py](src/claimguard/cfpb.py) | Import des sources officielles (eCFR, plaintes CFPB) et annotations faibles |
| [src/claimguard/api.py](src/claimguard/api.py), [frontend/](frontend/) | Interface mince (FastAPI + React, **hors cours**) : question, réponse, sources, évaluations |
| [src/claimguard/\_\_main\_\_.py](src/claimguard/__main__.py) | CLI `python -m claimguard` |

## Correspondance avec le cours

| Étape du projet | Fichier du cours | Implémentation |
|---|---|---|
| Qdrant persistant | `04-rag/docker-compose.yml` | [docker-compose.yml](docker-compose.yml) (image épinglée) |
| Chargement, découpage 1000/100, indexation | `10-init_qdrant.py`, `10bis-…multiple_files.py` | `ingest.load_documents`, `split_documents`, `QdrantVectorStore.from_documents` |
| Empreinte de fichier, fichiers déjà indexés ignorés, `add_documents` | `14-adding_metadata.py` | `ingest.indexed_hashes`, `ingest.ingest` |
| Connexion à une collection existante, prompt, `StrOutputParser` | `11-qdrant_retreival.py`, `12-rag_inside_chain.py` | `rag.connect`, `rag.ANSWER_PROMPT`, `rag.rewrite_chain` |
| Réécriture de requête | `13-rag_query_rewriting.py` | `rag.REWRITE_PROMPT` (consignes ajoutées : négations, dates, montants) |
| Filtres de métadonnées (`Filter`, `FieldCondition`, `Range`) | `14-dealing_with_metadata.py`, `14bis-…` | `rag.in_force` (version en vigueur) ; filtres source + paragraphe des qrels |
| BM25 et mode hybride | `15-using_bm25.py`, `15bis-dense_vs_sparse_vs_hybrid.py` | `FastEmbedSparse("Qdrant/bm25")`, `RetrievalMode` |
| Reranking | `16-including_reranking.py` | `rag.retrieve(..., rerank=True)` |
| Questions avec passage vérifié | `01-generate_questions.py` | `evaluation.generate_questions` (« paragraphe » remplace « page ») |
| Qrels par suites de 5 mots | `02-buidling_qrels.py` | `evaluation.build_qrels`, `match_chunks` |
| Precision@k / Recall@k, six combinaisons | `03-benchmarking_retrieval.ipynb` | `evaluation.run_benchmark` |

Écarts volontaires, corrections d'erreurs des exemples :

- `16-including_reranking.py` appelle `.page_content` sur des chaînes ; ici le reranking renvoie les Documents (comme le notebook 03).
- Le notebook 03 ne remet pas `average_precision` / `average_recall` à zéro entre les stratégies : le rappel publié y dépasse 1. Ici les accumulateurs sont réinitialisés pour chaque combinaison, les identifiants sont dédupliqués et un test vérifie que toutes les valeurs restent dans [0, 1].
- `15bis` et `14bis` importent `Range` depuis `param` ; le bon import est `qdrant_client.models.Range`.
- Le vecteur sparse est créé avec le modificateur IDF, que Qdrant exige pour `Qdrant/bm25`. Sans lui, les scores BM25 n'utilisent pas l'IDF.
- Les qrels comparent des mots en minuscules sans ponctuation et écartent les suites de 5 mots trop générales (présentes dans plus de 5 chunks).
- Les modèles sont chargés une fois et partagés par les trois `QdrantVectorStore` ; le corpus n'est jamais réencodé à la requête.

## Démarrage (Windows, PowerShell)

Python 3.12, Docker Desktop. Node.js n'est nécessaire que pour recompiler l'interface.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
Copy-Item .env.example .env                       # renseigner GROQ_API_KEY
docker compose up -d                              # Qdrant persistant (volume qdrant_data)
.\.venv\Scripts\python.exe -m claimguard ingest   # collection claimguard_c1000_o100 (idempotent)
.\.venv\Scripts\python.exe -m claimguard ask "How many days does a consumer have to send a billing error notice?"
.\.venv\Scripts\python.exe -m claimguard serve    # http://127.0.0.1:8000 (ou start.bat)
```

Interface : `cd frontend; npm install; npm run build` (le build `frontend/dist` est livré).

## Reproduire l'évaluation

```powershell
python -m claimguard import-cfpb --build-only   # plaintes annotées depuis data/cfpb/raw (hors ligne)
python -m claimguard ingest --all               # collections des découpages candidats (1000/100, 500/50)
python -m claimguard questions                  # data/benchmark/questions.jsonl (Groq), rejets journalisés
python -m claimguard qrels --all                # data/benchmark/qrels_<collection>.json + rapport
python -m claimguard develop                    # grille de développement + reports/v3/selection.json
python -m claimguard final                      # test : configuration du cours et configuration choisie
python -m claimguard generation                 # génération et abstention, séparées de la recherche
python -m claimguard report                     # reports/v3/RESULTS.md
python -m pytest -q -m "not real"               # tests unitaires (doubles)
python -m pytest -q -m real                     # vérifications sur Qdrant et les vrais modèles
```

Un run isolé : `python -m claimguard benchmark --suite documents --split development [--rewrite] [--n-candidates 40] [--chunk-size 500 --chunk-overlap 50]`.

## Deux benchmarks distincts

- **Documentaire (méthode du cours)** : questions générées par Groq à partir des paragraphes en vigueur. Le passage justificatif est vérifié dans le paragraphe source avant acceptation, et les questions rejetées ou échouées sont listées dans `data/benchmark/questions_generation.json`. Les qrels sont les identifiants de points Qdrant. Le développement et le test sont séparés par paragraphe.
- **Plaintes CFPB réelles** : test de janvier–février 2025, développement de novembre–décembre 2024. Les labels sont **faibles** : une catégorie CFPB est associée à des paragraphes ([configs/cfpb.json](configs/cfpb.json)), sans revue juridique. Les qrels regroupent tous les chunks des paragraphes annotés. Les plaintes hors périmètre sont exclues des métriques de recherche et servent à l'évaluation de l'abstention.

Aucun champ de vérité terrain (paragraphes annotés, réponse de référence, identifiants pertinents) n'est transmis au retriever ou au prompt. Les paramètres sont choisis sur le développement selon la règle écrite dans `configs/rag.json`, puis le test est exécuté. Résultats : [reports/v3/RESULTS.md](reports/v3/RESULTS.md). Les rapports v2, dont l'unité était la section, sont conservés dans [reports/archive/v2_sections/](reports/archive/v2_sections/) ; ils ne sont pas comparables.

Données et provenance : [docs/DATA.md](docs/DATA.md).
