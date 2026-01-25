import pandas as pd
import unicodedata

class ElectionDataCleaner:
    """
    Classe pour nettoyer et préparer un DataFrame de résultats électoraux.
    
    Fonctionnalités :
    - Convertir les colonnes numériques en int ou float
    - Diviser les pourcentages par 100 pour SQL et calculs
    - Créer des colonnes normalisées pour filtrage et recherche
    - Remplacer les régions vides par 'NON_TRANSMIS'
    - Supprimer accents et mettre en minuscules pour les colonnes de recherche
    - Nettoyer les espaces dans les chiffres
    """

    def __init__(self):
        # Colonnes numériques
        self.int_cols = [
            "nb_bureaux_vote", "inscrits", "votants",
            "bulletins_nuls", "suffrages_exprimes", "bulletins_blancs_nombre", "score_voix"
        ]
        self.float_cols = ["taux_participation", "bulletins_blancs_pourcentage", "pourcentage_voix"]

        # Colonnes texte à normaliser
        self.text_cols = ["region_nom", "nom_circonscription", "parti_politique", "nom_liste_candidat"]

    @staticmethod
    def normalize_text(s: str) -> str:
        """
        Transforme le texte en minuscule et supprime les accents.
        """
        if pd.isna(s):
            return ""
        s = str(s).lower()
        s = ''.join(c for c in unicodedata.normalize('NFD', s)
                    if unicodedata.category(c) != 'Mn')
        return s

    @staticmethod
    def clean_numeric_string(s: str) -> str:
        """
        Supprime les espaces dans les chiffres et remplace la virgule par un point pour float.
        """
        if pd.isna(s):
            return "0"
        s = str(s).replace(" ", "").replace(",", ".")
        return s

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Applique le nettoyage complet sur le DataFrame.
        """
        df_clean = df.copy()

        #  Remplacer régions vides par 'NON_TRANSMIS'
        if "region_nom" in df_clean.columns:
            df_clean["region_nom"] = df_clean["region_nom"].fillna("NON_TRANSMIS")

        #  Nettoyer et convertir colonnes int
        for col in self.int_cols:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].apply(self.clean_numeric_string)
                df_clean[col] = pd.to_numeric(df_clean[col], errors="coerce").fillna(0).astype(int)

        #  Nettoyer et convertir colonnes float (y compris pourcentages)
        for col in self.float_cols:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].apply(self.clean_numeric_string)
                df_clean[col] = pd.to_numeric(df_clean[col], errors="coerce").fillna(0.0).astype(float)
                df_clean[col] = df_clean[col] / 100  # fraction pour SQL et calculs

        #  Normaliser colonnes texte pour filtrage/recherche
        for col in self.text_cols:
            if col in df_clean.columns:
                df_clean[col + "_norm"] = df_clean[col].apply(self.normalize_text)

        # S'assurer que la colonne booléenne est correcte
        if "est_elu" in df_clean.columns:
            df_clean["est_elu"] = df_clean["est_elu"].fillna(False).astype(bool)

        return df_clean
