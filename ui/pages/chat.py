import streamlit as st
from pathlib import Path
import sys
import pandas as pd
import base64
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

def chat_page():
    """
    Page de chat avec l'agent SQL électoral
    """
    st.header("Assistant Electoral IA")
    st.markdown("Posez vos questions sur les données électorales")
    st.warning("""
 **Important pour une meilleure expérience :**

Pour des résultats plus précis, veuillez toujours préciser :
- La **nature** de l'élément recherché (région, circonscription, parti, candidat)
**Exemples de bonnes questions :**
-  "Combien de sièges a gagné le parti RHDP ?"
-  "Quel est le taux de participation dans la région de Gbêkê ?"
    """)

    
    # --- LAZY IMPORT & INITIALISATION ---
    @st.cache_resource(show_spinner="Patientez quelques instants ...")
    def get_agent():
        # C'est ICI que l'import se fait, une fois que les clés sont chargées dans app.py
        from src.agent.graph import build_agent_graph
        return build_agent_graph()
    
    # Tentative de chargement de l'agent
    try:
        agent = get_agent()
    except Exception as e:
        st.error("Impossible d'initialiser l'agent IA.")
        st.warning(f"Détail de l'erreur : {e}")
        st.info("💡 Vérifiez que vous avez bien entré vos clés API dans la barre latérale.")
        return # On arrête l'exécution de la fonction ici si l'agent n'est pas prêt

    # --- HISTORIQUE ---
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # --- FONCTION D'AFFICHAGE ---
    def display_message(message):
        with st.chat_message(message["role"]):
            # 1. Texte
            st.markdown(message["content"])
            
            # 2. Graphique (Décodage Base64)
            if message.get("chart"):
                chart_info = message["chart"]
                try:
                    # Gestion robuste du format base64
                    data_str = chart_info.get("data", "") if isinstance(chart_info, dict) else chart_info
                    img_bytes = base64.b64decode(data_str)
                    st.image(img_bytes, width="stretch")
                except Exception as e:
                    st.error(f"Erreur d'affichage du graphique")
            
            # 3. Données SQL (Tableau)
            if message.get("sql_results") is not None:
                # On évite d'afficher des listes vides
                results = message["sql_results"]
                if isinstance(results, list) and not results:
                    pass
                else:
                    with st.expander("Voir les données brutes"):
                        df = pd.DataFrame(results) if isinstance(results, list) else results
                        st.dataframe(df, use_container_width=True)

    # Affichage de l'historique
    for message in st.session_state.messages:
        display_message(message)
    
    # --- INTERACTION UTILISATEUR ---
    if prompt := st.chat_input("Posez votre question ici..."):
        # 1. Affichage User
        user_msg = {"role": "user", "content": prompt}
        st.session_state.messages.append(user_msg)
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # 2. Réponse Assistant
        with st.chat_message("assistant"):
            with st.spinner("Analyse des données en cours..."):
                try:
                    # Préparation de l'état initial pour LangGraph
                    initial_state = {
                        "user_query": prompt,
                        # On initialise les autres champs à None/Vide pour éviter les KeyError
                        "classification": None,
                        "sql_query": None,
                        "sql_results": [],
                        "chart_generated": False,
                        "errors": [],
                        "final_answer": None
                    }
                    
                    # Invoquer l'agent
                    result = agent.invoke(initial_state)
                    
                    # Extraction sécurisée des résultats
                    final_answer = result.get("final_answer", "Je n'ai pas trouvé de réponse.")
                    sql_results = result.get("sql_results")
                    chart_data = result.get("chart_data") 
                    
                    # --- AFFICHAGE LIVE ---
                    st.markdown(final_answer)
                    
                    if chart_data:
                        try:
                            data_str = chart_data.get("data", "") if isinstance(chart_data, dict) else chart_data
                            img_bytes = base64.b64decode(data_str)
                            st.image(img_bytes, width="stretch")
                        except:
                            pass # On ignore silencieusement les erreurs d'image en live
                    
                    if sql_results:
                         if isinstance(sql_results, list) and len(sql_results) > 0:
                            with st.expander("Voir les données brutes"):
                                df = pd.DataFrame(sql_results)
                                st.dataframe(df, use_container_width=True)
                    
                    # --- SAUVEGARDE HISTORIQUE ---
                    message_data = {
                        "role": "assistant",
                        "content": final_answer,
                        "chart": chart_data,
                        "sql_results": sql_results
                    }
                    st.session_state.messages.append(message_data)
                    
                except Exception as e:
                    # Gestion propre des erreurs pour l'utilisateur
                    error_msg = f"Une erreur est survenue : {str(e)}"
                    st.error(error_msg)
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": "Désolé, une erreur technique m'a empêché de répondre."
                    })

    # --- RESET ---
    st.sidebar.divider()
    if st.sidebar.button("🗑️ Nouvelle conversation"):
        st.session_state.messages = []
        st.rerun()