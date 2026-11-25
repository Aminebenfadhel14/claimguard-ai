# Résultats mesurés — ClaimGuard AI v3

Document généré par `python -m claimguard report` à partir des fichiers de `reports/v3/` ; aucun nombre n’est saisi à la main.

Cours : https://github.com/Nadjib23/AI-Engineering-Course — révision `fc178ae632816c42dbca8f5c01e97932f0f32502` (labs/04-rag, labs/05-Evaluation/Retrieval Evaluation).

Modèles : `sentence-transformers/all-MiniLM-L6-v2`, `Qdrant/bm25`, `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`.

**Non comparable aux rapports v2** (`reports/archive/v2_sections/`) : l’unité de mesure passe de la section au chunk Qdrant, les chunks et la chaîne de recherche ont changé, et un nouveau benchmark documentaire est ajouté.

## Benchmark documentaire (méthode du cours)

79 questions générées par `openai/gpt-oss-120b` à partir des 41 paragraphes en vigueur le 2026-01-01 ; passage justificatif vérifié dans le paragraphe source. Rejets ou échecs : {'retried_after_error': 1, 'passage_not_found': 3}. Répartition par paragraphe : {'development': 42, 'test': 37}.

## Test — benchmark documentaire

collection `claimguard_c1000_o100`, 20 candidats, k=5, réécriture désactivée ; 37/37 questions évaluées.

| Stratégie | precision@5 | recall@5 | hit@5 | mrr@5 | ndcg@5 | Latence p50 | Latence p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| dense | 0.200 | 0.937 | 0.973 | 0.860 | 0.866 | 13 ms | 16 ms |
| dense+rerank | 0.211 | 0.973 | 1.000 | 0.973 | 0.955 | 866 ms | 958 ms |
| sparse | 0.195 | 0.910 | 0.946 | 0.860 | 0.852 | 15 ms | 28 ms |
| sparse+rerank | 0.205 | 0.964 | 1.000 | 0.973 | 0.950 | 900 ms | 1140 ms |
| hybrid | 0.205 | 0.964 | 1.000 | 0.901 | 0.899 | 17 ms | 35 ms |
| hybrid+rerank | 0.205 | 0.964 | 1.000 | 0.973 | 0.950 | 975 ms | 1146 ms |

Requêtes plus longues que la limite du modèle dense (256 tokens, tronquées) : 0/37 (médiane 26 tokens). Chunks tronqués par le modèle dense : 0/122 (médiane 160.5 tokens).

## Test — plaintes CFPB réelles

collection `claimguard_c1000_o100`, 20 candidats, k=5, réécriture désactivée ; 180/201 questions évaluées.

Plaintes hors périmètre (aucun paragraphe annoté), exclues des métriques de recherche et utilisées pour l’abstention : 21 — CFPB-11368452, CFPB-11949064, CFPB-11374012, CFPB-12133825, CFPB-11720589, CFPB-11363523, CFPB-11550766, CFPB-11503430, CFPB-11466705, CFPB-12071115, CFPB-12058901, CFPB-11694241, CFPB-11881431, CFPB-11871084, CFPB-11532875, CFPB-11631605, CFPB-11945142, CFPB-11694504, CFPB-11544075, CFPB-11577760, CFPB-11579553.

| Stratégie | precision@5 | recall@5 | hit@5 | mrr@5 | ndcg@5 | paragraph_recall@5 | Latence p50 | Latence p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dense | 0.213 | 0.134 | 0.522 | 0.379 | 0.239 | 0.282 | 38 ms | 60 ms |
| dense+rerank | 0.168 | 0.126 | 0.539 | 0.320 | 0.186 | 0.321 | 1581 ms | 2114 ms |
| sparse | 0.166 | 0.109 | 0.472 | 0.284 | 0.176 | 0.235 | 14 ms | 27 ms |
| sparse+rerank | 0.169 | 0.128 | 0.528 | 0.322 | 0.190 | 0.330 | 1429 ms | 1591 ms |
| hybrid | 0.212 | 0.138 | 0.572 | 0.362 | 0.227 | 0.297 | 31 ms | 52 ms |
| hybrid+rerank | 0.169 | 0.128 | 0.522 | 0.320 | 0.189 | 0.323 | 1514 ms | 1821 ms |

