# Données réelles

## Sources

| Données | Source officielle | Licence | Rôle |
|---|---|---|---|
| Plaintes | CFPB Consumer Complaint Database, archive officielle des narratifs (FOIA Reading Room) | Domaine public US (17 U.S.C. §105) | Benchmark CFPB (développement et test) |
| Catégories des plaintes | API publique de la CFPB (produit, issue, sous-issue) | Domaine public | Labels, jointure par `complaint_id` si l’archive ne les contient pas |
| Règlements | eCFR, Office of the Federal Register (API versioner) | Domaine public | XML chargés en Documents LangChain et indexés dans Qdrant, avec dates de version |

Les narratifs sont rédigés par les consommateurs, publiés avec leur consentement et expurgés par la CFPB (`XXXX`). Ils ne sont pas vérifiés : ClaimGuard les traite comme des allégations.

## Règlements retenus (8 sections, 12 CFR)

| Identifiant | Section | Sujet | Famille |
|---|---|---|---|
| REGZ-012 | 1026.12 | Dispositions spéciales cartes de crédit (usage non autorisé, litiges) | credit_card |
| REGZ-013 | 1026.13 | Résolution des erreurs de facturation | credit_card |
| REGE-006 | 1005.6 | Responsabilité du consommateur, transferts non autorisés | bank_account |
| REGE-011 | 1005.11 | Procédure de résolution des erreurs (transferts électroniques) | bank_account |
| REGF-034 | 1006.34 | Avis de validation de dette | debt_collection |
| REGF-038 | 1006.38 | Contestations et informations sur le créancier d’origine | debt_collection |
| REGV-042 | 1022.42 | Exactitude des informations fournies aux bureaux de crédit | credit_reporting |
| REGV-043 | 1022.43 | Contestations directes auprès du fournisseur | credit_reporting |

Chaque section est découpée en paragraphes de premier niveau (a), (b), (c)… Référence interne : `REGZ-013@2.0#a` = 12 CFR 1026.13(a), version 2.0. Pour 1026.12, 1026.13 et 1005.11, deux versions officielles successives sont conservées (avant et après la réforme des comptes prépayés du 1er avril 2019). Chaque chunk porte `version_date` / `valid_until` (dates de version eCFR) ; un filtre de métadonnées Qdrant (`metadata.valid_from_int`, `metadata.valid_until_int`, `Range` comme dans le lab 14bis) sélectionne la version en vigueur à la date de référence. 2017-01-01 est la plus ancienne date proposée par le versioner eCFR : elle signifie « en vigueur au moins depuis », pas une date d’entrée en vigueur.

## Sélection des plaintes (déterministe)

- **Split temporel** : développement (fichiers `training/train.jsonl` + `training/validation.jsonl`, noms hérités de la v2) = plaintes reçues en novembre–décembre 2024 ; test = janvier–février 2025. Aucune plainte commune (contrôlé par le code).
- **Date de référence** : la seule date disponible est `date_received` (réception par la CFPB), pas la date des faits. Elle sert uniquement à choisir la version du règlement en vigueur ; depuis 2021 aucune des sections n’a changé, l’approximation n’a donc pas d’effet sur ce jeu.
- Seules les plaintes avec narratif de 300 à 3 500 caractères sont candidates ; les narratifs identiques sont dédoublonnés.
- Ordre de sélection = empreinte SHA-256 de `graine | complaint_id` : aucun choix manuel, résultat identique quel que soit l’ordre du fichier.
- Quotas par règle : 20 en test, 8 en entraînement, 4 en validation ; 7 par catégorie hors périmètre en test.

## Règles d’annotation (`configs/cfpb.json`)

| Règle | Catégorie officielle CFPB | Paragraphes attendus |
|---|---|---|
| R1 | Credit card › Problem with a purchase shown on your statement › …isn’t resolving a dispute | 1026.13(a), (c), (f) |
| R2 | Credit card › … › Card was charged for something you did not purchase | 1026.12(b), 1026.13(a) |
| R3 | Checking or savings account › …charging your account › Transaction was not authorized | 1005.6(b), 1005.11(a), (c) |
| R4 | Money transfer… › Unauthorized transactions or other transaction problem | 1005.11(a), (c), 1005.6(b) |
| R5 | Debt collection › Attempts to collect debt not owed › Debt is not yours | 1006.38(d) |
| R6 | Debt collection › Written notification about debt › Didn’t receive enough information to verify debt | 1006.34(c), 1006.38(d) |
| R7 | Debt collection › Written notification about debt › Didn’t receive notice of right to dispute | 1006.34(a), (c) |
| R8 | Credit card › Problem with a company’s investigation… › Their investigation did not fix an error | 1022.43(a), (e) |
| R9 | Credit card › Incorrect information on your report › Account status incorrect | 1022.42(a), 1022.43(a) |
| U1–U3 | Mortgage (paiement), Student loan (gestionnaire), découverts | aucun : hors périmètre |

La justification de chaque règle figure dans le champ `rationale`. Ces labels sont une correspondance documentée, pas une revue juridique : une plainte peut aussi relever de paragraphes non annotés. C’est la principale limite à mentionner.

## Particularités rencontrées à l'import

- **eCFR refuse les requêtes Python** (HTTP 406, protection anti-robots) mais accepte un navigateur. Chaque version est donc enregistrée depuis le navigateur sous forme d'un fichier XML officiel, un par version : `data/cfpb/raw/ecfr/<section>_<date>.xml` (ex. `1026.13_2019-04-01.xml`, téléchargé depuis `https://www.ecfr.gov/api/versioner/v1/full/2019-04-01/title-12.xml?part=1026&section=1026.13`). L'importeur utilise ces fichiers s'ils existent, sinon il interroge l'API ; si elle refuse, il affiche la liste exacte des liens à enregistrer.
- **Pourquoi l'XML de l'API et pas un copier-coller de la page web** : l'XML garde la structure officielle (paragraphes (a), (b)…, titres, ligne « Source »), une date de version exacte et un fichier vérifiable par empreinte SHA-256 ; un copier-coller perd cette structure, peut introduire des erreurs et ne se refait pas à l'identique.
- **Plaintes modèles déposées plusieurs fois** : un même texte peut apparaître en 2024 et en 2025 (lettres de contestation types). Tout texte présent dans le test est retiré de l'entraînement et de la validation (2 cas), puis un contrôle de fuite bloque le benchmark s'il en reste.
- Les archives officielles des narratifs (`CCDB_Export_…zip`, 52,6 Mo et 75,5 Mo) contiennent toutes les colonnes : aucune jointure avec l'API n'a été nécessaire.

## Reproductibilité

`python -m claimguard import-cfpb` télécharge les sources et écrit `data/cfpb/raw/manifest.json` (URL, date, SHA-256 de chaque fichier). `--build-only` reconstruit les plaintes annotées hors ligne à partir de cet instantané. Les XML sont lus directement par `python -m claimguard ingest` (empreinte vérifiée contre le manifeste). `data/cfpb/provenance.json` résume les effectifs et les empreintes.
