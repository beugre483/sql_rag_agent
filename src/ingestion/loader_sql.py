import asyncio
import os
import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine
from typing import List

from ingestion.table_extractor import PDFElectionExtractor  
from ingestion.clean_data import ElectionDataCleaner
from database.connection import DatabaseConnection
from database.schema import metadata, creation_views_sql

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

    async def run_pipeline(self):
        print("\n" + "="*70)
        print(f" DÉMARRAGE DU PIPELINE : {self.pdf_path.name}")
        print("="*70)

        print("\n ÉTAPE 1/5 : Extraction du PDF (Ordre conservé)...")
        # Plus d'argument auto_propagate, c'est fait d'office dans l'extracteur maintenant
        await self.extractor.extract_from_pdf(str(self.pdf_path))
        
        print("\n  ÉTAPE 2/5 : Aplatissement des données...")
        df_raw = self.extractor.to_dataframe()
        print(f"   {len(df_raw)} lignes extraites")

        print("\n🧹 ÉTAPE 3/5 : Nettoyage des données...")
        df_clean = self.cleaner.clean(df_raw)
        print(f"   {len(df_clean)} lignes après nettoyage")

        print("\nÉTAPE 4/5 : Sauvegarde CSV...")
        self.output_csv_path.parent.mkdir(parents=True, exist_ok=True)
        df_clean.to_csv(self.output_csv_path, index=False, encoding='utf-8')
        print(f"   ✓ Fichier généré : {self.output_csv_path}")

        print("\n  ÉTAPE 5/5 : Chargement dans la base de données...")
        
        # Initialisation DB
        engine_url = f"sqlite:///{self.db_path.resolve()}"
        engine = create_engine(engine_url)
        metadata.drop_all(engine)
        metadata.create_all(engine)

        db_conn = DatabaseConnection(str(self.db_path), read_only=False)
        conn = db_conn.get_connection()
        cursor = conn.cursor()

        try:
            # Groupement par circonscription pour recréer la structure relationnelle
            # On utilise sort=False pour ne pas casser l'ordre d'apparition
            cols_group = [
                'region_nom', 'region_nom_norm', 'code_circonscription', 
                'nom_circonscription', 'nom_circonscription_norm',
                'nb_bureaux_vote', 'inscrits', 'votants', 'taux_participation',
                'bulletins_nuls', 'suffrages_exprimes', 
                'bulletins_blancs_nombre', 'bulletins_blancs_pourcentage'
            ]

            # sort=False est CRUCIAL ici pour garder l'ordre du PDF
            grouped = df_clean.groupby(cols_group, sort=False)

            for group_keys, df_group in grouped:
                data_circo = dict(zip(cols_group, group_keys))
                data_circo['nb_bureau'] = data_circo.pop('nb_bureaux_vote')
                
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
                cursor.execute(sql_circo, data_circo)
                circo_id = cursor.lastrowid

                candidates_data = []
                for _, row in df_group.iterrows():
                    candidates_data.append({
                        "circonscription_id": circo_id,
                        "nom_liste_candidat": row["nom_liste_candidat"],
                        "nom_liste_candidat_norm": row["nom_liste_candidat_norm"],
                        "parti_politique": row["parti_politique"],
                        "parti_politique_norm": row["parti_politique_norm"],
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
            
            # Vues
            for view_sql in creation_views_sql:
                cursor.execute(view_sql)
            conn.commit()

        except Exception as e:
            conn.rollback()
            print(f"\n ERREUR : {e}")
            raise e
        finally:
            conn.close()

        print("\n" + "="*70)
        print(" TERMINÉ !")
        print("="*70)

if __name__ == "__main__":
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    PDF_FILE = BASE_DIR / "data/raw/resultat.pdf"
    DB_FILE = BASE_DIR / "data/processed/elections.db"
    CSV_OUT = BASE_DIR / "data/processed/elections_clean.csv"

    if not PDF_FILE.exists():
        print(f"Erreur: {PDF_FILE} introuvable.")
        exit(1)

    loader = ElectionLoader(str(PDF_FILE), str(DB_FILE), str(CSV_OUT))
    asyncio.run(loader.run_pipeline())