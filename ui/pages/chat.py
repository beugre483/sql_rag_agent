import streamlit as st
from pathlib import Path
import sys
import pandas as pd

# Ajouter le dossier racine au path pour les imports
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.agent.graph import build_agent_graph


def chat_page():
    """
    Page de chat avec l'agent SQL électoral
    """
    st.header("Assistant Electoral IA")
    st.markdown("Posez vos questions sur les données électorales")
    
    # Initialiser l'agent (avec cache pour éviter de reconstruire à chaque interaction)
    @st.cache_resource
    def get_agent():
        return build_agent_graph()
    
    agent = get_agent()
    
    # Initialiser l'historique de conversation dans la session
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Afficher l'historique des messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            # Afficher le graphique si présent
            if message.get("chart"):
                st.plotly_chart(message["chart"], use_container_width=True)
            
            # Afficher les données SQL si présentes
            if message.get("sql_results") is not None:
                with st.expander("Voir les données brutes"):
                    # Convertir en DataFrame si ce n'est pas déjà fait
                    if isinstance(message["sql_results"], list):
                        df = pd.DataFrame(message["sql_results"])
                    else:
                        df = message["sql_results"]
                    st.dataframe(df, use_container_width=True)
    
    # Input utilisateur
    if prompt := st.chat_input("Posez votre question ici..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("Analyse en cours..."):
                try:
                    initial_state = {
    "user_query": prompt,
    "classification": None,
    "sql_query": None,
    "sql_results": [],
    "chart_generated": False, # On l'initialise ici !
    "errors": [],
    "final_answer": None
}
                    
                    # Invoquer l'agent
                    result = agent.invoke(initial_state)
                    
                    final_answer = result.get("final_answer", "Désolé, je n'ai pas pu générer une réponse.")
                    sql_results = result.get("sql_results")
                    chart_data = result.get("chart_data")
                    
                    st.markdown(final_answer)
                    
                    chart = None
                    if chart_data:
                        # Si chart_data contient déjà une figure Plotly
                        if hasattr(chart_data, '__call__') or hasattr(chart_data, 'show'):
                            chart = chart_data
                        else:
                            # Sinon, créer le graphique ici selon vos données
                            pass
                    
                    # Afficher le graphique si disponible
                    if chart:
                        st.plotly_chart(chart, use_container_width=True)
                    
                    # Afficher les données SQL si disponibles
                    if sql_results is not None:
                        with st.expander("Voir les données brutes"):
                            # Convertir en DataFrame si c'est une liste de dict
                            if isinstance(sql_results, list):
                                df = pd.DataFrame(sql_results)
                            elif isinstance(sql_results, pd.DataFrame):
                                df = sql_results
                            else:
                                df = pd.DataFrame([sql_results])
                            
                            st.dataframe(df, use_container_width=True)
                    
                    # Ajouter la réponse à l'historique
                    message_data = {
                        "role": "assistant",
                        "content": final_answer,
                    }
                    
                    # Ajouter les données optionnelles
                    if chart:
                        message_data["chart"] = chart
                    if sql_results is not None:
                        message_data["sql_results"] = sql_results
                    
                    st.session_state.messages.append(message_data)
                    
                except Exception as e:
                    import traceback
                    st.error(f"Erreur lors du traitement de votre question : {str(e)}")
                    st.error(f"Détails: {traceback.format_exc()}")
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": f"Erreur: {str(e)}"
                    })
    
    # Bouton pour réinitialiser la conversation
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("Nouvelle conversation", type="secondary"):
            st.session_state.messages = []
            st.rerun()