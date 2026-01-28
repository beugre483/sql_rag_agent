import streamlit as st
import os
from pathlib import Path

# Imports UI
from ui.menu import sidebar_menu
from ui.pages.view_data import view_data_page
from ui.pages.chat import chat_page

# --- 1. CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Élections CI", layout="wide")

BASE_DIR = Path(__file__).resolve().parent
UI_DIR = BASE_DIR / "ui"

def load_css():
    css_path = UI_DIR / "style.css"
    
    if css_path.exists():
        with open(css_path, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    elif css_path.exists():
        with open(css_path, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

def handle_api_keys():
    """
    Affiche un formulaire de connexion.
    Mistral ET LlamaCloud sont obligatoires.
    """
    
    # Si l'utilisateur est déjà validé, on sort
    if st.session_state.get("authenticated", False):
        return True

    # Tentative de récupération automatique (si secrets.toml existe)
    try:
        secrets = dict(st.secrets)
    except (FileNotFoundError, Exception):
        secrets = {}

    # Si les clés sont déjà dans les secrets (Cloud), on valide silencieusement
    if "MISTRAL_API_KEY" in secrets and "LLAMA_CLOUD_API_KEY" in secrets:
        os.environ["MISTRAL_API_KEY"] = secrets["MISTRAL_API_KEY"]
        os.environ["LLAMA_CLOUD_API_KEY"] = secrets["LLAMA_CLOUD_API_KEY"]
        
        if "LANGCHAIN_API_KEY" in secrets:
            os.environ["LANGCHAIN_API_KEY"] = secrets["LANGCHAIN_API_KEY"]
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
        
        st.session_state["authenticated"] = True
        return True

    # SINON : Affichage du formulaire OBLIGATOIRE dans la Sidebar
    with st.sidebar:
        st.header("🔐 Authentification")
        st.info("Veuillez entrer vos clés pour continuer.")
        
        with st.form("login_form"):
            mistral_key = st.text_input("Clé Mistral API (Obligatoire)", type="password")
            llama_key = st.text_input("Clé Llama Cloud (Obligatoire)", type="password")
            langsmith_key = st.text_input("Clé LangSmith (Optionnel)", type="password")
            
            submitted = st.form_submit_button("Valider")
            
            if submitted:
                # VÉRIFICATION STRICTE : Les deux clés sont exigées
                if not mistral_key or not llama_key:
                    st.error("❌ Vous devez entrer la clé Mistral ET la clé Llama Cloud.")
                else:
                    # Injection dans l'environnement
                    os.environ["MISTRAL_API_KEY"] = mistral_key
                    os.environ["LLAMA_CLOUD_API_KEY"] = llama_key
                    
                    if langsmith_key:
                        os.environ["LANGCHAIN_API_KEY"] = langsmith_key
                        os.environ["LANGCHAIN_TRACING_V2"] = "true"
                        os.environ["LANGCHAIN_PROJECT"] = "Challenge Artefact Demo"
                    
                    # Validation
                    st.session_state["authenticated"] = True
                    st.success("Clés valides.")
                    st.rerun()
    
    return False

# --- 3. EXÉCUTION PRINCIPALE ---

# A. Vérification des clés
is_authenticated = handle_api_keys()

# B. Menu Latéral
selected_page = sidebar_menu()

# --- 4. ROUTAGE DES PAGES ---

if selected_page == "🏠 Accueil":
    st.title("Bienvenue")
    st.markdown("""
    ## Interface d'exploration des données électorales
    
    Cette application vous permet de :
    
    ### Chat
    Posez des questions sur les données électorales.
    Le système interroge la base de données pour vous répondre.
    
    **Important :** Vous devez entrer vos clés dans la barre latérale pour accéder au chat.
    
    ### Voir les données
    Explorez directement les tableaux de résultats.
    """)

elif selected_page == "🤖 Chat IA":
    if is_authenticated:
        try:
            chat_page()
        except Exception as e:
            st.error(f"Une erreur est survenue : {e}")
    else:
        st.warning("🔒 Accès verrouillé")
        st.info("⬅️ Vous devez entrer vos clés dans la barre latérale pour utiliser cette fonctionnalité.")

elif selected_page == "📁 Voir les données":
    view_data_page()