Labels faibles : correspondance catégorie CFPB -> paragraphe (configs/cfpb.json), sans revue juridique. Qrels = tous les chunks des paragraphes annotés. Les plaintes hors périmètre (aucun paragraphe annoté) sont exclues des métriques de recherche.

Version en vigueur à la date de réception de la plainte par la CFPB (date_received) : ce n’est pas la date des faits, inconnue.

recall@5 (chunk) par règle d’annotation :

| Stratégie | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| dense | 0.150 | 0.058 | 0.195 | 0.200 | 0.100 | 0.222 | 0.244 | 0.037 | 0.000 |
| dense+rerank | 0.138 | 0.125 | 0.105 | 0.127 | 0.200 | 0.172 | 0.181 | 0.050 | 0.033 |
| sparse | 0.025 | 0.083 | 0.109 | 0.109 | 0.025 | 0.244 | 0.188 | 0.113 | 0.083 |
| sparse+rerank | 0.037 | 0.092 | 0.082 | 0.127 | 0.125 | 0.189 | 0.181 | 0.237 | 0.083 |
| hybrid | 0.100 | 0.058 | 0.182 | 0.173 | 0.075 | 0.239 | 0.250 | 0.100 | 0.067 |
| hybrid+rerank | 0.138 | 0.092 | 0.105 | 0.118 | 0.150 | 0.172 | 0.188 | 0.125 | 0.067 |

Requêtes plus longues que la limite du modèle dense (256 tokens, tronquées) : 80/201 (médiane 212 tokens). Chunks tronqués par le modèle dense : 0/122 (médiane 160.5 tokens).

## Sélection sur le développement

Sur le développement uniquement : moyenne de hit@5 (suite documents : au moins un chunk du passage dans le top 5) et de paragraph_recall@5 (suite cfpb : part des paragraphes annotés couverts par le top 5) ; égalité départagée par la moyenne de mrr@5, puis par la configuration la plus simple (sans reranking, sans réécriture, découpage de référence, 20 candidats).

Règle initiale (recall@5 par chunk) remplacée avant tout run de test : le recall par chunk dépend du nombre de chunks pertinents, donc de la taille des chunks, et ne permet pas de comparer deux découpages.

Configuration retenue (avant le test) : `claimguard_c1000_o100`, 20 candidats, réécriture non, hybrid+rerank — développement : documents hit@5 1.000, CFPB paragraph_recall@5 0.327.

