# Archive — rapports v2 (historique)

Rapports produits le 17 novembre 2026 par l'architecture v2 du projet : catalogue SQLite, index Qdrant en
mémoire reconstruit au démarrage, RRF maison et profil fine-tuné. Cette architecture a été retirée en v3.

Ils ne sont **pas comparables** aux rapports v3 (`reports/v3/`), pour quatre raisons :

- unité de mesure : la section `(policy, version, paragraphe)` dédupliquée, contre le chunk Qdrant en v3 ;
- chaîne différente : fusion RRF maison, déduplication par section avant reranking, modèle fine-tuné ;
- métriques @10 calculées sur des sections, contre @5 sur des chunks ;
- pas de benchmark documentaire.

Ils restent ici à titre de trace et ne décrivent pas l'architecture active.
