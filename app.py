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

# ... imports ...

def handle_api_keys():
    """
    Gère l'authentification et active LangSmith.
    """
    # 1. Récupération des secrets (si fichier local secrets.toml existant)
    try:
        secrets = dict(st.secrets)
    except (FileNotFoundError, Exception):
        secrets = {}

    # Variables pour stocker les clés trouvées
    mistral = secrets.get("MISTRAL_API_KEY")
    llama = secrets.get("LLAMA_CLOUD_API_KEY")
    langsmith = secrets.get("LANGCHAIN_API_KEY")

    # 2. Si on n'a pas les clés dans les secrets, on affiche le formulaire
    if not (mistral and llama):
        with st.sidebar:
            st.header("🔐 Authentification")
            with st.form("login_form"):
                mistral_input = st.text_input("Clé Mistral", type="password")
                llama_input = st.text_input("Clé Llama Cloud", type="password")
                langsmith_input = st.text_input("Clé LangSmith (Optionnel)", type="password")
                
                if st.form_submit_button("Valider"):
                    if mistral_input and llama_input:
                        # On met à jour les variables avec ce que l'user a tapé
                        mistral = mistral_input
                        llama = llama_input
                        if langsmith_input:
                            langsmith = langsmith_input
                        st.rerun()
                    else:
                        st.error("Mistral et Llama Cloud sont obligatoires.")
                        return False
            return False

    # 3. INJECTION DANS L'ENVIRONNEMENT (C'est l'étape CRUCIALE)
    if mistral and llama:
        os.environ["MISTRAL_API_KEY"] = mistral
        os.environ["LLAMA_CLOUD_API_KEY"] = llama
        
        # --- ACTIVATION DE LANGSMITH ---
        # Si une clé LangSmith est trouvée (dans secrets ou input)
        if langsmith:
            os.environ["LANGCHAIN_API_KEY"] = langsmith
            os.environ["LANGCHAIN_TRACING"] = "true"  
            os.environ["LANGCHAIN_PROJECT"] = "My First App" 
            
            # st.sidebar.success("✅ LangSmith activé !") 
        
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

elif selected_page == "📁 Voir les données":
    view_data_page()