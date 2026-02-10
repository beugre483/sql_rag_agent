# src/agent/nodes/verify_sql.py
import sqlite3
import re
from typing import Literal
from langgraph.types import Command
from pathlib import Path
from ..state import AgentState
from langsmith import traceable


current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent.parent
DB_PATH = project_root / "data" / "processed" / "elections.db"

ALLOWED_OBJECTS = [
    "vue_resultats_detailles", 
    "vue_elus_uniquement", 
    "vue_stats_regionales",
    "circonscriptions", 
    "candidats"
]

@traceable(name="sql_verification")
def verify_sql_node(state: AgentState) -> Command[Literal["execute_sql", "generate_sql", "reponse_hors_sujet"]]:
    query = state['sql_query']
    
    if not query:
        return Command(
            update={"errors": ["Aucune requête SQL n'a été générée."]},
            goto="generate_sql"
        )

    print(f"\n[Verify SQL] Analyse de : {query}")

    # 1. FILTRE DE SÉCURITÉ
    forbidden_pattern = r"\b(DROP|DELETE|INSERT|UPDATE|ALTER|TRUNCATE|GRANT|REVOKE|PRAGMA|VACUUM)\b"
    if re.search(forbidden_pattern, query, re.IGNORECASE):
        msg = "SÉCURITÉ : Tentative de modification de la base interdite (DROP/DELETE...)."
        print(f"  ✗ {msg}")
        return _gerer_erreur(state, msg)

    # 2. VÉRIFICATION DES TABLES
    tables_found = re.findall(r'\b(?:FROM|JOIN)\s+([a-zA-Z0-9_]+)', query, re.IGNORECASE)
    
    for table in tables_found:
        clean_table = table.strip('"').strip("'").strip().lower()
        
        if clean_table not in [t.lower() for t in ALLOWED_OBJECTS] and not clean_table.startswith("("):
            if clean_table.upper() not in ["SELECT", "WHERE", "VALUES", "UNNEST"]:
                msg = f"HALLUCINATION : La table '{clean_table}' n'existe pas."
                print(f"   {msg}")
                return _gerer_erreur(state, msg)

    # 3. VALIDATION SYNTAXIQUE
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(f"EXPLAIN QUERY PLAN {query}")
            
        print("   Syntaxe et Schéma valides.")
        return Command(goto="execute_sql")

    except sqlite3.Error as e:
        error_msg = f"ERREUR SYNTAXE SQLITE : {str(e)}"
        print(f"   {error_msg}")
        return _gerer_erreur(state, error_msg)


def _gerer_erreur(state: AgentState, new_error: str) -> Command[Literal["generate_sql", "reponse_hors_sujet"]]:
    """
    Gère la logique de retry
    """
    total_errors = len(state['errors']) + 1
    
    print(f"  ℹ Nombre d'erreurs: {total_errors}")
    
    # STOP : Trop d'essais
    if total_errors >= 3:
        print("   Trop d'échecs successifs. Abandon.")
        return Command(
            update={
                "errors": [new_error],  # Ajoute cette erreur
                "final_answer": "Je n'ai pas réussi à générer une requête valide après plusieurs essais."
            },
            goto="reponse_hors_sujet"
        )
    
    return Command(
        update={
            "errors": [new_error],  
            "sql_query": None
        },
        goto="generate_sql"
    )