| Rang | Collection | Candidats | Réécriture | Stratégie | hit@5 docs | paragraph_recall@5 CFPB | Moyenne |
|---:|---|---:|---|---|---:|---:|---:|
| 1 | claimguard_c1000_o100 | 20 | non | hybrid+rerank | 1.000 | 0.327 | 0.664 |
| 2 | claimguard_c1000_o100 | 20 | non | sparse+rerank | 1.000 | 0.324 | 0.662 |
| 3 | claimguard_c1000_o100 | 20 | non | dense+rerank | 1.000 | 0.308 | 0.654 |
| 4 | claimguard_c1000_o100 | 40 | non | hybrid | 1.000 | 0.300 | 0.650 |
| 5 | claimguard_c1000_o100 | 40 | oui | hybrid | 1.000 | 0.299 | 0.649 |
| 6 | claimguard_c1000_o100 | 20 | non | hybrid | 1.000 | 0.296 | 0.648 |
| 7 | claimguard_c1000_o100 | 40 | non | dense+rerank | 1.000 | 0.289 | 0.645 |
| 8 | claimguard_c1000_o100 | 20 | non | dense | 1.000 | 0.289 | 0.645 |
| 9 | claimguard_c1000_o100 | 40 | non | dense | 1.000 | 0.289 | 0.645 |
| 10 | claimguard_c500_o50 | 20 | non | hybrid | 1.000 | 0.289 | 0.645 |
| 11 | claimguard_c500_o50 | 40 | non | hybrid | 1.000 | 0.289 | 0.645 |
| 12 | claimguard_c1000_o100 | 40 | non | hybrid+rerank | 1.000 | 0.285 | 0.642 |
| 13 | claimguard_c500_o50 | 40 | oui | hybrid | 1.000 | 0.267 | 0.634 |
| 14 | claimguard_c1000_o100 | 20 | oui | hybrid | 0.976 | 0.289 | 0.633 |
| 15 | claimguard_c1000_o100 | 20 | oui | hybrid+rerank | 1.000 | 0.264 | 0.632 |
| 16 | claimguard_c1000_o100 | 40 | oui | hybrid+rerank | 1.000 | 0.263 | 0.631 |
| 17 | claimguard_c500_o50 | 20 | oui | hybrid | 1.000 | 0.259 | 0.630 |
| 18 | claimguard_c1000_o100 | 40 | non | sparse+rerank | 1.000 | 0.258 | 0.629 |
| 19 | claimguard_c1000_o100 | 40 | oui | sparse+rerank | 1.000 | 0.245 | 0.623 |
| 20 | claimguard_c500_o50 | 20 | non | dense+rerank | 0.952 | 0.289 | 0.621 |
| 21 | claimguard_c500_o50 | 20 | non | dense | 0.952 | 0.288 | 0.620 |
| 22 | claimguard_c500_o50 | 40 | non | dense | 0.952 | 0.288 | 0.620 |
| 23 | claimguard_c1000_o100 | 20 | oui | sparse+rerank | 1.000 | 0.237 | 0.619 |
| 24 | claimguard_c1000_o100 | 20 | non | sparse | 0.976 | 0.259 | 0.618 |
| 25 | claimguard_c1000_o100 | 40 | non | sparse | 0.976 | 0.259 | 0.618 |
| 26 | claimguard_c500_o50 | 20 | non | hybrid+rerank | 0.952 | 0.280 | 0.616 |
| 27 | claimguard_c500_o50 | 40 | non | hybrid+rerank | 0.952 | 0.272 | 0.612 |
| 28 | claimguard_c1000_o100 | 40 | oui | dense+rerank | 1.000 | 0.222 | 0.611 |
| 29 | claimguard_c500_o50 | 20 | non | sparse+rerank | 0.952 | 0.266 | 0.609 |
| 30 | claimguard_c1000_o100 | 20 | oui | dense+rerank | 0.976 | 0.236 | 0.606 |
| 31 | claimguard_c1000_o100 | 20 | oui | sparse | 0.952 | 0.258 | 0.605 |
| 32 | claimguard_c1000_o100 | 40 | oui | sparse | 0.952 | 0.258 | 0.605 |
| 33 | claimguard_c500_o50 | 40 | non | dense+rerank | 0.952 | 0.258 | 0.605 |
| 34 | claimguard_c500_o50 | 40 | non | sparse+rerank | 0.952 | 0.228 | 0.590 |
| 35 | claimguard_c500_o50 | 20 | oui | dense | 0.905 | 0.269 | 0.587 |
| 36 | claimguard_c500_o50 | 40 | oui | dense | 0.905 | 0.269 | 0.587 |
| 37 | claimguard_c500_o50 | 20 | non | sparse | 0.905 | 0.247 | 0.576 |
| 38 | claimguard_c500_o50 | 40 | non | sparse | 0.905 | 0.247 | 0.576 |
| 39 | claimguard_c1000_o100 | 20 | oui | dense | 0.857 | 0.292 | 0.575 |
| 40 | claimguard_c1000_o100 | 40 | oui | dense | 0.857 | 0.292 | 0.575 |
| 41 | claimguard_c500_o50 | 20 | oui | dense+rerank | 0.929 | 0.220 | 0.574 |
| 42 | claimguard_c500_o50 | 20 | oui | sparse | 0.881 | 0.263 | 0.572 |
| 43 | claimguard_c500_o50 | 40 | oui | sparse | 0.881 | 0.263 | 0.572 |
| 44 | claimguard_c500_o50 | 20 | oui | sparse+rerank | 0.929 | 0.214 | 0.571 |
| 45 | claimguard_c500_o50 | 40 | oui | dense+rerank | 0.929 | 0.209 | 0.569 |
| 46 | claimguard_c500_o50 | 20 | oui | hybrid+rerank | 0.929 | 0.209 | 0.569 |
| 47 | claimguard_c500_o50 | 40 | oui | hybrid+rerank | 0.929 | 0.193 | 0.561 |
| 48 | claimguard_c500_o50 | 40 | oui | sparse+rerank | 0.929 | 0.182 | 0.555 |

## Analyse sur le développement (effets moyens mesurés)

