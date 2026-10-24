# Contexte projet — à coller dans Claude pour continuer le rapport

## Projet
**ElectCI Agent** : agent text-to-SQL en langage naturel (français) sur les résultats des élections législatives ivoiriennes (205 circonscriptions, 930 candidats, 173 élus). Auteur : Beugre Niamba Okess. Dépôt : github.com/beugre483/sql_rag_agent. Application Streamlit déployée.

## Pipeline de données
1. Extraction des PDF officiels avec LlamaExtract (mode PER_TABLE_ROW, schéma Pydantic strict).
2. Nettoyage et normalisation (`clean_data.py`) : colonnes `*_norm` (minuscules, sans accents ni ponctuation).
3. Base SQLite : tables `circonscriptions` et `candidats` (clé étrangère `circonscription_id`), vues `vue_resultats_detailles`, `vue_elus_uniquement`, `vue_stats_regionales`.

## Architecture de l'agent (LangGraph, `AgentState` en TypedDict)
Nœuds : guardrail (mots-clés interdits) → classify_intent (validité : allowed / out_of_scope / policy_violation / ambiguous ; nature : simple_retrieval / ranking / aggregation / comparison ; type de graphique) → recherche_similaire (few-shot BM25, 12 exemples) → generate_sql → verify_sql (filtre de sécurité, allowlist de tables, `EXPLAIN QUERY PLAN`, 3 essais max) → execute_sql (connexion SQLite en lecture seule) → determine_chart_intent / generate_chart → generate_final_answer. Branches : generate_clarification, reponse_hors_sujet, reponse_politique.
Traçage : LangSmith. LLM : Mistral (passé de `mistral-small-latest` à `open-mistral-nemo` après des erreurs 429 de limite de débit sur le plan gratuit).

## Amélioration réalisée : profilage automatique de la base
Problème : le schéma du prompt SQL était écrit à la main (risque de désynchronisation, le LLM ne connaissait pas les valeurs réelles).
Solution : `src/database/profiler.py` introspecte la base (`sqlite_master`, `PRAGMA table_info`, `foreign_key_list`) et calcule par colonne : type (déduit des données pour les colonnes calculées des vues), % de NULL, nombre de valeurs distinctes, min/max des numériques, liste exhaustive des valeurs si ≤ 40 valeurs distinctes (sinon top 5), plus 2 lignes d'exemple. Résultat mis en cache (`data/processed/db_profile.json`, invalidé si la base est plus récente) et injecté via `{db_profile}` dans `GENERATE_SQL_SYSTEM` (~13 000 caractères).

## Problèmes de qualité de données révélés par le profilage
- Région `C` (troncature probable à l'ingestion).
- `HAUT- SASSANDRA` et `HAUT-SASSANDRA` : doublon de région.
- `BAGOUE` présente en base mais absente de la liste de régions des prompts.
- Variantes d'une même liste (« UNE COTE DIVOIRE EN PAIX… »).
- 41 valeurs distinctes pour `parti_politique` contre 42 pour `parti_politique_norm`.
Impact : `LIKE` et `GROUP BY` faussés.

## Limites actuelles
Pas de mémoire conversationnelle ; pas d'agent RAG ; raccourci codé en dur pour le comptage de sièges de 5 partis (`_build_direct_party_seat_count_query`) ; validation SQL par regex ; une erreur d'exécution SQL ne relance pas la génération ; pas de jeu d'évaluation ; schéma des prompts de classification encore écrit à la main.

## Pistes d'amélioration (par priorité)
1. Corriger les données dans `clean_data.py`.
2. Schema linking : résolution d'entités par correspondance floue (`rapidfuzz`) sur les valeurs réelles.
3. Jeu d'évaluation avec mesure d'execution accuracy.
4. Validation par AST (`sqlglot`), `LIMIT` automatique, timeout, réessai sur erreur d'exécution.
5. Few-shots étendus (50-100) avec embeddings.
6. Backoff exponentiel sur les erreurs 429.

## Ce que je veux de toi
Continuer la rédaction de mon rapport à partir de ce contexte. Demande-moi le plan imposé par mon école avant de commencer.
