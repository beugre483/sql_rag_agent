# src/agent/graph.py

from langgraph.graph import StateGraph, END
from langgraph.types import Command
from .state import AgentState

# Importation de tous les nœuds
from src.agent.nodes.classify_intent_sql import (
    classify_intent_node, 
    reponse_hors_sujet_node, 
    reponse_politique_node
)
from src.agent.nodes.retrieve_similar_sql import retrieve_similar_examples
from src.agent.nodes.generate_adapte_sql import generate_sql_query_node
from src.agent.nodes.verify_sql import verify_sql_node
from src.agent.nodes.execute_sql import execute_sql_node
from src.agent.nodes.generate_chart_sql import (
    determine_chart_intent_node, 
    generate_chart_node
)
from src.agent.nodes.generate_final_answer_sql import generate_final_answer_node

def guardrail_node(state: AgentState) -> Command:
    """
    Nœud de garde-fou. 
    Vérifie les mots interdits et oriente le flux via Command.
    """
    mots_interdits = [
        "supprime", "efface", "supprimer", "effacer",
        "modifie", "modifier", "change", "changer",
        "insère", "insérer", "ajoute", "ajouter",
        "crée", "créer", "altère", "truncate", "drop",
        "rm ", "rm -rf", "pirate", "hack"
    ]
    
    user_query = state.get("user_query", "").lower()
    
    if not user_query:
        return Command(goto="classify_intent")
    
    for mot in mots_interdits:
        if mot in user_query:
            print(f" [Guardrail] Mot interdit détecté : {mot}")
            return Command(
                update={
                    "errors": [f"Mot-clé interdit détecté: '{mot}'"],
                    "final_answer": "Désolé, votre requête contient des opérations non autorisées sur la base de données."
                },
                goto="reponse_politique"
            )
    
    # Si tout est OK, on passe à la classification
    return Command(goto="classify_intent")

def build_agent_graph():
    """
    Construit le graphe de l'agent.
    Puisque chaque nœud renvoie un objet Command(goto="..."), 
    nous n'avons plus besoin de définir d'edges ou de conditional_edges ici.
    """
    
    # Initialisation du graphe avec la structure AgentState
    builder = StateGraph(AgentState)

    # --- 1. AJOUT DES NŒUDS ---
    builder.add_node("guardrail", guardrail_node)
    builder.add_node("classify_intent", classify_intent_node)
    builder.add_node("recherche_similaire", retrieve_similar_examples)
    builder.add_node("generate_sql", generate_sql_query_node)
    builder.add_node("verify_sql", verify_sql_node)
    builder.add_node("execute_sql", execute_sql_node)
    builder.add_node("determine_chart_intent", determine_chart_intent_node)
    builder.add_node("generate_chart", generate_chart_node)
    builder.add_node("generate_final_answer", generate_final_answer_node)
    builder.add_node("reponse_hors_sujet", reponse_hors_sujet_node)
    builder.add_node("reponse_politique", reponse_politique_node)

    # --- 2. POINT D'ENTRÉE ---
    builder.set_entry_point("guardrail")


    return builder.compile()