Chaque ligne compare deux runs qui ne diffèrent que par un facteur (autres facteurs : `claimguard_c1000_o100`, 20 candidats, sans réécriture), moyenne sur les stratégies indiquées. Mesures : documents hit@5, CFPB paragraph_recall@5.

| Facteur | Stratégies | Documents A → B | CFPB A → B |
|---|---|---:|---:|
| Réécriture Groq (non → oui) | dense, dense+rerank, sparse, sparse+rerank, hybrid, hybrid+rerank | 0.996 → 0.960 | 0.301 → 0.263 |
| Réécriture Groq (non → oui), sans reranking | dense, sparse, hybrid | 0.992 → 0.929 | 0.281 → 0.280 |
| Réécriture Groq (non → oui), avec reranking | dense+rerank, sparse+rerank, hybrid+rerank | 1.000 → 0.992 | 0.320 → 0.246 |
| Candidats (20 → 40), avec reranking | dense+rerank, sparse+rerank, hybrid+rerank | 1.000 → 1.000 | 0.320 → 0.277 |
| Découpage (1000/100 → 500/50) | dense, dense+rerank, sparse, sparse+rerank, hybrid, hybrid+rerank | 0.996 → 0.952 | 0.301 → 0.276 |
| CrossEncoder (sans → avec), documents | — | dense: 1.000 → 1.000; sparse: 0.976 → 1.000; hybrid: 1.000 → 1.000 |  |
| CrossEncoder (sans → avec), cfpb | — |  | dense: 0.289 → 0.308; sparse: 0.259 → 0.324; hybrid: 0.296 → 0.327 |

## Développement — détail des runs

### cfpb — collection `claimguard_c1000_o100`, 20 candidats, k=5, réécriture désactivée ; 106/106 questions évaluées

| Stratégie | precision@5 | recall@5 | hit@5 | mrr@5 | ndcg@5 | paragraph_recall@5 | Latence p50 | Latence p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dense | 0.211 | 0.135 | 0.547 | 0.389 | 0.235 | 0.289 | 41 ms | 65 ms |
| dense+rerank | 0.177 | 0.128 | 0.547 | 0.327 | 0.189 | 0.308 | 1782 ms | 2112 ms |
| sparse | 0.158 | 0.109 | 0.500 | 0.292 | 0.169 | 0.259 | 7 ms | 29 ms |
| sparse+rerank | 0.183 | 0.134 | 0.566 | 0.336 | 0.198 | 0.324 | 1684 ms | 1991 ms |
| hybrid | 0.200 | 0.135 | 0.585 | 0.361 | 0.215 | 0.296 | 39 ms | 61 ms |
| hybrid+rerank | 0.181 | 0.136 | 0.575 | 0.351 | 0.203 | 0.327 | 1775 ms | 2101 ms |

### cfpb — collection `claimguard_c1000_o100`, 20 candidats, k=5, réécriture Groq (openai/gpt-oss-120b) ; 106/106 questions évaluées

| Stratégie | precision@5 | recall@5 | hit@5 | mrr@5 | ndcg@5 | paragraph_recall@5 | Latence p50 | Latence p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dense | 0.234 | 0.144 | 0.575 | 0.408 | 0.256 | 0.292 | 16 ms | 36 ms |
| dense+rerank | 0.172 | 0.101 | 0.434 | 0.281 | 0.179 | 0.236 | 928 ms | 1105 ms |
| sparse | 0.168 | 0.127 | 0.509 | 0.300 | 0.182 | 0.258 | 5 ms | 27 ms |
| sparse+rerank | 0.160 | 0.112 | 0.472 | 0.275 | 0.168 | 0.237 | 1003 ms | 1168 ms |
| hybrid | 0.223 | 0.151 | 0.566 | 0.371 | 0.237 | 0.289 | 17 ms | 34 ms |
| hybrid+rerank | 0.179 | 0.122 | 0.500 | 0.299 | 0.186 | 0.264 | 996 ms | 1138 ms |

### cfpb — collection `claimguard_c1000_o100`, 40 candidats, k=5, réécriture désactivée ; 106/106 questions évaluées

