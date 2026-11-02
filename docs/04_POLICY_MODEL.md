# Modèle documentaire NovaRetail

Chaque document `POLICY-ID_version.md|txt|pdf` possède un sidecar portant le suffixe supplémentaire `.json`.

| Champ | Règle |
|---|---|
| document_id | Identité documentaire, ex. RETURN-001-V2 |
| policy_id | Identité métier stable, ex. RETURN-001 |
| title/category/department | Libellé, catégorie, responsable |
| version | Chaîne numérique majeure.mineure ; immuable |
| effective_date | Date inclusive de prise d'effet |
| effective_until | Date exclusive de fin, ou null |
| language | en ou fr |
| access_level | public, internal, restricted |
| source | Mention explicite du caractère fictif académique |

Le pipeline ajoute file_hash SHA-256, chunk_id SHA-256, section, page physique à partir de 1, source_file. Les titres de section ont la forme `## 4.2 — Defective product exchange`. Les paragraphes et négations sont préservés. Les conditions et exceptions restent dans le texte source ; le futur Level 2 les représentera par règles contrôlées : variable, opérateur, valeur, préconditions, exceptions, référence source.

Une référence stable de benchmark a la forme `RETURN-001@2.0#4.2`. Les réponses ajoutent le chunk précis, la page et l'extrait. Les empreintes identifient les octets exacts. Les originaux sont conservés dans `var/sources/` pour la durée de la démonstration.

Une version nouvelle doit avoir son propre identifiant, son contenu et un intervalle non chevauchant. L'exemple inclus déclare d'emblée la fin de v1. Pour une politique déjà publiée avec une fin ouverte, une migration administrative auditée de l'intervalle serait nécessaire ; le prototype refuse le chevauchement au lieu d'écraser silencieusement l'historique. La suppression physique n'est pas exposée ; seule la désactivation auditée est implémentée.
