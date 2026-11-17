# ClaimGuard AI — exploitation locale

L’architecture reste : parsing PDF/TXT/Markdown, catalogue SQLite immuable, vecteurs Qdrant dense et BM25, fusion RRF, CrossEncoder, puis brouillon Groq facultatif. Streamlit, API et MCP partagent le même moteur. DRIP-R et NovaRetail restent séparés.

## Installation et lancement Windows

Depuis la racine, avec Python 3.12 :

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe scripts/prepare_models.py --profiles course multilingual
.\.venv\Scripts\python.exe scripts/doctor.py --load
.\.venv\Scripts\python.exe scripts/run.py
```

Ouvrir <http://localhost:8501>. Pour un autre port : `python scripts/run.py --port 8502`. Le lancement vérifie les ressources et refuse d’utiliser un port déjà occupé. Il ne télécharge rien implicitement. Le lanceur Python fonctionne même lorsque Windows interdit les scripts `.ps1` ; aucune modification de la stratégie d’exécution n’est nécessaire. `scripts/start.ps1` reste disponible lorsque cette stratégie autorise les scripts. `run.py --check --port 8502` contrôle les ressources et le port sans démarrer de serveur.

La préparation est la seule étape nécessitant Hugging Face. Les modèles sont copiés dans `models/cache/<modèle>/<révision>`, chargés pour vérification et accompagnés d’un manifeste SHA-256. `prepare_models.py --offline` réutilise les snapshots locaux ; `doctor.py` vérifie les empreintes. Une suppression, corruption ou modification de poids impose une nouvelle préparation. Un dossier vide ne constitue pas un modèle prêt.

Le serveur HTTP peut être démarré sans moteur utilisable. Le diagnostic distingue les ressources présentes et l’index réellement chargé. Une première recherche initialise les composants nécessaires ; les suivantes réutilisent le cache Streamlit. Les index locaux sont en mémoire et se reconstruisent au redémarrage. `QDRANT_URL` permet de conserver le mode serveur Qdrant.

La configuration Docker conserve Qdrant serveur et Streamlit, copie les profils et monte le cache dans `/app/models`. Avant le premier lancement de l’interface, préparer les modèles dans ce volume avec `docker compose run --rm workbench python scripts/prepare_models.py --profiles course multilingual validated`, puis utiliser `docker compose up`. Cette voie Docker n’a pas été exécutée lors de la validation Windows locale.

## Configuration et diagnostic

`configs/retrieval.json` contient les révisions des modèles, les préfixes E5, les limites de tokens, le budget de candidats et les paramètres RRF. `course` garde les modèles du cours avec des fenêtres de tokens ; `course_reference` conserve le contexte original sans ces fenêtres ni enrichissement des titres ; `multilingual` est un candidat E5 multilingue ; `validated` enregistre le réglage sélectionné sur développement. `CLAIMGUARD_PROFILE` choisit un profil pour CLI/API/MCP ; l’interface possède son sélecteur. Les anciens paramètres isolés `EMBEDDING_MODEL` et `RERANKER_MODEL` sont remplacés par ces profils cohérents. Les préfixes `query:` et `passage:` suivent la [fiche officielle E5](https://huggingface.co/intfloat/multilingual-e5-small).

Les modes dense et sparse ne chargent pas les poids inutiles. Le mode sparse peut fonctionner sans embeddings ; s’il existe, le tokenizer local est utilisé pour garder le même découpage. Sans ce tokenizer, le découpage original est conservé et l’identité de l’index est différente.

Les fenêtres de tokens sont des données dérivées ; elles ne réécrivent ni les sources ni les chunks immuables de SQLite. Les références de sections restent stables. Les identités d’index comprennent le découpage, le profil et les empreintes des poids, y compris les checkpoints locaux. La sélection des candidats de reranking privilégie les sections distinctes ; les classements intermédiaires restent consultables par passage.

Les erreurs techniques sont dans `var/logs/errors.log`, avec identifiant et secrets expurgés. La trace de l’échec BM25 initial est dans `var/initial_failure.log`. Un modèle absent affiche sa commande de préparation. Une panne Groq conserve les preuves et affiche un avertissement ; une recherche locale n’envoie pas les questions à Groq.

## Évaluation et entraînement

```powershell
.\.venv\Scripts\python.exe scripts/prepare_development.py
.\.venv\Scripts\python.exe scripts/audit_annotations.py
.\.venv\Scripts\python.exe scripts/tune_retrieval.py
.\.venv\Scripts\python.exe training/finetune.py --corpus drip_r --epochs 3
.\.venv\Scripts\python.exe scripts/evaluate.py --corpus drip_r
.\.venv\Scripts\python.exe scripts/evaluate.py --corpus novaretail
```

Le jeu de développement comprend 40 questions avec réponse et 4 sans réponse, en français et en anglais, regroupées par situation bilingue. Il inclut des demandes nécessitant plusieurs sections et des négations. Les 40 exemples d’entraînement narratifs sont distincts. Aucun scénario DRIP-R original, champ privé du simulateur ou variante de ces scénarios ne sert au développement ou à l’entraînement. Les politiques sont volontairement partagées : cette expérience ne mesure pas la généralisation à des politiques inconnues.

La sélection des paramètres utilise seulement le développement : p95 ≤ 3 s si un candidat le permet, puis MRR@10, Recall@5 et latence. Le script enregistre les candidats et le choix exact. Le benchmark historique est conservé comme test de régression ; ses annotations restent inchangées. Après constat d’une régression intermédiaire, la diversité des candidats a été corrigée et le développement enrichi de cas multi-sections. Les rapports intermédiaires restent archivés ; le test historique ne doit pas être présenté comme un nouveau test aveugle indépendant.

L’entraînement utilise de vrais gradients CPU et des négatifs difficiles extraits de la baseline, en excluant toutes les sections déclarées pertinentes. L’époque zéro participe au choix. Chaque époque est évaluée par recherche réelle dans Qdrant ; le meilleur checkpoint est choisi sur MRR puis Recall. Une comparaison de bout en bout sur développement décide de son éligibilité. Le checkpoint du modèle de référence n’est jamais écrasé et aucun modèle entraîné n’est promu automatiquement. Pour mesurer un checkpoint sur test, utiliser `evaluate.py --corpus drip_r --trained <chemin du checkpoint>`.

Les anciennes mesures sont conservées dans `reports/baselines/v1` et `reports/drip_r/baselines/v1`. Les nouvelles exécutions sont versionnées dans les dossiers `runs` ; `latest.json` alimente l’interface. Les rapports indiquent empreintes des données, sources, profil, langues, moyennes par situation et protocole de latence. Les moyennes de retrieval excluent les questions sans réponse ; celles-ci restent enregistrées et ne sont pas déclarées correctement traitées sur la seule base d’un score de recherche.

Recall@1 n’est pas une précision : une question avec trois sections attendues ne peut obtenir plus de 1/3 de rappel au premier rang. Hit@1 indique si le premier résultat est pertinent. Les scores du moteur ne sont pas des probabilités de conformité.

Les annotations restent des jugements de pertinence synthétiques nécessitant une revue humaine indépendante. L’audit automatique contrôle l’existence des références et la provenance ; il ne constitue pas cette revue. Toute correction future doit créer une version justifiée du jeu, sans réécrire le test initial.

## API, MCP et Groq

```powershell
.\.venv\Scripts\python.exe -m uvicorn claimguard.api:app --host 127.0.0.1 --port 8000
.\.venv\Scripts\python.exe -m claimguard.mcp.client --corpus drip_r
.\.venv\Scripts\python.exe -m claimguard.mcp.client --corpus novaretail
```

`POST /search` conserve ses entrées et son authentification Bearer. `GET /health` confirme le serveur ; `GET /ready`, authentifié, fournit le diagnostic de ressources et précise si un moteur est chargé. Une erreur de recherche retourne 503 avec un identifiant de journal. Les outils MCP conservent leurs noms et arguments ; la consultation documentaire ne nécessite pas de poids de modèles.

Groq utilise la clé locale `GROQ_API_KEY` dans `.env`. Ne jamais la copier dans un rapport ou un dépôt. Une génération transmet la question et les passages retrouvés au fournisseur. La commande de vérification facultative est :

```powershell
.\.venv\Scripts\python.exe scripts/live_rag_check.py --corpus drip_r --sample 3
```

Elle envoie trois questions synthétiques avec réponse et les huit cas sans réponse, ainsi que leurs passages. Elle valide les citations exactes et mesure l’abstention sur cet échantillon ; les erreurs restent dans le dénominateur. Elle ne mesure pas automatiquement la fidélité sémantique de chaque affirmation. Le test externe n’a pas été exécuté lors de cette livraison : le contrôle automatique d’approbation demande une autorisation explicite pour ces données vers Groq.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp var/test-local
```

Utiliser un nouveau dossier temporaire si le précédent appartient à un autre contexte Windows. Les tests intègrent les vrais modèles et Qdrant, la requête de la capture, les quatre modes, FR/EN, les filtres, le fonctionnement hors réseau, les ressources absentes, la déduplication et la conservation des preuves lors d’une panne Groq simulée. Ils ne déclenchent aucun appel Groq réel.
