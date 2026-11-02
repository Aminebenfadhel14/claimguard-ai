# ClaimGuard AI

**Intelligent Customer Complaint Analysis & Policy Compliance Assistant — NovaRetail**

Projet académique TEK-UP, Medamine Ben Fadhel. Cette livraison contient un **socle RAG exécuté et évalué**, un fine-tuning réel, un serveur MCP officiel et un atelier Streamlit. L'application métier complète n'est pas encore terminée : voir [état d'acceptation](reports/ACCEPTANCE.md).

## Ajout DRIP-R — novembre 2026

Le dataset Hugging Face **hsuvaskakoty/DRIP-R est inclus** dans `data/external/drip_r/` :

- `scenarios.jsonl` : 400 scénarios synthétiques, issus de 40 situations et de 10 profils.
- `tasks.jsonl`, `personas.jsonl`, carte du dataset et métadonnées d'origine.
- Version source figée, SHA-256 contrôlés ; attribution dans `docs/DRIP_R.md`.

Les deux politiques sont extraites sans réécriture dans `data/drip_r/policies/`. Le corpus DRIP-R reste séparé de NovaRetail : les règles, dates et résultats ne doivent pas être mélangés. L'interface propose un sélecteur de corpus et démarre sur DRIP-R.

**Guide de cette adaptation : [docs/DRIP_R.md](docs/DRIP_R.md). Mesures : [reports/drip_r/RESULTS.md](reports/drip_r/RESULTS.md).** Les résultats NovaRetail ci-dessous restent ceux de la livraison précédente.

Après installation des dépendances, les commandes DRIP-R sont :

```powershell
.\.venv\Scripts\python.exe scripts/prepare_drip_r.py
.\.venv\Scripts\python.exe -m streamlit run app/Home.py --server.address 127.0.0.1
```

Pour reproduire les expériences depuis la racine du projet (remplacer `python` par `.\.venv\Scripts\python.exe` sous Windows) :

```bash
python scripts/prepare_drip_r.py --download
python scripts/create_drip_annotations.py
python training/finetune.py --corpus drip_r --epochs 3
python scripts/evaluate.py --corpus drip_r --trained models/drip-r-policy-embedding
python scripts/drip_batch.py
python scripts/report_drip_results.py
python -m claimguard.mcp.client --corpus drip_r
python -m pytest -q
```

Le modèle adapté est livré dans `models/drip-r-policy-embedding/`. Les 400 scénarios originaux restent réservés à l'évaluation. L'entraînement porte sur 60 questions séparées rédigées pour le projet à partir des politiques, avec 30 autres pour validation. Le test comprend 50 scénarios annotés provisoirement et 8 cas sans réponse ajoutés au projet. Les labels de pertinence nécessitent une revue indépendante et ne sont pas des labels de conformité DRIP-R.

Pour l'API/MCP, `CLAIMGUARD_CORPUS=drip_r` choisit ce corpus. Pour vérifier Groq après configuration de `.env` : `python scripts/live_rag_check.py --corpus drip_r`. La génération LLM, l'abstention et le Level 2 restent non validés ici.

## Ce qui fonctionne dans cette livraison

- PDF, TXT, Markdown ; sections, pages, nettoyage conservateur, tableaux PDF, chunks récursifs 1000/100.
- Catalogue SQLite avec empreintes SHA-256, versions immuables, filtres temporels, déduplication, désactivation et comparaison.
- Embeddings MiniLM, vrais vecteurs Qdrant, sparse BM25 FastEmbed, RRF unique k=60, CrossEncoder du cours, traces avant/après fusion.
- 10 politiques fictives, 11 versions, 76 questions annotées, 60 exemples train et 30 validation.
- E1–E5 réellement exécutées ; Recall/MRR/precision/nDCG/latence, détails par question et graphiques.
- Fine-tuning CPU 3 époques, checkpoint inclus dans l'archive sous `models/novaretail-embedding`, logs et SHA des données.
- MCP stdio : 3 outils découverts et appelés par un client réel.
- API FastAPI de recherche avec authentification locale et atelier Streamlit.
- 16 tests réussis sur Linux/Python 3.12 ; vérification supplémentaire du formulaire Streamlit avec recherche réelle.

**Limites de livraison :** Groq absent, donc génération/réécriture LLM et abstention non validées en réel. Les modules métier Level 2, les décisions humaines persistées et l'interface métier complète restent à développer après le passage Level 1. Le moteur de recherche ne tranche ni les droits du client ni la culpabilité d'un employé.

## Démarrage Windows 11 / PowerShell

Depuis le dossier `claimguard-ai`, avec Python 3.12 :

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run app/Home.py --server.address 127.0.0.1
```

Ouvrir http://localhost:8501. L'activation du venv n'est pas nécessaire avec ces commandes explicites. Les premiers lancements téléchargent les modèles Hugging Face. Les versions directes sont épinglées dans `requirements.txt`. L'environnement Linux complet observé est dans `reports/environment-linux.lock.txt` ; il sert de provenance, pas de fichier universel Windows/CUDA.

## Démarrage Linux / macOS

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
cp .env.example .env
.venv/bin/python -m pytest -q
.venv/bin/python -m streamlit run app/Home.py --server.address 127.0.0.1
```

Toutes les commandes suivantes s'exécutent à la racine du projet, dans le venv (sur Windows, remplacer `python` par `.\.venv\Scripts\python.exe`).

## Démonstration et évaluation

```bash
python scripts/demo.py --mode rerank --date 2026-11-02
python scripts/evaluate.py --trained models/novaretail-embedding
python scripts/evaluate_dense_finetuned.py
python scripts/report_results.py
python -m claimguard.mcp.client
```

Pour reproduire l'entraînement :

```bash
python training/finetune.py --epochs 3
```

Le script écrit le meilleur checkpoint de validation à `models/novaretail-embedding`. Sauvegarder une copie si vous souhaitez conserver exactement le checkpoint livré. Le corpus de test est gelé avant entraînement, ses empreintes sont enregistrées. Les exemples synthétiques partagent les politiques mais pas les requêtes/scénarios entre splits. Il ne s'agit pas d'un test sur politiques inconnues.

Pour les appels LLM, remplir uniquement `GROQ_API_KEY` dans `.env`, choisir éventuellement `GROQ_MODEL`, puis :

```bash
python scripts/live_rag_check.py
```

Ce script parcourt les 76 questions via Groq (appels réseau au fournisseur), avec réécriture, retrieval et sortie structurée. Sans clé, il échoue clairement et ne simule pas de réponse. Seules les questions fictives sont utilisées. Il ne mesure pas automatiquement l'implication logique des citations ; une revue humaine reste requise.

## Résultats observés

| Expérience | Recall@5 | MRR@10 |
|---|---:|---:|
| E1 — Dense | 0,9853 | 0,8771 |
| E2 — BM25 | 0,9853 | 0,9289 |
| E3 — Hybride RRF | 1,0000 | 0,9277 |
| E4 — Hybride + reranker | 0,9926 | 0,9706 |
| E5 — Fine-tuned + hybride + reranker | 0,9926 | 0,9706 |

Aucun gain end-to-end n'est démontré par le fine-tuning. Le modèle dense seul régresse légèrement sur MRR. Les limites, échecs et graphiques figurent dans [le rapport expérimental](reports/RESULTS.md).

## Documents et mises à jour

Chaque document dans `data/policies/` possède un sidecar `.md.json`, `.txt.json` ou `.pdf.json` contenant des métadonnées validées. Au démarrage, le catalogue ingère les nouveaux documents. Un même policy_id/version avec un contenu différent est refusé. Les intervalles des versions ne doivent pas se chevaucher. Les versions expirées restent éligibles pour leur période historique.

`Catalog.deactivate(policy_id, version, actor)` exclut la version sans supprimer ses octets ni son événement d'audit. Le moteur doit être reconstruit après cette mutation ; les index sont dérivés du catalogue. Une évolution d'une politique à intervalle ouvert nécessite une migration administrative auditée qui reste à développer : le prototype refuse le chevauchement.

## Données du professeur

Le CSV brut n'est pas inclus pour éviter de redistribuer ses données personnelles. L'audit complet agrégé est livré. Pour le reproduire, télécharger le CSV depuis le commit indiqué dans `docs/01_COURSE_MATRIX.md`, puis :

```bash
python scripts/audit_tickets.py chemin/customer_support_tickets.csv
```

Les exports expurgés sont locaux dans `var/audit/`, exclus de Git et de l'archive. Ils demandent une revue PII supplémentaire avant tout usage externe. Les résolutions du CSV ne sont jamais utilisées comme labels de conformité.

## API et Docker

Pour l'API, définir une valeur aléatoire longue pour `CLAIMGUARD_API_TOKEN` dans l'environnement, puis :

```bash
python -m uvicorn claimguard.api:app --host 127.0.0.1 --port 8000
```

`POST /search` exige `Authorization: Bearer <token>` et un objet `query`, `incident_date`, `mode`, `top_k`, éventuellement `category`. C'est une identité de service locale, pas un système RBAC multi-utilisateurs.

`docker compose up --build` prépare Qdrant serveur et Streamlit. Le mode sans Docker utilise Qdrant in-process. Docker/Windows n'ont pas été exécutés dans cet environnement ; seule la voie Linux in-process a été validée. Aucun port n'est publié sur une interface publique.

## Livrables de conception

1. [Inventaire du cours et matrice](docs/01_COURSE_MATRIX.md), plus inventaire JSON.
2. [Architecture technique](docs/02_ARCHITECTURE.md).
3. [Stratégie des 8 469 tickets](docs/03_DATA_STRATEGY.md).
4. [Modèle des politiques](docs/04_POLICY_MODEL.md).
5. [Plan détaillé et passage Level 1](docs/05_ROADMAP.md).
6. [Résultats et preuves](reports/RESULTS.md), [acceptation](reports/ACCEPTANCE.md).

Le dépôt Git est local. Aucun dépôt GitHub distant ni déploiement public n'est créé ou annoncé. Le code applicatif est écrit pour ce projet ; les exemples du cours sont référencés, non redistribués. Le modèle de base et les autres dépendances conservent leurs licences respectives.
