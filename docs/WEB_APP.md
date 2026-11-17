# Interface web React + API FastAPI

L’interface web reprend les quatre onglets de l’atelier Streamlit (Recherche, Documents,
Explication RAG, Évaluations) avec un frontend React et une API FastAPI dédiée. Elle utilise
**le même moteur** (`claimguard.runtime.build`) : SQLite, Qdrant dense + BM25, fusion RRF,
CrossEncoder, et Groq en option. Rien n’est simulé : sans modèles préparés, la recherche
renvoie un message expliquant la commande à lancer.

## Lancement (Windows / PowerShell)

Prérequis : l’installation du projet décrite dans le README et les modèles préparés.

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe scripts\prepare_models.py --profiles course multilingual   # une seule fois
.\.venv\Scripts\python.exe scripts\run_web.py
```

Le navigateur s’ouvre sur http://127.0.0.1:8000. Le frontend compilé (`frontend/dist`) est
livré : **Node.js n’est pas nécessaire** pour l’utiliser. La documentation interactive de
l’API est sur http://127.0.0.1:8000/docs.

Options : `--port 8001`, `--no-browser`, `--build` (recompile le frontend, Node.js 18+ requis),
`--api-only`.

La première recherche d’un couple corpus / profil / méthode charge les modèles et construit
l’index (de quelques secondes à une minute sur CPU). Les suivantes sont rapides ; le moteur
reste en mémoire (trois combinaisons au maximum).

## Développement du frontend

Deux terminaux :

```powershell
.\.venv\Scripts\python.exe scripts\run_web.py --api-only     # API sur 8000
cd frontend; npm install; npm run dev                         # Vite sur 5173, /api relayé vers 8000
```

Après modification : `npm run build` (ou `run_web.py --build`) régénère `frontend/dist`.

## Architecture

```
frontend/ (React 18 + TypeScript + Vite)
  src/api.ts              client typé de l’API
  src/App.tsx             coque : barre latérale, onglets, état partagé
  src/pages/SearchPage    formulaire, cas DRIP-R, résultats, brouillon Groq
  src/pages/DocumentsPage sources, sections, provenance, comparaison de versions
  src/pages/ExplainPage   étapes dense / BM25 / RRF / reranking / final
  src/pages/EvaluationPage KPI, graphique, tableaux, détail par question
src/claimguard/web.py     API FastAPI + service du build React (un seul port)
scripts/run_web.py        lanceur (vérifie les modèles, compile si besoin, ouvre le navigateur)
tests/test_web.py         tests de contrat avec un moteur par mots-clés (sans modèles)
```

## Points d’API

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/api/config` | corpus, profils, méthodes, Groq configuré ou non |
| GET | `/api/status?corpus&profile` | modèles présents, modes disponibles, moteurs chargés |
| POST | `/api/engine/load` | préchargement d’un moteur |
| GET | `/api/cases?q&limit` | 400 scénarios DRIP-R (plainte + contexte agent) |
| POST | `/api/search` | recherche ; renvoie toutes les étapes, diagnostics, brouillon éventuel |
| GET | `/api/documents`, `/api/documents/{nom}` | liste, texte, sections, métadonnées, SHA-256 |
| GET | `/api/documents/{nom}/download` | fichier source |
| GET | `/api/policies/{id}/versions`, `/compare?a&b` | catalogue SQLite et diff de versions |
| GET | `/api/evaluation`, `/api/evaluation/questions` | rapport mesuré et détail par question |

## Sécurité et limites

- Le lanceur écoute uniquement sur `127.0.0.1` ; CORS n’autorise que le serveur Vite local.
  Cette API web n’a pas d’authentification : ne l’exposez pas sur un réseau.
  L’API historique protégée par jeton (`claimguard.api`, `POST /search`) est inchangée.
- Les noms de documents sont vérifiés contre la liste du corpus (pas d’accès arbitraire au disque).
- Les erreurs sont journalisées dans `var/logs/errors.log` sans le texte des requêtes ; l’interface
  affiche une référence d’erreur.
- Comme dans Streamlit : les scores sont des scores de classement, le brouillon Groq est à vérifier
  par un humain, et DRIP-R reste un instantané non daté.