| Stratégie | precision@5 | recall@5 | hit@5 | mrr@5 | ndcg@5 | paragraph_recall@5 | Latence p50 | Latence p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dense | 0.211 | 0.135 | 0.547 | 0.389 | 0.235 | 0.289 | 38 ms | 61 ms |
| dense+rerank | 0.158 | 0.099 | 0.547 | 0.296 | 0.164 | 0.289 | 3149 ms | 3986 ms |
| sparse | 0.158 | 0.109 | 0.500 | 0.292 | 0.169 | 0.259 | 8 ms | 30 ms |
| sparse+rerank | 0.140 | 0.095 | 0.500 | 0.275 | 0.149 | 0.258 | 3236 ms | 3919 ms |
| hybrid | 0.202 | 0.138 | 0.604 | 0.354 | 0.214 | 0.300 | 41 ms | 61 ms |
| hybrid+rerank | 0.155 | 0.104 | 0.509 | 0.288 | 0.165 | 0.285 | 3264 ms | 3992 ms |

### cfpb — collection `claimguard_c1000_o100`, 40 candidats, k=5, réécriture Groq (openai/gpt-oss-120b) ; 106/106 questions évaluées

| Stratégie | precision@5 | recall@5 | hit@5 | mrr@5 | ndcg@5 | paragraph_recall@5 | Latence p50 | Latence p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dense | 0.234 | 0.144 | 0.575 | 0.408 | 0.256 | 0.292 | 16 ms | 36 ms |
| dense+rerank | 0.162 | 0.099 | 0.453 | 0.294 | 0.174 | 0.222 | 1876 ms | 2183 ms |
| sparse | 0.168 | 0.127 | 0.509 | 0.300 | 0.182 | 0.258 | 15 ms | 30 ms |
| sparse+rerank | 0.160 | 0.109 | 0.472 | 0.272 | 0.168 | 0.245 | 1845 ms | 2115 ms |
| hybrid | 0.226 | 0.153 | 0.566 | 0.361 | 0.236 | 0.299 | 20 ms | 33 ms |
| hybrid+rerank | 0.172 | 0.116 | 0.500 | 0.298 | 0.181 | 0.263 | 1870 ms | 2204 ms |

### cfpb — collection `claimguard_c500_o50`, 20 candidats, k=5, réécriture désactivée ; 106/106 questions évaluées

| Stratégie | precision@5 | recall@5 | hit@5 | mrr@5 | ndcg@5 | paragraph_recall@5 | Latence p50 | Latence p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dense | 0.211 | 0.077 | 0.481 | 0.333 | 0.223 | 0.288 | 40 ms | 81 ms |
| dense+rerank | 0.175 | 0.068 | 0.509 | 0.301 | 0.176 | 0.289 | 1289 ms | 2016 ms |
| sparse | 0.157 | 0.054 | 0.472 | 0.281 | 0.162 | 0.247 | 5 ms | 29 ms |
| sparse+rerank | 0.164 | 0.060 | 0.481 | 0.281 | 0.165 | 0.266 | 1166 ms | 2111 ms |
| hybrid | 0.206 | 0.069 | 0.509 | 0.330 | 0.209 | 0.289 | 39 ms | 62 ms |
| hybrid+rerank | 0.179 | 0.067 | 0.491 | 0.290 | 0.179 | 0.280 | 1233 ms | 2028 ms |

### cfpb — collection `claimguard_c500_o50`, 20 candidats, k=5, réécriture Groq (openai/gpt-oss-120b) ; 106/106 questions évaluées

| Stratégie | precision@5 | recall@5 | hit@5 | mrr@5 | ndcg@5 | paragraph_recall@5 | Latence p50 | Latence p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dense | 0.234 | 0.072 | 0.491 | 0.333 | 0.235 | 0.269 | 16 ms | 33 ms |
| dense+rerank | 0.174 | 0.059 | 0.425 | 0.259 | 0.171 | 0.220 | 525 ms | 678 ms |
| sparse | 0.172 | 0.065 | 0.519 | 0.250 | 0.158 | 0.263 | 5 ms | 20 ms |
| sparse+rerank | 0.168 | 0.057 | 0.425 | 0.225 | 0.155 | 0.214 | 520 ms | 666 ms |
| hybrid | 0.192 | 0.064 | 0.491 | 0.312 | 0.194 | 0.259 | 16 ms | 36 ms |
| hybrid+rerank | 0.162 | 0.056 | 0.434 | 0.247 | 0.157 | 0.209 | 521 ms | 683 ms |

### cfpb — collection `claimguard_c500_o50`, 40 candidats, k=5, réécriture désactivée ; 106/106 questions évaluées

