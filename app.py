import streamlit as st
import os
from pathlib import Path

# Imports UI
from ui.menu import sidebar_menu
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

# ... imports ...

def handle_api_keys():
    """
    Gère l'authentification avec persistance des données.
    """
    # 1. On cherche d'abord dans les SECRETS (fichier .streamlit/secrets.toml)
    try:
        secrets = dict(st.secrets)
    except (FileNotFoundError, Exception):
        secrets = {}

  
    mistral = secrets.get("MISTRAL_API_KEY") or st.session_state.get("MISTRAL_API_KEY")
    llama = secrets.get("LLAMA_CLOUD_API_KEY") or st.session_state.get("LLAMA_CLOUD_API_KEY")
    langsmith = secrets.get("LANGCHAIN_API_KEY") or st.session_state.get("LANGCHAIN_API_KEY")

    # 3. Si on n'a toujours pas les clés, on affiche le formulaire
    if not (mistral and llama):
        with st.sidebar:
            st.header("🔐 Authentification")
            with st.form("login_form"):
                mistral_input = st.text_input("Clé Mistral", type="password")
                llama_input = st.text_input("Clé Llama Cloud", type="password")
                langsmith_input = st.text_input("Clé LangSmith (Optionnel)", type="password")
                
                if st.form_submit_button("Valider"):
                    if mistral_input and llama_input:
                        # --- CORRECTION ICI ---
                        # On sauvegarde dans le session_state pour qu'elles survivent au rerun
                        st.session_state["MISTRAL_API_KEY"] = mistral_input
                        st.session_state["LLAMA_CLOUD_API_KEY"] = llama_input
                        
                        if langsmith_input:
                            st.session_state["LANGCHAIN_API_KEY"] = langsmith_input
                        
                        st.success("Connexion réussie !")
                        st.rerun() # Maintenant, au rechargement, les clés seront trouvées à l'étape 2
                    else:
                        st.error("Mistral et Llama Cloud sont obligatoires.")
                        
            # On retourne False tant que le formulaire est affiché
            return False

    # 4. INJECTION DANS L'ENVIRONNEMENT
    # Si on arrive ici, c'est qu'on a les clés (soit via secrets, soit via session_state)
    if mistral and llama:
        os.environ["MISTRAL_API_KEY"] = mistral
        os.environ["LLAMA_CLOUD_API_KEY"] = llama
        
        # Activation LangSmith
        if langsmith:
            os.environ["LANGCHAIN_API_KEY"] = langsmith
            os.environ["LANGCHAIN_TRACING_V2"] = "true" # Note: V2 est préférable à TRACING tout court
            os.environ["LANGCHAIN_PROJECT"] = "Elections CI App"
        
        st.session_state["authenticated"] = True
        return True

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
    ## Interface d'exploration des données d'elections legislatives ivoiriennes 
    
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
        
