import asyncio
import os
import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine
from typing import List

# Imports de tes modules existants
from ingestion.table_extractor import PDFElectionExtractor
from ingestion.clean_data import ElectionDataCleaner
from database.connection import DatabaseConnection
from database.schema import metadata, creation_views_sql

class ElectionLoader:
    """
    Orchestrateur ETL (Extract, Transform, Load).
    1. Extrait les données du PDF via LlamaCloud.
    2. Nettoie les données via Pandas.
    3. Sauvegarde en CSV (backup).
    4. Insère les données normalisées dans la base SQLite.
    """

    def __init__(self, pdf_path: str, db_path: str, output_csv_path: str):
        self.pdf_path = Path(pdf_path)
        self.db_path = Path(db_path)
        self.output_csv_path = Path(output_csv_path)
        
        # Initialisation des composants
        api_key = os.getenv("LLAMA_CLOUD_API_KEY")
        if not api_key:
            raise ValueError("La clé LLAMA_CLOUD_API_KEY est manquante dans le .env")
            
        self.extractor = PDFElectionExtractor(api=api_key)
        self.cleaner = ElectionDataCleaner()

    async def run_pipeline(self):
        """
        Exécute tout le pipeline de données.
        """
        print(f" Démarrage du pipeline pour : {self.pdf_path.name}")


        # 1. Extraction (Appel API)
        raw_data = await self.extractor.extract_from_pdf(str(self.pdf_path))
        
        # 2. Aplatissement
        df_raw = self.extractor._flatten_to_dataframe(raw_data)
        
        # 3. Nettoyage
        print(" Nettoyage des données...")
        df_clean = self.cleaner.clean(df_raw)
        
        # 4. Sauvegarde CSV (Checkpoint)
        self.output_csv_path.parent.mkdir(parents=True, exist_ok=True)
        df_clean.to_csv(self.output_csv_path, index=False)
        print(f" Données nettoyées sauvegardées : {self.output_csv_path}")


        print(" Initialisation de la base de données...")
        
        # On utilise SQLAlchemy juste pour créer les tables proprement selon le schema.py
        # (L'URI sqlalchemy nécessite 3 slashs pour un chemin relatif ou 4 pour absolu)
        engine_url = f"sqlite:///{self.db_path.resolve()}"
        engine = create_engine(engine_url)
        
        # On vide les anciennes tables si elles existent (Reset)
        metadata.drop_all(engine)
        metadata.create_all(engine)
        print("Tables créées (Circonscriptions & Candidats).")

    
        print(" Insertion des données dans SQLite...")
        
        # On utilise ta classe de connexion pour l'insertion
        # IMPORTANT : read_only=False car on veut écrire
        db_conn = DatabaseConnection(str(self.db_path), read_only=False)
        conn = db_conn.get_connection()
        cursor = conn.cursor()

        try:
            # On groupe par circonscription pour insérer d'abord le parent, puis les enfants
            # Clés uniques pour identifier une circonscription (AVEC COLONNES NORMALISÉES)
            cols_group = [
                'region_nom', 'region_nom_norm', 'code_circonscription', 
                'nom_circonscription', 'nom_circonscription_norm',
                'nb_bureaux_vote', 'inscrits', 'votants', 'taux_participation',
                'bulletins_nuls', 'suffrages_exprimes', 
                'bulletins_blancs_nombre', 'bulletins_blancs_pourcentage'
            ]

            grouped = df_clean.groupby(cols_group)

            for group_keys, df_group in grouped:
                # 1. Préparer les données de la Circonscription (Parent)
                # group_keys contient les valeurs dans l'ordre de cols_group
                data_circo = dict(zip(cols_group, group_keys))
                
                # Renommage pour matcher le SQL (nb_bureaux_vote -> nb_bureau)
                data_circo['nb_bureau'] = data_circo.pop('nb_bureaux_vote')
                
                # Insertion Circonscription (AVEC COLONNES NORMALISÉES)
                sql_circo = """
                    INSERT INTO circonscriptions 
                    (region_nom, region_nom_norm, code_circonscription, 
                     nom_circonscription, nom_circonscription_norm, 
                     nb_bureau, inscrits, votants, taux_participation, 
                     bulletins_nuls, suffrages_exprimes, 
                     bulletins_blancs_nombre, bulletins_blancs_pourcentage)
                    VALUES (:region_nom, :region_nom_norm, :code_circonscription, 
                            :nom_circonscription, :nom_circonscription_norm, 
                            :nb_bureau, :inscrits, :votants, :taux_participation, 
                            :bulletins_nuls, :suffrages_exprimes, 
                            :bulletins_blancs_nombre, :bulletins_blancs_pourcentage)
                """
                # Le dictionnaire data_circo contient déjà les colonnes _norm
                # car elles sont dans le df_clean venant du cleaner !
                cursor.execute(sql_circo, data_circo)
                
                # Récupérer l'ID généré pour cette circonscription
                circo_id = cursor.lastrowid

                # 2. Insérer les Candidats (AVEC COLONNES NORMALISÉES)
                candidates_data = []
                for _, row in df_group.iterrows():
                    candidates_data.append({
                        "circonscription_id": circo_id,
                        "nom_liste_candidat": row["nom_liste_candidat"],
                        "nom_liste_candidat_norm": row["nom_liste_candidat_norm"], # Ajout
                        "parti_politique": row["parti_politique"],
                        "parti_politique_norm": row["parti_politique_norm"],       # Ajout
                        "score_voix": row["score_voix"],
                        "pourcentage_voix": row["pourcentage_voix"],
                        "est_elu": 1 if row["est_elu"] else 0
                    })
                
                sql_candidat = """
                    INSERT INTO candidats 
                    (circonscription_id, nom_liste_candidat, nom_liste_candidat_norm, 
                     parti_politique, parti_politique_norm, 
                     score_voix, pourcentage_voix, est_elu)
                    VALUES (:circonscription_id, :nom_liste_candidat, :nom_liste_candidat_norm, 
                            :parti_politique, :parti_politique_norm, 
                            :score_voix, :pourcentage_voix, :est_elu)
                """
                cursor.executemany(sql_candidat, candidates_data)

            conn.commit()
            print(f" Insertion terminée : {len(df_clean)} candidats traités.")


            print(" Création des vues analytiques...")
            for view_sql in creation_views_sql:
                cursor.execute(view_sql)
            conn.commit()
            print(" Vues créées avec succès.")

        except Exception as e:
            conn.rollback()
            print(f" Erreur critique lors de l'insertion : {e}")
            raise e
        finally:
            conn.close()


if __name__ == "__main__":
    # Configuration des chemins
    BASE_DIR = Path(__file__).resolve().parent.parent.parent # Remonte à la racine du projet
    PDF_FILE = BASE_DIR / "data/raw/resultat.pdf"
    DB_FILE = BASE_DIR / "data/processed/elections.db" # Ou dans data/database/elections.db
    CSV_OUT = BASE_DIR / "data/processed/elections_clean.csv"

    # Vérification que le PDF existe
    if not PDF_FILE.exists():
        print(f"Erreur : Le fichier {PDF_FILE} n'existe pas.")
        exit(1)

    # Lancement du loader
    loader = ElectionLoader(str(PDF_FILE), str(DB_FILE), str(CSV_OUT))
    
    # Exécution asynchrone
    asyncio.run(loader.run_pipeline())