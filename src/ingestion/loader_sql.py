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
        await self.extractor.extract_from_pdf(str(self.pdf_path))
        
        print("\n ÉTAPE 2/5 : Aplatissement des données...")
        df_raw = self.extractor.to_dataframe()
        print(f"   ✓ {len(df_raw)} lignes extraites")

        print("\n🧹 ÉTAPE 3/5 : Nettoyage des données...")
        df_clean = self.cleaner.clean(df_raw)
        print(f"   ✓ {len(df_clean)} lignes après nettoyage")

        print("\n ÉTAPE 4/5 : Sauvegarde CSV...")
        self.output_csv_path.parent.mkdir(parents=True, exist_ok=True)
        df_clean.to_csv(self.output_csv_path, index=False, encoding='utf-8')
        print(f"   ✓ Fichier généré : {self.output_csv_path}")

        print("\n ÉTAPE 5/5 : Chargement dans la base de données...")
        
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

       
            grouped = df_clean.groupby(cols_group, sort=False)

            #  Définir les colonnes numériques pour conversion explicite
            int_columns = {'nb_bureaux_vote', 'inscrits', 'votants', 
                          'bulletins_nuls', 'suffrages_exprimes', 
                          'bulletins_blancs_nombre'}
            float_columns = {'taux_participation', 'bulletins_blancs_pourcentage'}

            circonscriptions_count = 0
            candidats_count = 0

            for group_keys, df_group in grouped:
                data_circo = {}
                for key, value in zip(cols_group, group_keys):
                    if pd.isna(value):
                        data_circo[key] = None
                    elif key in int_columns:
                        # Convertir numpy int en int Python natif
                        data_circo[key] = int(value)
                    elif key in float_columns:
                        # Convertir numpy float en float Python natif
                        data_circo[key] = float(value)
                    else:
                        # Pour les strings
                        data_circo[key] = str(value) if value is not None else None
                
                # Renommer nb_bureaux_vote -> nb_bureau
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
                circonscriptions_count += 1

                #  CONVERSION EXPLICITE POUR LES CANDIDATS
                candidates_data = []
                for _, row in df_group.iterrows():
                    candidates_data.append({
                        "circonscription_id": int(circo_id),
                        "nom_liste_candidat": str(row["nom_liste_candidat"]),
                        "nom_liste_candidat_norm": str(row["nom_liste_candidat_norm"]) if pd.notna(row["nom_liste_candidat_norm"]) else None,
                        "parti_politique": str(row["parti_politique"]) if pd.notna(row["parti_politique"]) else None,
                        "parti_politique_norm": str(row["parti_politique_norm"]) if pd.notna(row["parti_politique_norm"]) else None,
                        "score_voix": int(row["score_voix"]) if pd.notna(row["score_voix"]) else 0,
                        "pourcentage_voix": float(row["pourcentage_voix"]) if pd.notna(row["pourcentage_voix"]) else 0.0,
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
                candidats_count += len(candidates_data)

            conn.commit()
            print(f"   ✓ {circonscriptions_count} circonscriptions insérées")
            print(f"   ✓ {candidats_count} candidats insérés")
            
            # Vues
            print("\n Création des vues SQL...")
            for view_sql in creation_views_sql:
                cursor.execute(view_sql)
            conn.commit()
            print("   ✓ Vues créées avec succès")

        except Exception as e:
            conn.rollback()
            print(f"\n ERREUR : {e}")
            import traceback
            traceback.print_exc()
            raise e
        finally:
            conn.close()

        print("\n" + "="*70)
        print(" PIPELINE TERMINÉ AVEC SUCCÈS !")
        print("="*70)

if __name__ == "__main__":
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    PDF_FILE = BASE_DIR / "data/raw/resultat.pdf"
    DB_FILE = BASE_DIR / "data/processed/elections.db"
    CSV_OUT = BASE_DIR / "data/processed/elections_clean.csv"

    if not PDF_FILE.exists():
        print(f" Erreur: {PDF_FILE} introuvable.")
        exit(1)

    loader = ElectionLoader(str(PDF_FILE), str(DB_FILE), str(CSV_OUT))
    asyncio.run(loader.run_pipeline())