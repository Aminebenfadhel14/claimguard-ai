# Analyse du cours et correspondance ClaimGuard AI

Source inspectée : [Nadjib23/AI-Engineering-Course](https://github.com/Nadjib23/AI-Engineering-Course/tree/2b0c4d78f992dce0a6349121e543ff8dddce94d4/labs), commit `2b0c4d78f992dce0a6349121e543ff8dddce94d4`. Les 29 fichiers Python du dépôt ont été lus. L'inventaire JSON conserve chemins, imports, longueurs et SHA-256. Une importation seule n'est pas une preuve d'exécution.

Tous les chemins ci-dessous sont relatifs à `labs/`. « Prévu » indique une utilisation future, pas une fonction validée.

| Module | Fichier réel | Technique constatée dans le code | Application ClaimGuard |
|---|---|---|---|
| 01 | `01-prompt-engineering/01-chatbot.py` | SDK Groq, messages système/utilisateur/assistant, historique manuel | Fournisseur Groq configurable, secret `.env` |
| 01 | `01-prompt-engineering/02-langchain_chatbot.py` | ChatGroq, HumanMessage, AIMessage, SystemMessage | Adaptateur LLM LangChain |
| 01 | `01-prompt-engineering/03-langchain_prompt_template.py` | ChatPromptTemplate.from_template, variables, composition `prompt \| llm` | Prompts de requête et génération |
| 01 | `01-prompt-engineering/04-langchain_chat_prompt_template.py` | from_messages, MessagesPlaceholder, historique | Séparation instructions/données ; mémoire métier prévue |
| 02 | `02-chains-and-output-parsing/05-langchain_chains.py` | RunnableParallel, RunnableLambda, RunnableBranch, StrOutputParser | Composition LCEL ; branche d'abstention et normalisation. Recherche séquentielle initiale pour traces déterministes |
| 02 | `02-chains-and-output-parsing/06-langchain_output_parsers.py` | StrOutputParser, PydanticOutputParser, with_structured_output, schéma QuizQuestion | GeneratedAnswer et Citation Pydantic. JsonOutputParser est importé mais pas utilisé |
| 03 | `03-session-tools-and-agents/07-langchain_memory.py` | InMemoryChatMessageHistory, RunnableWithMessageHistory, session_id, trim_messages | Isolation des sessions prévue pour Level 2 ; stockage mémoire du lab insuffisant en production |
| 03 | `03-session-tools-and-agents/08-langchain_tools.py` | @tool, bind_tools, schémas JSON, dispatch explicite | Outils contrôlés ; distinction avec MCP |
| 03 | `03-session-tools-and-agents/08bis-langchain_tools_problems.py` | tool_choice auto/any/nom, arguments listes | Aucun outil de décision irréversible confié au LLM |
| 03 | `03-session-tools-and-agents/09-langchain_tool_agent.py` | ToolMessage avec tool_call_id, boucle bornée, outils inconnus et erreurs | Orchestration bornée prévue ; serveur MCP séparé |
| 04 | `04-rag/10-init_qdrant.py` | PyPDFLoader, splitter 1000/100, all-MiniLM-L6-v2, QdrantVectorStore | ingestion/pipeline.py, indexing/qdrant.py |
| 04 | `04-rag/10bis-init_qdrant_with_multiple_files.py` | os.walk, ingestion multi-PDF | Corpus multi-documents avec sidecars validés |
| 04 | `04-rag/11-qdrant_retreival.py` | Chargement collection, similarity_search, contexte, génération | Recherche dense avec scores et sources conservées |
| 04 | `04-rag/12-rag_inside_chain.py` | retriever, RunnablePassthrough, LCEL RAG | Chaîne prompts/rag.py et moteur partagé |
| 04 | `04-rag/13-rag_query_rewriting.py` | Réécriture LLM avant retrieval | rewrite(), désactivable, texte original conservé |
| 04 | `04-rag/14-adding_metadata.py` | SHA-256, scroll par hash, source_file | Déduplication et catalogue SQLite immuable |
| 04 | `04-rag/14-dealing_with_metadata.py` | Filter, FieldCondition, MatchValue sur source | Filtres métier validés côté serveur |
| 04 | `04-rag/14bis-retreiving_with_metadata.py` | MatchAny exécuté ; exemples Range, must/should/must_not principalement commentés | Date d'effet, catégorie, accès ; tests exécutés dans ClaimGuard |
| 04 | `04-rag/15-using_bm25.py` | FastEmbedSparse Qdrant/bm25, index dense+sparse, mode HYBRID | Sparse Qdrant avec IDF appliqué une seule fois |
| 04 | `04-rag/15bis-dense_vs_sparse_vs_hybrid.py` | RetrievalMode.HYBRID, modes DENSE/SPARSE cités ; pas de benchmark automatisé | E1/E2/E3 mesurés séparément |
| 04 | `04-rag/16-including_reranking.py` | CrossEncoder mmarco-mMiniLMv2-L12-H384-v1, paires query/passage, tri | E4/E5, cinq passages pour génération, dix pour métriques |
| 99 | `99-exercices/ticket_categorisation.py` | CSV, Pydantic sentiment/department/priority, structured output | Audit réel du CSV ; classification métier Level 2 prévue |
| 99 | `99-exercices/invoices_extractor/src/ingesting.py` | PDF, hash, hybrid, extraction métadonnées | Métadonnées de politique explicites et validées sans invention par LLM |
| 99 | `99-exercices/invoices_extractor/src/metadata_extractor.py` | Schéma InvoiceMetadata et extraction structurée | Schéma PolicyMetadata, extraction déclarative contrôlée |
| 99 | `99-exercices/invoices_extractor/src/chat.py` | RAG hybride factures ; filtre invoice_nbr commenté | Réutilisation du moteur et des filtres |
| 99 | `99-exercices/invoices_extractor/app.py` | Streamlit, chats, filtres, boutons ; réponse placeholder | Interface métier prévue, sans présenter ce lab comme application achevée |
| 99 | `99-exercices/rag_with_sources.py` | RagAnswer(answer,sources), structured output | Validation des IDs et des citations exactes |
| 99 | `99-exercices/quiz_generator.py` | Génération structurée, liste d'historique | Inspiration schémas et questions annotées ; questions du projet rédigées explicitement |
| 99 | `99-exercices/quiz_generator_save_tool.py` | Retry borné, outil save_quiz, bind_tools | Tolérance aux erreurs ; aucun envoi client automatique |

## Corrections et limites constatées

- Le fichier `16-including_reranking.py` transforme les documents en chaînes puis tente de lire `.page_content` sur ces chaînes. ClaimGuard conserve les objets Chunk jusqu'au rendu.
- `14bis` et `15bis` importent `Range` depuis `param`, alors que le filtre Qdrant utilise `qdrant_client.models.Range` ; certains exemples sont seulement des commentaires.
- L'application facture importe des fonctions absentes des fichiers inspectés et affiche une réponse placeholder. Elle n'est pas une preuve de système terminé.
- `requirements.txt` du cours n'épingle pas les versions et omet notamment FastEmbed/Streamlit. Les dépendances du projet sont testées puis verrouillées séparément.
- Aucun fine-tuning, calcul Recall/MRR ou serveur MCP n'a été trouvé dans les fichiers inspectés. Ce sont des exigences supplémentaires du cahier des charges, pas des capacités attribuées au dépôt.
- RRF n'est pas écrit explicitement dans les labs ; l'hybride délègue à l'intégration Qdrant. Ici les deux classements sont demandés séparément puis fusionnés localement à k=60, sans fusion Qdrant supplémentaire.
