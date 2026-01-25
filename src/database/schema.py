# db/schema.py
from sqlalchemy import Table, Column, Integer, String, Float, ForeignKey, MetaData, Boolean

metadata = MetaData()


circonscriptions = Table(
    "circonscriptions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("region_nom", String, nullable=False, index=True), 
    Column("code_circonscription", String), 
    Column("nom_circonscription", String, nullable=False),
    
    # Colonnes NORMALISÉES (Ajoutées pour la recherche facile)
    Column("region_nom_norm", String, index=True),
    Column("nom_circonscription_norm", String, index=True),

    # Statistiques
    Column("nb_bureau", Integer, default=0),
    Column("inscrits", Integer, default=0),
    Column("votants", Integer, default=0),
    Column("taux_participation", Float, default=0.0),
    Column("bulletins_nuls", Integer, default=0),
    Column("suffrages_exprimes", Integer, default=0),
    Column("bulletins_blancs_nombre", Integer, default=0),
    Column("bulletins_blancs_pourcentage", Float, default=0.0),
)


candidats = Table(
    "candidats",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("circonscription_id", Integer, ForeignKey("circonscriptions.id"), nullable=False),
    
    Column("nom_liste_candidat", String, nullable=False),
    Column("parti_politique", String, nullable=True, index=True),
    
    # Colonnes NORMALISÉES
    Column("nom_liste_candidat_norm", String),
    Column("parti_politique_norm", String, index=True),

    Column("score_voix", Integer, default=0),
    Column("pourcentage_voix", Float, default=0.0),
    Column("est_elu", Boolean, default=False), 
)


vue_resultats_detailles = """
CREATE VIEW IF NOT EXISTS vue_resultats_detailles AS
SELECT 
    ci.region_nom,
    ci.region_nom_norm, -- L'agent peut filtrer ici (ex: WHERE region_nom_norm LIKE '%gbeke%')
    ci.nom_circonscription,
    ci.nom_circonscription_norm,
    ci.taux_participation,
    c.parti_politique,
    c.parti_politique_norm,
    c.nom_liste_candidat,
    c.nom_liste_candidat_norm,
    c.score_voix,
    c.pourcentage_voix,
    c.est_elu
FROM candidats c
JOIN circonscriptions ci ON c.circonscription_id = ci.id;
"""

# Vue B : Gagnants uniquement
vue_elus_uniquement = """
CREATE VIEW IF NOT EXISTS vue_elus_uniquement AS
SELECT 
    region_nom,
    nom_circonscription,
    parti_politique,
    nom_liste_candidat,
    score_voix
FROM vue_resultats_detailles
WHERE est_elu = 1 OR est_elu = 'TRUE';
"""


vue_stats_regionales = """
CREATE VIEW IF NOT EXISTS vue_stats_regionales AS
SELECT 
    region_nom,
    SUM(inscrits) as total_inscrits,
    SUM(votants) as total_votants,
    SUM(suffrages_exprimes) as total_exprimes,
    ROUND((CAST(SUM(votants) AS FLOAT) / SUM(inscrits)) * 100, 2) as taux_participation_moyen
FROM circonscriptions
GROUP BY region_nom;
"""

creation_views_sql = [vue_resultats_detailles, vue_elus_uniquement, vue_stats_regionales]