| Stratégie | precision@5 | recall@5 | hit@5 | mrr@5 | ndcg@5 | paragraph_recall@5 | Latence p50 | Latence p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dense | 0.211 | 0.077 | 0.481 | 0.333 | 0.223 | 0.288 | 43 ms | 88 ms |
| dense+rerank | 0.153 | 0.056 | 0.500 | 0.265 | 0.151 | 0.258 | 2228 ms | 3905 ms |
| sparse | 0.157 | 0.054 | 0.472 | 0.281 | 0.162 | 0.247 | 6 ms | 31 ms |
| sparse+rerank | 0.125 | 0.048 | 0.425 | 0.233 | 0.127 | 0.228 | 2292 ms | 3861 ms |
| hybrid | 0.208 | 0.070 | 0.509 | 0.315 | 0.207 | 0.289 | 40 ms | 62 ms |
| hybrid+rerank | 0.155 | 0.059 | 0.500 | 0.281 | 0.156 | 0.272 | 2356 ms | 3896 ms |

### cfpb — collection `claimguard_c500_o50`, 40 candidats, k=5, réécriture Groq (openai/gpt-oss-120b) ; 106/106 questions évaluées

| Stratégie | precision@5 | recall@5 | hit@5 | mrr@5 | ndcg@5 | paragraph_recall@5 | Latence p50 | Latence p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dense | 0.234 | 0.072 | 0.491 | 0.333 | 0.235 | 0.269 | 16 ms | 35 ms |
| dense+rerank | 0.147 | 0.052 | 0.443 | 0.258 | 0.149 | 0.209 | 989 ms | 1249 ms |
| sparse | 0.172 | 0.065 | 0.519 | 0.250 | 0.158 | 0.263 | 6 ms | 27 ms |
| sparse+rerank | 0.134 | 0.045 | 0.387 | 0.214 | 0.131 | 0.182 | 1019 ms | 1312 ms |
| hybrid | 0.194 | 0.064 | 0.491 | 0.300 | 0.193 | 0.267 | 19 ms | 37 ms |
| hybrid+rerank | 0.138 | 0.049 | 0.406 | 0.230 | 0.137 | 0.193 | 1027 ms | 1298 ms |

### documents — collection `claimguard_c1000_o100`, 20 candidats, k=5, réécriture désactivée ; 42/42 questions évaluées

| Stratégie | precision@5 | recall@5 | hit@5 | mrr@5 | ndcg@5 | Latence p50 | Latence p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| dense | 0.257 | 0.895 | 1.000 | 0.869 | 0.828 | 15 ms | 34 ms |
| dense+rerank | 0.271 | 0.931 | 1.000 | 0.972 | 0.922 | 895 ms | 1024 ms |
| sparse | 0.252 | 0.871 | 0.976 | 0.897 | 0.834 | 5 ms | 28 ms |
| sparse+rerank | 0.276 | 0.942 | 1.000 | 0.972 | 0.927 | 940 ms | 1123 ms |
| hybrid | 0.267 | 0.919 | 1.000 | 0.925 | 0.880 | 17 ms | 28 ms |
| hybrid+rerank | 0.271 | 0.931 | 1.000 | 0.972 | 0.922 | 1045 ms | 1168 ms |

### documents — collection `claimguard_c1000_o100`, 20 candidats, k=5, réécriture Groq (openai/gpt-oss-120b) ; 42/42 questions évaluées

| Stratégie | precision@5 | recall@5 | hit@5 | mrr@5 | ndcg@5 | Latence p50 | Latence p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| dense | 0.219 | 0.744 | 0.857 | 0.726 | 0.676 | 13 ms | 36 ms |
| dense+rerank | 0.262 | 0.895 | 0.976 | 0.937 | 0.879 | 858 ms | 935 ms |
| sparse | 0.243 | 0.847 | 0.952 | 0.905 | 0.828 | 5 ms | 30 ms |
| sparse+rerank | 0.267 | 0.919 | 1.000 | 0.960 | 0.902 | 892 ms | 1053 ms |
| hybrid | 0.257 | 0.883 | 0.976 | 0.881 | 0.829 | 14 ms | 35 ms |
| hybrid+rerank | 0.267 | 0.919 | 1.000 | 0.960 | 0.902 | 938 ms | 1132 ms |

