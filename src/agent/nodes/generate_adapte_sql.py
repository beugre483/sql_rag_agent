# src/agent/nodes/generate_sql.py

from langgraph.types import Command
from langchain_core.prompts import ChatPromptTemplate
from typing import Literal
import re

from ..state import AgentState
from ..llm_client import LLMClient
from src.ingestion.clean_data import ElectionDataCleaner
from langsmith import traceable


# Initialisation du client LLM
llm_client = LLMClient()
@traceable(name="sql_generation")
def generate_sql_query_node(state: AgentState) -> Command[Literal["verify_sql"]]:
    """
    Nœud de génération SQL avec typage strict des colonnes pour SQLite.
    """

    # --- 1. RÉCUPÉRATION DES DONNÉES ---
    user_query = state.get('user_query', "")
    errors = state.get('errors', [])
    classification = state.get('classification')
    similar_context = state.get('similar_examples_context', "")

    # --- 2. NORMALISATION ---
    normalized_query = ""
    try:
        normalized_query = ElectionDataCleaner.normalize_text(user_query)
    except Exception:
        normalized_query = user_query.lower().strip()

    # --- 3. FEEDBACK D'ERREUR ---
    error_feedback = ""
    if errors:
        last_error = errors[-1]
        error_feedback = f"\n ERREUR PRÉCÉDENTE À CORRIGER : {last_error}\n"

    # --- 4. NATURE DE LA REQUÊTE ---
    query_nature = "simple_retrieval"
    if classification and hasattr(classification, 'query_nature'):
        query_nature = classification.query_nature

    # --- 5. CONSTRUCTION DU PROMPT AVEC TYPES DE COLONNES ---
    system_prompt = f"""
TU ES UN EXPERT SQLITE (DIALECTE SQLITE).
Génère une requête SQL brute basée strictement sur le schéma et les types ci-dessous.

--- SCHÉMA DÉTAILLÉ DES VUES (TYPES SQLITE) ---

1. VUE 'vue_resultats_detailles' (Tous les scores par candidat) :
   - region_nom (TEXT) : Nom officiel de la région.
   - region_nom_norm (TEXT) : Nom normalisé (minuscule, sans accent). <--- FILTRE ICI
   - nom_circonscription (TEXT) : Nom officiel de la circonscription.
   - nom_circonscription_norm (TEXT) : Nom normalisé. <--- FILTRE ICI
   - taux_participation (REAL) : Valeur décimale (ex: 45.5).
   - parti_politique (TEXT) : Sigle ou nom du parti.
   - parti_politique_norm (TEXT) : Parti normalisé.
   - nom_liste_candidat (TEXT) : Nom de la tête de liste.
   - nom_liste_candidat_norm (TEXT) : Nom candidat normalisé.
   - score_voix (INTEGER) : Nombre entier de voix.
   - pourcentage_voix (REAL) : Valeur décimale.
   - est_elu (INTEGER) : 1 pour élu, 0 pour non élu.

2. VUE 'vue_elus_uniquement' (Uniquement les vainqueurs) :
   - region_nom (TEXT), region_nom_norm (TEXT)
   - nom_circonscription (TEXT), nom_circonscription_norm (TEXT)
   - parti_politique (TEXT), parti_politique_norm (TEXT)
   - nom_liste_candidat (TEXT), nom_liste_candidat_norm (TEXT)
   - score_voix (INTEGER)

3. VUE 'vue_stats_regionales' (Agrégations participation) :
   - region_nom (TEXT), region_nom_norm (TEXT)
   - total_inscrits (INTEGER) : Somme des inscrits.
   - total_votants (INTEGER) : Somme des votants.
   - total_exprimes (INTEGER) : Somme des suffrages exprimés.
   - taux_participation_moyen (REAL) : Moyenne calculée en %.

--- CONSIGNES DE SYNTAXE ---
- TEXT : Utilise 'guillemets simples' et LIKE avec % (ex: region_nom_norm LIKE '%abidjan%').
- INTEGER/REAL : Pas de guillemets (ex: score_voix > 1000).
- LIMIT : Ajoute 'LIMIT 10' par défaut.
- SQL PUR : Pas de texte explicatif, pas de blocs Markdown (```).
- RÈGLES DE RECHERECHE INTELLIGENTE (IMPORTANT) ---
De nombreuses villes ont deux circonscriptions : une 'COMMUNE' et une 'SOUS-PRÉFECTURE'.

1. AMBIGUÏTÉ : Si l'utilisateur dit juste "Agboville" ou "Divo", cherche les deux avec :
   WHERE nom_circonscription_norm LIKE '%agboville%'
   
2. PRÉCISION COMMUNE : Si l'utilisateur dit "Ville", "Commune" ou "Cne", cherche :
   WHERE nom_circonscription_norm LIKE '%agboville%commune%'
   
3. PRÉCISION SOUS-PRÉFECTURE : Si l'utilisateur dit "S/P", "SP", "Village" ou "Sous-préfecture", cherche :
   WHERE nom_circonscription_norm LIKE '%agboville%prefecture%'
   
"N'utilise jamais l'opérateur '=' pour les noms de lieux ou de personnes. Utilise toujours l'opérateur 'LIKE' avec des jokers '%' de chaque côté (ex: LIKE '%nom%') sur les colonnes suffixées par '_norm
1. SUPPRESSION DES POINTS : "R.H.D.P." ou  devient "rhdp" ou "rdr". Ne jamais inclure de points dans le SQL.
2. SUPPRESSION DES TIRETS : "PPA-CI" ou "PDCI-RDA" devient "ppa-ci" ou "pdci-rda".
3. MINUSCULES : Transforme tout en minuscules (ex: "Abidjan" -> "abidjan").
Si une question porte sur une ville ou une circonscription sans précision (ex: juste 'Tiapoum' ou 'Agboville'), sélectionne TOUJOURS la colonne nom_circonscription dans ton SQL. Cela permettra de distinguer les résultats si plusieurs entités existent (Commune, Sous-préfecture, etc.). Utilise LIKE '%terme%' pour attraper toutes les variantes
{error_feedback}

CONTEXTE DE RÉFÉRENCE :
{similar_context if similar_context else "Aucun exemple, suis le schéma à la lettre."}
"""

    human_message = f"""
QUESTION UTILISATEUR : "{user_query}"
VALEUR DE RECHERCHE NETTOYÉE : "{normalized_query}"
TYPE DE REQUÊTE : {query_nature}

Requête SQLite :
"""

    # --- 6. EXÉCUTION ---
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", human_message)
    ])

    try:
        formatted_prompt = prompt.format()
        response = llm_client.invoke(formatted_prompt)

        # Extraction propre du contenu (gestion objet vs string)
        if isinstance(response, str):
            raw_sql = response.strip()
        elif hasattr(response, 'content'):
            raw_sql = response.content.strip()
        else:
            raw_sql = str(response).strip()
        
        clean_sql = _clean_sql_output(raw_sql)
        print(f"\n[Generate SQL] SQL produit : {clean_sql}")

        return Command(
            update={"sql_query": clean_sql},
            goto="verify_sql"
        )

    except Exception as e:
        print(f"  ✗ [Error] : {str(e)}")
        return Command(
            update={"sql_query": None, "errors": [str(e)]},
            goto="verify_sql"
        )

def _clean_sql_output(text: str) -> str:
    """Nettoie le résultat pour ne garder que le SELECT."""
    # Enlever les blocs markdown
    text = re.sub(r"```(?:sql)?", "", text, flags=re.IGNORECASE)
    text = text.replace("```", "").strip()
    
    # Extraire à partir de SELECT ou WITH
    match = re.search(r"\b(SELECT|WITH)\b", text, re.IGNORECASE)
    if match:
        text = text[match.start():]
    
    # Couper au premier point-virgule s'il y en a un
    return text.split(';')[0].strip()