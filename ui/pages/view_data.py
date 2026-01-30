import streamlit as st
import pandas as pd
from pathlib import Path

# Chemins RELATIFS au projet
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "processed"

@st.cache_data
def load_csv(filename: str) -> pd.DataFrame:
    path = DATA_DIR / filename
    return pd.read_csv(path)

def view_data_page():
    st.header("📂 Données électorales")

    # Lister les fichiers CSV
    csv_files = [f.name for f in DATA_DIR.glob("*.csv")]
    
    if not csv_files:
        st.warning("Aucun fichier CSV trouvé dans le dossier data/processed")
        return

    selected_file = st.selectbox(
        "Choisir un fichier",
        csv_files
    )

    if selected_file:
        df = load_csv(selected_file)

        st.markdown(f"### Aperçu : `{selected_file}`")
        st.dataframe(df, use_container_width=True)
