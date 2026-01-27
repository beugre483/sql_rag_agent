import streamlit as st
from ui.menu import sidebar_menu
from ui.pages.view_data import view_data_page
from ui.pages.chat import chat_page
from pathlib import Path

# Racine du projet (dossier contenant app.py)
BASE_DIR = Path(__file__).resolve().parent
UI_DIR = BASE_DIR / "ui"
DATA_DIR = BASE_DIR / "data" / "processed"

def load_css():
    css_path = UI_DIR / "style.css"
    if css_path.exists():
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


load_css()

# Appel du menu
page = sidebar_menu()

# CORRECTION ICI : Ajout des émojis pour correspondre au menu
if page == "🏠 Accueil":
    st.title("Bienvenue")
    st.markdown("""
    ## Interface d'exploration des données électorales
    
    Cette application vous permet de :
    
    ### Chat IA
    Posez des questions en langage naturel sur les données électorales.
    L'agent IA génère automatiquement des requêtes SQL et des visualisations.
    
    **Exemples de questions :**
    - Quel candidat a gagné dans la région AGNEBY-TIASSA ?
    - Montre-moi le taux de participation par région
    - Quels sont les résultats du RHDP dans toutes les circonscriptions ?
    
    ### Voir les données
    Explorez directement les fichiers CSV bruts extraits depuis les PDF.
    """)

elif page == "🤖 Chat IA":  # Ajout de l'émoji
    chat_page()

elif page == "📁 Voir les données":  # Ajout de l'émoji
    view_data_page()