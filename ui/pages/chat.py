import streamlit as st
from pathlib import Path
import sys
import pandas as pd
import base64

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
    
    # Initialiser l'agent avec cache
    @st.cache_resource
    def get_agent():
        return build_agent_graph()
    
    agent = get_agent()
    
    # Initialiser l'historique
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # --- FONCTION INTERNE POUR AFFICHER LES MESSAGES ---
    def display_message(message):
        with st.chat_message(message["role"]):
            # 1. Texte
            st.markdown(message["content"])
            
            # 2. Graphique (Décodage Base64)
            if message.get("chart"):
                chart_info = message["chart"]
                try:
                    # Décodage de la chaîne base64 envoyée par Matplotlib
                    img_bytes = base64.b64decode(chart_info["data"])
                    st.image(img_bytes, width="stretch")
                except Exception as e:
                    st.error(f"Erreur d'affichage du graphique : {e}")
            
            # 3. Données SQL (Tableau)
            if message.get("sql_results") is not None:
                with st.expander("Voir les données brutes"):
                    results = message["sql_results"]
                    df = pd.DataFrame(results) if isinstance(results, list) else results
                    st.dataframe(df, width="stretch")

    # Afficher l'historique existant
    for message in st.session_state.messages:
        display_message(message)
    
    # --- INPUT UTILISATEUR ---
    if prompt := st.chat_input("Posez votre question ici..."):
        # Ajouter et afficher le message utilisateur
        user_msg = {"role": "user", "content": prompt}
        st.session_state.messages.append(user_msg)
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Réponse de l'assistant
        with st.chat_message("assistant"):
            with st.spinner("Analyse des données en cours..."):
                try:
                    # Préparation de l'état initial pour LangGraph
                    initial_state = {
                        "user_query": prompt,
                        "classification": None,
                        "sql_query": None,
                        "sql_results": [],
                        "chart_generated": False,
                        "errors": [],
                        "final_answer": None
                    }
                    
                    # Invoquer l'agent (LangGraph)
                    result = agent.invoke(initial_state)
                    
                    # Extraction des résultats
                    final_answer = result.get("final_answer", "Désolé, je n'ai pas pu générer une réponse.")
                    sql_results = result.get("sql_results")
                    # Récupère l'image base64 depuis le node generate_chart
                    chart_data = result.get("chart_data") 
                    
                    # Affichage immédiat du texte
                    st.markdown(final_answer)
                    
                    # Affichage immédiat du graphique si présent
                    if chart_data and isinstance(chart_data, dict) and "data" in chart_data:
                        img_bytes = base64.b64decode(chart_data["data"])
                        st.image(img_bytes, width="stretch")
                    
                    # Affichage immédiat du tableau si présent
                    if sql_results is not None:
                        with st.expander("Voir les données brutes"):
                            df = pd.DataFrame(sql_results) if isinstance(sql_results, list) else sql_results
                            st.dataframe(df, width="stretch")
                    
                    # Sauvegarde dans l'historique
                    message_data = {
                        "role": "assistant",
                        "content": final_answer,
                        "chart": chart_data,
                        "sql_results": sql_results
                    }
                    st.session_state.messages.append(message_data)
                    
                except Exception as e:
                    import traceback
                    error_details = traceback.format_exc()
                    st.error(f"Erreur : {str(e)}")
                    # On log l'erreur pour le debug mais on reste propre pour l'utilisateur
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": "Désolé, une erreur technique est survenue."
                    })

    # --- BOUTON RESET ---
    st.sidebar.divider()
    if st.sidebar.button("Nouvelle conversation"):
        st.session_state.messages = []
        st.rerun()