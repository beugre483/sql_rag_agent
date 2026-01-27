
from langgraph.graph import StateGraph
from typing import Dict, Any
from ..state import AgentState

def guardrail_node(state: AgentState) -> AgentState:
    """Nœud de garde-fou pour détecter les requêtes dangereuses."""
    
    mots_interdits = [
        # Commandes SQL en français
        "supprime", "efface", "supprimer", "effacer",
        "modifie", "modifier", "change", "changer",
        "insère", "insérer", "ajoute", "ajouter",
        "crée", "créer", "créez",
        "altère", "altérer", "modifie la structure",
        "vide la table", "truncate",
        "accorde", "accorder", "révoque", "révoquer",
        "exécute", "exécuter",
        
        # Intentions dangereuses
        "supprime tout", "tout supprimer",
        "modifie les données", "change les données",
        "pirate", "hack", "accès admin", "administrateur",
        "mot de passe", "password", "credentials",
        
        # Commandes système
        "rm ", "rm -rf", "format", "shutdown", "restart"
    ]
    
    # Vérification insensible à la casse
    query_lower = state['user_query'].lower()
    
    for mot in mots_interdits:
        if mot in query_lower:
            state['errors'].append(f"Mot-clé interdit détecté: '{mot}'")
            state['final_answer'] = (
                "Désolé, votre requête semble contenir des opérations non autorisées. "
                "Je ne peux répondre qu'à des questions d'analyse et de consultation des données."
            )
            return state
    
    # Si aucun mot interdit n'est trouvé, on continue
    return state