import os
import re

root_dir = r"C:\Users\beugre niamba\Desktop\Challenge_artefact\sql_rag_agent\src"

attributes = [
    "user_query", "sql_query", "sql_results", "errors", 
    "classification", "chart_generated", "final_answer",
    "similar_examples_context", "chart_data"
]

def patch_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    new_content = content
    changes_made = 0

    for attr in attributes:
        # On cherche state.nom_attribut
        pattern = rf"state\.{attr}\b"
        # On remplace par state['nom_attribut'] (avec guillemets simples)
        # pour éviter les conflits dans les f-strings
        replacement = f"state['{attr}']"
        
        if re.search(pattern, new_content):
            new_content = re.sub(pattern, replacement, new_content)
            changes_made += 1
    
    # Correction spécifique pour les erreurs déjà générées avec doubles guillemets
    # Transforme ["user_query"] en ['user_query']
    for attr in attributes:
        wrong_nested = f'state["{attr}"]'
        correct_nested = f"state['{attr}']"
        if wrong_nested in new_content:
            new_content = new_content.replace(wrong_nested, correct_nested)
            changes_made += 1

    if changes_made > 0:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"✅ {file_path} : {changes_made} corrections.")

if __name__ == "__main__":
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith(".py"):
                patch_file(os.path.join(root, file))