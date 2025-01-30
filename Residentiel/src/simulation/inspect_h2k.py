import xml.etree.ElementTree as ET
from pathlib import Path
import sys
import logging

# Setup base logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('H2KInspector')

def print_element_structure(element, level=0, max_level=None, file=None):
    """
    Affiche la structure d'un élément XML avec ses attributs et valeurs
    """
    if max_level is not None and level > max_level:
        return

    # Indentation pour la hiérarchie
    indent = "  " * level

    # Informations sur l'élément
    element_info = f"{indent}{element.tag}"
    
    # Ajouter les attributs s'il y en a
    if element.attrib:
        element_info += f" {element.attrib}"
        
    # Ajouter la valeur si c'est une feuille
    if element.text and element.text.strip():
        text = element.text.strip()
        if len(text) > 50:
            text = text[:47] + "..."
        element_info += f" = {text}"

    # Écrire dans le fichier ou afficher
    if file:
        print(element_info, file=file)
    else:
        print(element_info)

    # Récursivement traiter les enfants
    for child in element:
        print_element_structure(child, level + 1, max_level, file)

def analyze_h2k_file(file_path: Path, output_file: Path = None, max_level: int = None):
    """
    Analyse un fichier H2K et affiche/sauvegarde sa structure
    """
    try:
        logger.info(f"Analyse de {file_path}")
        tree = ET.parse(file_path)
        root = tree.getroot()

        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                print(f"Structure de {file_path}:", file=f)
                print("-" * 50, file=f)
                print_element_structure(root, max_level=max_level, file=f)
        else:
            print(f"Structure de {file_path}:")
            print("-" * 50)
            print_element_structure(root, max_level=max_level)

    except Exception as e:
        logger.error(f"Erreur lors de l'analyse : {str(e)}")

def find_parameters(element, param_names, path="", results=None):
    """
    Cherche des paramètres spécifiques dans la structure
    """
    if results is None:
        results = {}

    current_path = f"{path}/{element.tag}" if path else element.tag

    # Vérifier si cet élément ou ses attributs contiennent les mots cherchés
    for param in param_names:
        param_lower = param.lower()
        if (param_lower in element.tag.lower() or 
            any(param_lower in k.lower() or param_lower in str(v).lower() 
                for k, v in element.attrib.items())):
            if param not in results:
                results[param] = []
            results[param].append({
                'path': current_path,
                'tag': element.tag,
                'attrib': element.attrib,
                'value': element.text.strip() if element.text else None
            })

    # Recherche récursive dans les enfants
    for child in element:
        find_parameters(child, param_names, current_path, results)

    return results

if __name__ == "__main__":
    # Chemins
    project_root = Path(__file__).parent.parent.parent
    h2k_stock_dir = project_root / "data" / "raw" / "individual_stock"
    output_dir = project_root / "data" / "results" / "h2k_analysis"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Paramètres à chercher
    parameters_of_interest = [
        "heating", "cooling", "setpoint", 
        "temperature", "infiltration", "ventilation",
        "thermostat", "dhw", "water"
    ]

    # Trouver le premier fichier H2K
    h2k_files = list(h2k_stock_dir.rglob("*.H2K"))
    if not h2k_files:
        h2k_files = list(h2k_stock_dir.rglob("*.h2k"))

    if h2k_files:
        sample_file = h2k_files[0]
        
        # 1. Analyser la structure complète
        output_file = output_dir / "h2k_structure.txt"
        analyze_h2k_file(sample_file, output_file, max_level=None)
        logger.info(f"Structure sauvegardée dans {output_file}")

        # 2. Chercher les paramètres spécifiques
        try:
            tree = ET.parse(sample_file)
            root = tree.getroot()
            
            # Chercher les paramètres
            results = find_parameters(root, parameters_of_interest)
            
            # Sauvegarder les résultats
            output_file = output_dir / "h2k_parameters.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                print("Paramètres trouvés :", file=f)
                print("-" * 50, file=f)
                for param, occurrences in results.items():
                    print(f"\n{param}:", file=f)
                    for occur in occurrences:
                        print(f"  Path: {occur['path']}", file=f)
                        print(f"  Tag: {occur['tag']}", file=f)
                        if occur['attrib']:
                            print(f"  Attributes: {occur['attrib']}", file=f)
                        if occur['value']:
                            print(f"  Value: {occur['value']}", file=f)
                        print("", file=f)
            
            logger.info(f"Paramètres sauvegardés dans {output_file}")
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche des paramètres : {str(e)}")
        
    else:
        logger.error("Aucun fichier H2K trouvé")