### documents — collection `claimguard_c1000_o100`, 40 candidats, k=5, réécriture désactivée ; 42/42 questions évaluées

| Stratégie | precision@5 | recall@5 | hit@5 | mrr@5 | ndcg@5 | Latence p50 | Latence p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| dense | 0.257 | 0.895 | 1.000 | 0.869 | 0.828 | 15 ms | 35 ms |
| dense+rerank | 0.276 | 0.942 | 1.000 | 0.972 | 0.927 | 1762 ms | 1976 ms |
| sparse | 0.252 | 0.871 | 0.976 | 0.897 | 0.834 | 15 ms | 28 ms |
| sparse+rerank | 0.276 | 0.942 | 1.000 | 0.972 | 0.927 | 1747 ms | 1870 ms |
| hybrid | 0.267 | 0.919 | 1.000 | 0.937 | 0.886 | 16 ms | 35 ms |
| hybrid+rerank | 0.276 | 0.942 | 1.000 | 0.972 | 0.927 | 1760 ms | 1918 ms |

### documents — collection `claimguard_c1000_o100`, 40 candidats, k=5, réécriture Groq (openai/gpt-oss-120b) ; 42/42 questions évaluées

| Stratégie | precision@5 | recall@5 | hit@5 | mrr@5 | ndcg@5 | Latence p50 | Latence p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| dense | 0.219 | 0.744 | 0.857 | 0.726 | 0.676 | 13 ms | 34 ms |
| dense+rerank | 0.267 | 0.919 | 1.000 | 0.960 | 0.902 | 1702 ms | 1900 ms |
| sparse | 0.243 | 0.847 | 0.952 | 0.905 | 0.828 | 6 ms | 30 ms |
| sparse+rerank | 0.267 | 0.919 | 1.000 | 0.960 | 0.902 | 1721 ms | 1830 ms |
| hybrid | 0.262 | 0.907 | 1.000 | 0.886 | 0.841 | 16 ms | 36 ms |
| hybrid+rerank | 0.267 | 0.919 | 1.000 | 0.960 | 0.902 | 1702 ms | 1807 ms |

### documents — collection `claimguard_c500_o50`, 20 candidats, k=5, réécriture désactivée ; 42/42 questions évaluées

| Stratégie | precision@5 | recall@5 | hit@5 | mrr@5 | ndcg@5 | Latence p50 | Latence p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| dense | 0.281 | 0.721 | 0.952 | 0.804 | 0.690 | 22 ms | 34 ms |
| dense+rerank | 0.300 | 0.735 | 0.952 | 0.877 | 0.735 | 504 ms | 638 ms |
| sparse | 0.290 | 0.724 | 0.905 | 0.810 | 0.697 | 14 ms | 28 ms |
| sparse+rerank | 0.314 | 0.758 | 0.952 | 0.877 | 0.748 | 479 ms | 604 ms |
| hybrid | 0.329 | 0.822 | 1.000 | 0.883 | 0.773 | 17 ms | 33 ms |
| hybrid+rerank | 0.319 | 0.766 | 0.952 | 0.877 | 0.755 | 490 ms | 631 ms |

### documents — collection `claimguard_c500_o50`, 20 candidats, k=5, réécriture Groq (openai/gpt-oss-120b) ; 42/42 questions évaluées

| Stratégie | precision@5 | recall@5 | hit@5 | mrr@5 | ndcg@5 | Latence p50 | Latence p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| dense | 0.276 | 0.699 | 0.905 | 0.705 | 0.613 | 18 ms | 39 ms |
| dense+rerank | 0.300 | 0.737 | 0.929 | 0.858 | 0.732 | 494 ms | 609 ms |
| sparse | 0.286 | 0.718 | 0.881 | 0.792 | 0.694 | 5 ms | 25 ms |
| sparse+rerank | 0.310 | 0.760 | 0.929 | 0.846 | 0.739 | 459 ms | 588 ms |
| hybrid | 0.314 | 0.802 | 1.000 | 0.794 | 0.713 | 16 ms | 34 ms |
| hybrid+rerank | 0.314 | 0.772 | 0.929 | 0.846 | 0.745 | 461 ms | 566 ms |

### documents — collection `claimguard_c500_o50`, 40 candidats, k=5, réécriture désactivée ; 42/42 questions évaluées

