import streamlit as st

def sidebar_menu():
    """Affiche le menu de navigation dans la sidebar"""
    st.sidebar.title("📊 Electoral AI")

    page = st.sidebar.radio(
        "Navigation",
        ["🏠 Accueil", "🤖 Chat IA"]
    )

    return page