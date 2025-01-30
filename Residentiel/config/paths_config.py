import os
from pathlib import Path

# Chemin racine du projet
ROOT_DIR = Path(__file__).parent.parent

# Chemins des dossiers principaux
DATA_DIR = ROOT_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
RESULTS_DIR = DATA_DIR / "results"
H2K_STOCK_DIR = RAW_DATA_DIR / "individual_stock"

# Chemins des fichiers de données brutes
DATA_FILES = {
    'ARCHETYPES_FILE': RAW_DATA_DIR / "quebec_archetypes_with_weather_zones.csv",
    'RESIDENTIAL_DATA_FILE': RAW_DATA_DIR / "donnees_residentielles_with_zones_final.csv",
    'WEATHER_FILE': RAW_DATA_DIR / "CWEEDS_2020_stns_all_REV_20210324.csv",
    'MRC_SHP_FILE': RAW_DATA_DIR / "base_mrc_database.shp",
    'H2K_STOCK_DIR': H2K_STOCK_DIR,
    'HYDRO_QUEBEC_FILES': {
        2019: RAW_DATA_DIR / "conso_residentielle_2019.csv",
        2020: RAW_DATA_DIR / "conso_residentielle_2020.csv",
        2021: RAW_DATA_DIR / "conso_residentielle_2021.csv",
        2022: RAW_DATA_DIR / "conso_residentielle_2022.csv",
        2023: RAW_DATA_DIR / "conso_residentielle_2023.csv"
    }
}

# Structure des résultats
RESULTS_STRUCTURE = {
    'PROCESSED_DIR': RESULTS_DIR / 'processed_results',
    'PROVINCIAL_DIR': RESULTS_DIR / 'processed_results' / 'provincial_results',
    'VALIDATION_DIR': RESULTS_DIR / 'validation_results',
    'SIMULATIONS_DIR': RESULTS_DIR / 'simulations',
    'CAMPAIGNS_DIR': RESULTS_DIR / 'campaigns'
}

def create_directories():
    """Crée les répertoires nécessaires s'ils n'existent pas"""
    directories = [DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, RESULTS_DIR]
    
    # Ajouter structure résultats
    directories.extend(RESULTS_STRUCTURE.values())
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

def get_iteration_dirs(iteration: int) -> dict:
    """Retourne les chemins pour une itération donnée"""
    return {
        'iteration_dir': RESULTS_STRUCTURE['PROCESSED_DIR'] / f'iteration_{iteration}',
        'provincial_file': RESULTS_STRUCTURE['PROVINCIAL_DIR'] / f'provincial_results_iter_{iteration}.csv',
        'validation_file': RESULTS_STRUCTURE['VALIDATION_DIR'] / f'validation_iter_{iteration}.json'
    }

def verify_paths():
    """Vérifie l'existence des fichiers et retourne un rapport"""
    report = {
        'directories': {},
        'files': {},
        'results_structure': {}
    }
    
    # Vérification des répertoires principaux
    for directory in [DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, RESULTS_DIR]:
        report['directories'][str(directory)] = directory.exists()
    
    # Vérification de la structure résultats
    for name, path in RESULTS_STRUCTURE.items():
        report['results_structure'][name] = path.exists()
    
    # Vérification des fichiers principaux
    for key, path in DATA_FILES.items():
        if key != 'HYDRO_QUEBEC_FILES':
            report['files'][key] = path.exists()
    
    # Vérification des fichiers Hydro-Québec
    report['files']['HYDRO_QUEBEC_FILES'] = {
        year: path.exists() 
        for year, path in DATA_FILES['HYDRO_QUEBEC_FILES'].items()
    }
    
    return report

if __name__ == "__main__":
    print("\nTest de la configuration des chemins :")
    print("-" * 50)
    
    # 1. Création des répertoires
    print("\n1. Création des répertoires...")
    create_directories()
    
    # 2. Vérification de la structure
    report = verify_paths()
    
    print("\n2. Structure des répertoires :")
    print("-" * 30)
    for dir_name, exists in report['directories'].items():
        print(f"{dir_name}: {'✓' if exists else '✗'}")
        
    print("\n3. Structure des résultats :")
    print("-" * 30)
    for dir_name, exists in report['results_structure'].items():
        print(f"{dir_name}: {'✓' if exists else '✗'}")
    
    # 4. Test get_iteration_dirs
    print("\n4. Test chemins d'itération :")
    print("-" * 30)
    iteration_paths = get_iteration_dirs(0)
    for name, path in iteration_paths.items():
        print(f"{name}: {path}")