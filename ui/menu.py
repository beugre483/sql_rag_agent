import streamlit as st

def sidebar_menu():
    """Affiche le menu de navigation dans la sidebar"""
    st.sidebar.title("📊 Electoral AI")

    # J'ai ajouté "🤖 Chat IA" qui manquait
    page = st.sidebar.radio(
        "Navigation",
        ["🏠 Accueil", "🤖 Chat IA", "📁 Voir les données"]
    )

    return page