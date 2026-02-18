from langgraph.graph import Command
from typing import Dict, Any
from ..state import AgentState
from langsmith import traceable

@traceable(name="guardrail_security")
def guardrail_node(state: AgentState) -> Command:
    """s
    Nœud de garde-fou. 
    Vérifie les mots interdits et oriente le flux via Command.
    """
    mots_interdits = [
        # Commandes SQL et actions dangereuses
        "supprime", "efface", "supprimer", "effacer",
        "modifie", "modifier", "change", "changer",
        "insère", "insérer", "ajoute", "ajouter",
        "crée", "créer", "créez",
        "altère", "altérer", "modifie la structure",
        "vide la table", "truncate", "drop",
        "accorde", "accorder", "révoque", "révoquer",
        "exécute", "exécuter",
        
        # Intentions dangereuses
        "supprime tout", "tout supprimer",
        "modifie les données", "change les données",
        "pirate", "hack", "accès admin", "administrateur",
        "mot de passe", "password", "credentials", "prompt",
        "ignore", "enlève",

        # Commandes système
        "rm ", "rm -rf", "format", "shutdown", "restart"
    ]
    
    user_query = state.get("user_query", "").lower()
    
    # Si pas de requête utilisateur, on passe à la classification
    if not user_query:
        return Command(goto="classify_intent")
    
    # Vérification des mots interdits
    for mot in mots_interdits:
        if mot in user_query:
            print(f"[Guardrail] Mot interdit détecté : {mot}")
            return Command(
                update={
                    "errors": state.get("errors", []) + [f"Mot-clé interdit détecté: '{mot}'"],
                    "final_answer": (
                        "Désolé, votre requête contient des opérations non autorisées sur la base de données."
                    )
                },
                goto="reponse_politique"
            )

    return Command(goto="classify_intent")
