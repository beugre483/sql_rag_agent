
from langgraph.types import Command
from langgraph.graph import END

from ..llm_client import LLMClient
from langsmith import traceable


from ..state import AgentState
@traceable(name="clarification")
def generate_clarification_node(state: AgentState) -> Command:
    """
    Utilise un LLM pour rédiger une question de clarification personnalisée.
    """
    # On instancie le client (Mistral)
    llm_client = LLMClient() 
    
    user_query = state.get("user_query")
    # On récupère le raisonnement de la classification précédente
    classification = state.get("classification")
    reasoning = classification.reasoning_summary if classification else "La requête est incomplète."
    
    prompt = f"""
    Tu es un assistant  electoral pour la population ivoirienne,tu ne reponds que pour les legislatives. L'utilisateur a posé une question, mais elle est incomplète ou ambiguë.
    
    QUESTION DE L'UTILISATEUR : "{user_query}"
    RAISON DU BLOCAGE : {reasoning}
    
    TACHE : 
    Rédige une réponse courte et polie pour :
    1. Reformuler ce que l'utilisateur cherche.
    2. Expliquer précisément ce qui manque (lieu, nom de candidat, etc.).
    3. Lui poser une question directe pour l'aider à préciser.
    
    RECO : Ne sois pas robotique. Utilise le contexte de sa question. Réponds en français
    ne donne que la reponse, ne soit pas strop bavard.
    """
    
    # Appel à Mistral
    response = llm_client.invoke(prompt)
    
    return Command(
        update={"final_answer": response.content},
        goto=END
    )