| Stratégie | precision@5 | recall@5 | hit@5 | mrr@5 | ndcg@5 | Latence p50 | Latence p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| dense | 0.281 | 0.721 | 0.952 | 0.804 | 0.690 | 17 ms | 54 ms |
| dense+rerank | 0.319 | 0.766 | 0.952 | 0.877 | 0.755 | 978 ms | 1233 ms |
| sparse | 0.290 | 0.724 | 0.905 | 0.810 | 0.697 | 15 ms | 30 ms |
| sparse+rerank | 0.319 | 0.766 | 0.952 | 0.877 | 0.755 | 967 ms | 1176 ms |
| hybrid | 0.329 | 0.822 | 1.000 | 0.871 | 0.774 | 17 ms | 33 ms |
| hybrid+rerank | 0.319 | 0.766 | 0.952 | 0.877 | 0.755 | 975 ms | 1183 ms |

### documents — collection `claimguard_c500_o50`, 40 candidats, k=5, réécriture Groq (openai/gpt-oss-120b) ; 42/42 questions évaluées

| Stratégie | precision@5 | recall@5 | hit@5 | mrr@5 | ndcg@5 | Latence p50 | Latence p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| dense | 0.276 | 0.699 | 0.905 | 0.705 | 0.613 | 20 ms | 32 ms |
| dense+rerank | 0.310 | 0.760 | 0.929 | 0.858 | 0.748 | 904 ms | 1109 ms |
| sparse | 0.286 | 0.718 | 0.881 | 0.792 | 0.694 | 5 ms | 26 ms |
| sparse+rerank | 0.310 | 0.760 | 0.929 | 0.846 | 0.739 | 919 ms | 1178 ms |
| hybrid | 0.319 | 0.810 | 1.000 | 0.818 | 0.729 | 26 ms | 33 ms |
| hybrid+rerank | 0.310 | 0.760 | 0.929 | 0.846 | 0.739 | 918 ms | 1108 ms |

## Génération (évaluée séparément de la recherche)

Modèle `openai/gpt-oss-120b`, options {'mode': 'hybrid', 'rerank': True, 'rewrite': False, 'k': 5, 'n_candidates': 20}, 56 questions de test. Échecs de génération : 0 ; échecs de réécriture : 0 ; passages conservés en cas d’échec : oui. Citations retrouvées mot pour mot : 0.904.

| Groupe | Questions | Échecs | Taux d’abstention | Réponse avec citation vérifiée |
|---|---:|---:|---:|---:|
| documents | 20 | 0 | 0.050 | 0.950 |
| cfpb_in_scope | 15 | 0 | 0.333 | 0.667 |
| cfpb_out_of_scope | 21 | 0 | 0.619 | 0.381 |

Documents : nombres de la réponse de référence présents dans la réponse générée : 0.556 (indicateur lexical).

- Taux d’abstention et de réponses citées calculés sur toutes les questions du groupe, échecs de génération inclus au dénominateur.
- Une citation vérifiée prouve seulement que les mots cités figurent dans le passage.
- « reference_numbers_in_answer » est un indicateur lexical (nombres de la réponse de référence présents), pas un jugement de justesse.

## Limites

- Corpus réduit : 8 sections réglementaires (11 versions) ; échantillons de test modestes, écarts de quelques points non significatifs.
- Questions documentaires générées par un LLM à partir des textes : plus faciles que des plaintes réelles.
- Le hit@5 documentaire est proche de 1 pour toutes les stratégies : ce benchmark discrimine peu ; la sélection est surtout décidée par le benchmark CFPB, lui-même à labels faibles.
- Labels CFPB faibles (catégorie -> paragraphe) ; date de réception utilisée comme date de référence.
- Une part importante des plaintes dépasse la fenêtre de 256 tokens du modèle dense (fin tronquée) ; la réécriture supprime cette troncature mais n’améliore pas les mesures sur le développement.
- Sur les plaintes hors périmètre, une partie des réponses ne s’abstient pas et cite des passages existants mais non applicables : la vérification des citations ne détecte pas ce cas.
- Le quota journalier Groq de `openai/gpt-oss-20b` a été épuisé pendant la génération des questions ; questions, réécritures et réponses ont toutes été produites avec `openai/gpt-oss-120b` (`reasoning_effort=low`).
- Mesures CPU sur une seule machine ; la latence Groq dépend d’un service externe.
