import asyncio
import os
import pandas as pd
import unicodedata
from pathlib import Path
from sqlalchemy import create_engine

from ingestion.table_extractor import PDFElectionExtractor  
from ingestion.clean_data import ElectionDataCleaner
from database.connection import DatabaseConnection
from database.schema import metadata, creation_views_sql
from dotenv import load_dotenv

load_dotenv()


class ElectionLoader:
    def __init__(self, pdf_path: str, db_path: str, output_csv_path: str):
        self.pdf_path = Path(pdf_path)
        self.db_path = Path(db_path)
        self.output_csv_path = Path(output_csv_path)
        
        api_key = os.getenv("LLAMA_CLOUD_API_KEY")
        if not api_key:
            raise ValueError("La clé LLAMA_CLOUD_API_KEY est manquante dans le .env")
            
        self.extractor = PDFElectionExtractor(api_key=api_key)
        self.cleaner = ElectionDataCleaner()

    def _normalize_text(self, text):
        """Nettoie le texte : Majuscules, sans accents"""
        if pd.isna(text):
            return None
        text = str(text).upper()
        text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
        return text.strip()

    def _prepare_dataframe_for_db(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Renomme les colonnes de l'extracteur vers les noms de la Base de Données
        et génère les colonnes _norm.
        """
        # Mapping: Nom Extracteur (gauche) -> Nom DB (droite)
        mapping = {
            'region': 'region_nom',
            'code_circo': 'code_circonscription',
            'nom_circo': 'nom_circonscription',
            'nb_bureaux': 'nb_bureaux_vote',
            'nb_blancs': 'bulletins_blancs_nombre',
            'pourcentage_blancs': 'bulletins_blancs_pourcentage',
            'parti': 'parti_politique',
            'candidat': 'nom_liste_candidat',
            'score': 'score_voix',
            'pourcentage': 'pourcentage_voix'
        }
        
        # Renommage
        df = df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})

        # Création des colonnes normalisées (_norm)
        cols_to_normalize = {
            'region_nom': 'region_nom_norm',
            'nom_circonscription': 'nom_circonscription_norm',
            'nom_liste_candidat': 'nom_liste_candidat_norm',
            'parti_politique': 'parti_politique_norm'
        }

        for source, target in cols_to_normalize.items():
            if source in df.columns:
                df[target] = df[source].apply(self._normalize_text)
            else:
                df[target] = None # Sécurité

        # Conversion Types Numériques (Sécurité)
        cols_int = ['inscrits', 'votants', 'nb_bureaux_vote', 'bulletins_nuls', 'suffrages_exprimes', 'bulletins_blancs_nombre', 'score_voix']
        for col in cols_int:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        
        cols_float = ['taux_participation', 'bulletins_blancs_pourcentage', 'pourcentage_voix']
        for col in cols_float:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

        return df

    async def run_pipeline(self):
        print("\n" + "="*70)
        print(f" DÉMARRAGE DU PIPELINE : {self.pdf_path.name}")
        print("="*70)

        # 1. Extraction
        await self.extractor.extract_from_pdf(str(self.pdf_path))
        df_raw = self.extractor.to_dataframe()
        print(f"   ✓ Lignes extraites : {len(df_raw)}")

        if df_raw.empty:
            print("   ! Aucune donnée extraite. Arrêt.")
            return

        # 2. Préparation (Renommage + Normalisation)
        df_mapped = self._prepare_dataframe_for_db(df_raw)

        # 3. Nettoyage (Via ton module existant)
        df_clean = self.cleaner.clean(df_mapped)
        print(f"   ✓ Lignes après nettoyage : {len(df_clean)}")

        # 4. Sauvegarde CSV
        self.output_csv_path.parent.mkdir(parents=True, exist_ok=True)
        df_clean.to_csv(self.output_csv_path, index=False, encoding='utf-8')
        print(f"   ✓ CSV généré : {self.output_csv_path}")

        # 5. Chargement en Base de Données
        print("\n ÉTAPE : Chargement SQL...")
        engine_url = f"sqlite:///{self.db_path.resolve()}"
        engine = create_engine(engine_url)
        metadata.drop_all(engine)
        metadata.create_all(engine)

        db_conn = DatabaseConnection(str(self.db_path), read_only=False)
        conn = db_conn.get_connection()
        cursor = conn.cursor()

        try:
            # Groupement par Circonscription
            # On utilise les colonnes qui définissent une circo unique
            cols_group = [
                'region_nom', 'region_nom_norm', 'code_circonscription', 
                'nom_circonscription', 'nom_circonscription_norm',
                'nb_bureaux_vote', 'inscrits', 'votants', 'taux_participation',
                'bulletins_nuls', 'suffrages_exprimes', 
                'bulletins_blancs_nombre', 'bulletins_blancs_pourcentage'
            ]
            
            # Filtre pour ne garder que les colonnes présentes dans le DF
            cols_group = [c for c in cols_group if c in df_clean.columns]

            grouped = df_clean.groupby(cols_group, sort=False, dropna=False)

            circo_count = 0
            cand_count = 0

            for group_keys, df_group in grouped:
                # Préparation données Circo
                # zip permet d'associer NomColonne -> Valeur
                data_circo = dict(zip(cols_group, group_keys))
                
                # Adaptation nom colonne pour INSERT (nb_bureaux_vote -> nb_bureau dans ta DB)
                if 'nb_bureaux_vote' in data_circo:
                    data_circo['nb_bureau'] = data_circo.pop('nb_bureaux_vote')
                
                # Gestion des None
                for k, v in data_circo.items():
                    if pd.isna(v): data_circo[k] = None

                # Construction dynamique requête INSERT Circo
                keys = list(data_circo.keys())
                placeholders = [f":{k}" for k in keys]
                sql_circo = f"INSERT INTO circonscriptions ({', '.join(keys)}) VALUES ({', '.join(placeholders)})"
                
                cursor.execute(sql_circo, data_circo)
                circo_id = cursor.lastrowid
                circo_count += 1

                # Préparation données Candidats
                candidates_data = []
                for _, row in df_group.iterrows():
                    candidates_data.append({
                        "circonscription_id": circo_id,
                        "nom_liste_candidat": row.get("nom_liste_candidat"),
                        "nom_liste_candidat_norm": row.get("nom_liste_candidat_norm"),
                        "parti_politique": row.get("parti_politique"),
                        "parti_politique_norm": row.get("parti_politique_norm"),
                        "score_voix": row.get("score_voix", 0),
                        "pourcentage_voix": row.get("pourcentage_voix", 0.0),
                        "est_elu": 1 if row.get("est_elu") else 0
                    })
                
                sql_cand = """
                    INSERT INTO candidats 
                    (circonscription_id, nom_liste_candidat, nom_liste_candidat_norm, 
                     parti_politique, parti_politique_norm, score_voix, pourcentage_voix, est_elu)
                    VALUES (:circonscription_id, :nom_liste_candidat, :nom_liste_candidat_norm, 
                            :parti_politique, :parti_politique_norm, :score_voix, :pourcentage_voix, :est_elu)
                """
                cursor.executemany(sql_cand, candidates_data)
                cand_count += len(candidates_data)

            conn.commit()
            print(f"   ✓ {circo_count} circonscriptions insérées")
            print(f"   ✓ {cand_count} candidats insérés")
            
            # Création des Vues SQL
            print("\n Création des vues...")
            for view_sql in creation_views_sql:
                cursor.execute(view_sql)
            conn.commit()
            print("   ✓ Vues créées")

        except Exception as e:
            conn.rollback()
            print(f"\n ERREUR CRITIQUE : {e}")
            import traceback
            traceback.print_exc()
        finally:
            conn.close()

        print("\n" + "="*70)
        print(" TERMINÉ !")
        print("="*70)

if __name__ == "__main__":
    # CONFIGURATION DES CHEMINS
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    PDF_FILE = BASE_DIR / "data/raw/resultat.pdf"
    DB_FILE = BASE_DIR / "data/processed/elections.db"
    CSV_OUT = BASE_DIR / "data/processed/elections_clean.csv"

    if not PDF_FILE.exists():
        print(f" Erreur: Le fichier {PDF_FILE} est introuvable.")
        exit(1)

    loader = ElectionLoader(str(PDF_FILE), str(DB_FILE), str(CSV_OUT))
    asyncio.run(loader.run_pipeline())