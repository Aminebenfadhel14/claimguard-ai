# Stratégie des données

Le CSV du cours a été téléchargé au commit fixé dans la matrice. SHA-256 et distributions complètes sont dans `reports/ticket_audit.json`. Aucun identifiant personnel brut n'est inclus dans le livrable.

## Résultats de l'audit

8 469 lignes, 17 colonnes, 0 ligne entièrement dupliquée, 392 descriptions répétées au-delà de la première occurrence. 5 700 résolutions, délais de résolution et notes de satisfaction sont absents. 2 819 dates/heures de première réponse sont absentes. Toutes les descriptions présentent au moins un marqueur détecté par l'heuristique (accolades/HTML/placeholders) ; ce comptage doit être interprété comme un signal de qualité et non comme 8 469 textes entièrement inutilisables.

Types de tickets : Technical issue 1 747 ; Billing inquiry 1 634 ; Cancellation request 1 695 ; Product inquiry 1 641 ; Refund request 1 752. Les classes ne sont pas des labels de conformité aux politiques NovaRetail.

## Usage permis dans ce projet

1. Auditer le CSV localement, sans transmettre le corpus à un LLM externe.
2. Retirer nom/email/âge/genre ; supprimer les occurrences des identifiants dans les autres champs ; masquer les motifs email et numéros à examiner. Cette expurgation heuristique n'est pas une anonymisation garantie.
3. Conserver les placeholders non résolus avec un drapeau. Remplacer `{product_purchased}` par la colonne produit serait possible dans une étape contrôlée, mais n'est pas nécessaire au benchmark et n'est pas appliqué silencieusement.
4. Grouper les descriptions identiques avant toute séparation train/validation/test de classification. Étendre ensuite à la quasi-duplication et à l'analyse des gabarits.
5. Utiliser les types/priorités comme labels de classification exploratoires, après revue ; jamais traiter la résolution comme preuve de conformité.
6. Pour une démonstration métier, sélectionner ultérieurement des tickets expurgés et relus. Le corpus actuel d'évaluation utilise uniquement des scénarios fictifs explicites.

## Corpus et vérité terrain

10 politiques, 11 versions documentaires, 30 sections courantes. RETURN-001 v1 est valable en 2025 et accorde 7 jours ; v2 est valable depuis le 1 janvier 2026 et accorde 14 jours. Les autres politiques commencent en 2026.

Les 76 questions de test comprennent 60 cas de section, 8 cas multithématiques/comparatifs/temporels/français et 8 cas sans réponse. Les annotations sont rédigées et contrôlées contre les textes par l'auteur du corpus, puis validées automatiquement pour existence des sections, versions et dates. Elles ne constituent pas une annotation indépendante par plusieurs humains ; cette revue reste à organiser avec l'équipe/professeur.

Le fine-tuning dispose de 60 requêtes d'entraînement et 30 de validation. Train = navigation vers une règle ; validation = résumé d'une règle ; test = scénarios de plainte et questions de fond. Les textes de requête et identifiants de scénarios sont disjoints. Le corpus documentaire est commun : il s'agit d'un test sur requêtes nouvelles concernant des politiques connues, pas d'une généralisation à de nouvelles politiques. Les gabarits train/validation restent proches, limite documentée.

Le test est gelé avant entraînement. Le choix du checkpoint utilise uniquement la perte de validation. Les cas sans réponse sont exclus des dénominateurs Recall/MRR et nécessitent une évaluation d'abstention distincte. Un score de retrieval n'est pas une mesure de faithfulness.
