import pandas as pd 

donnée=pd.read_csv(r'C:\Users\beugre niamba\Desktop\Challenge_artefact\sql_rag_agent\data\processed\elections_clean.csv')

print(donnée['region_nom_norm'].unique())