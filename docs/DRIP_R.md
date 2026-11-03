# Adaptation de ClaimGuard AI au dataset DRIP-R

## Source, licence et fichiers

Source : https://huggingface.co/datasets/hsuvaskakoty/DRIP-R

Révision figée : `02f4c696df2a9170c3bea254ed2d60ea14bd4be4`.

Auteurs : Hsuvas Borkakoty, Sebastian Pohl, Cheng Wang, Bei Chen et Yufang Hou. DRIP-R: A Benchmark for Decision-Making and Reasoning Under Real-World Policy Ambiguity in the Retail Domain, 2026, arXiv:2605.07699. Les métadonnées Croissant déclarent CC BY 4.0. Les textes Amazon cités par le benchmark conservent leur provenance ; ils ne constituent pas ici un avis sur les règles Amazon actuelles.

Les originaux sont inclus sans modification dans `data/external/drip_r/`. Le script `prepare_drip_r.py --download` télécharge uniquement les fichiers manquants à la révision figée et vérifie tous les SHA-256. Une différence d'empreinte arrête l'import au lieu de remplacer silencieusement les données.

| Emplacement | Contenu |
|---|---|
| `data/external/drip_r/scenarios.jsonl` | Les 400 enregistrements source complets |
| `data/external/drip_r/tasks.jsonl` | 40 situations de référence du simulateur |
| `data/external/drip_r/personas.jsonl` | 10 profils synthétiques |
| `data/drip_r/agent_cases.jsonl` | 400 messages/résumés autorisés pour le RAG |
| `data/drip_r/policies/` | Deux textes exacts, métadonnées et bornes de sections |
| `data/drip_r/training/` | Questions de projet pour entraînement et validation |
| `data/drip_r/evaluation/questions.jsonl` | 50 scénarios annotés + 8 cas sans réponse |
| `reports/drip_r/` | Audit, expériences, preuves, limites et graphiques |
| `models/drip-r-policy-embedding/` | Checkpoint réellement entraîné |

## Audit et préparation

Le fichier contient 400 messages distincts et 400 identifiants de scénario distincts. Ils sont issus de seulement 40 situations, chacune déclinée selon 10 profils. Les politiques sont répétées dans les enregistrements : leur déduplication SHA-256 produit exactement deux textes uniques.

Les valeurs manquantes restent signalées dans `audit.json`. Les dix variantes de `task_051` contiennent un jeton numérique `NaN` non conforme au JSON strict dans `task.task`, alors que le fichier des tâches emploie une chaîne vide. Les originaux restent intacts ; la projection destinée à l'agent exclut ce champ et ses 400 lignes ont été vérifiées comme JSON strict. Le tableau des exceptions de durée et certaines conditions des frais sont incomplets dans le texte source. Il est interdit de les remplir par hypothèse. Les URLs de politiques d'origine et les dates de validité ne sont pas fournies dans les enregistrements.

Les textes sont conservés à l'identique dans les fichiers TXT. Des sidecars définissent 30 sections par numéros de lignes, sans modifier les phrases. `DRIP-001`, `DRIP-002`, les identifiants de section et la version `1.0` sont des références locales ajoutées par le projet ; ce ne sont pas des identifiants officiels Amazon. `page=1` représente uniquement une page logique TXT ; l'interface cite les lignes d'origine.

`effective_date=null`, `temporal_basis=dataset_snapshot` : on recherche dans un instantané documentaire. La date technique transmise à l'API n'établit aucune applicabilité historique. Aucune deuxième version n'étant fournie, la comparaison de versions n'est pas démontrée pour DRIP-R.

## Prévention des fuites

Le RAG ne reçoit que `first_customer_message` et `detail_agent`, en plus des politiques. Les champs `task`, `related_policy_issues`, `customer_task_detail.private_info`, `behavior` et les attributs du persona sont exclus de la projection destinée à l'agent. Ces champs complets restent disponibles dans les sources pour le chercheur, mais ne doivent pas être ajoutés au contexte du modèle.

Les IDs de scénarios comportent parfois des alias anciens ; le regroupement utilise le champ explicite `task_id`. L'échantillon de 50 scénarios couvre les 40 situations et les 10 profils, avec cinq exemples par profil. Les variantes ne sont pas considérées comme indépendantes : les rapports proposent aussi des moyennes par situation.

## Évaluation et fine-tuning

DRIP-R ne publie pas de décision correcte unique ni les annotations humaines décrites dans sa carte. Le projet ajoute explicitement des **annotations provisoires de pertinence documentaire**, créées par le modèle assistant après lecture des entrées visibles. Elles doivent être vérifiées par un humain avant d'être présentées comme vérité terrain validée. Les extraits, lignes et références associés sont disponibles dans le JSONL de test.

Les étiquettes ne garantissent pas une réponse complète ni une éligibilité. Par exemple, retrouver la clause des bundles ne prouve pas qu'un kit donné est un « Bundle with Savings ». Le système doit demander les faits manquants. Les huit questions sans réponse comprennent la conduite des employés, les dates historiques inconnues et les cellules absentes des tableaux.

Les 400 scénarios restent un benchmark externe. Pour l'exigence académique de fine-tuning, 60 requêtes distinctes sont rédigées à partir des 30 sections, avec 30 autres pour validation. Ce sont des données dérivées créées pour le projet, pas des labels officiels DRIP-R. Les requêtes de test ne servent ni aux gradients ni au choix du checkpoint. Le corpus documentaire étant partagé, les résultats mesurent une adaptation à un corpus connu.

Les expériences E1 à E5 utilisent la même pipeline que NovaRetail : Sentence Transformers, Qdrant, FastEmbed BM25, RRF k=60, CrossEncoder. Une comparaison dense seule isole également l'effet des embeddings adaptés. Les modèles, paramètres, empreintes, pertes et résultats par question sont conservés. Aucun résultat n'est transféré depuis le benchmark NovaRetail.

## Application, MCP et limites

Streamlit permet de choisir DRIP-R ou NovaRetail, de sélectionner un des 400 scénarios, de consulter ses passages et les étapes de classement. Un texte modifié n'est pas associé automatiquement au résumé d'un autre scénario. Les résultats conservés en session sont séparés par corpus.

Le serveur MCP officiel réutilise cette pipeline. Le client DRIP-R appelle réellement `search_policies` et `get_policy_section`. L'outil de comparaison reste disponible pour le corpus NovaRetail, qui possède plusieurs versions.

`drip_batch.py` récupère des preuves pour les 400 scénarios. Ses sorties portent le statut `EVIDENCE_RETRIEVED_ONLY` et `compliance_decision=null` : elles ne sont pas présentées comme des analyses LLM ou des décisions définitives.

La génération et la réécriture Groq sont intégrées mais nécessitent une clé dans `.env`. Aucun secret n'est inclus. L'exécution réelle n'a pas été possible ici. La classification métier avancée, l'évaluation de conformité complète et les décisions humaines persistées restent à développer après validation Level 1. Windows et Docker sont documentés mais n'ont pas été exécutés dans cet environnement Linux.

## Revue des annotations

Lire `data/drip_r/evaluation/questions.jsonl`, vérifier chaque `relevant_sections` à partir du seul texte visible puis enregistrer l'identité/date du réviseur dans une nouvelle version de l'annotation. Ne pas modifier les labels après observation d'une erreur de retrieval sans le documenter et refaire toutes les comparaisons sur le même jeu gelé. Les annotations actuelles ne sont pas présentées comme indépendantes ou expertes.
