import os
from pathlib import Path

# Chemin racine du projet
ROOT_DIR = Path(__file__).parent.parent

# Chemins des dossiers principaux
DATA_DIR = ROOT_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
RESULTS_DIR = DATA_DIR / "results"

# Chemins des fichiers de données brutes
DATA_FILES = {
    'ARCHETYPES_FILE': RAW_DATA_DIR / "quebec_archetypes_with_weather_zones.csv",
    'RESIDENTIAL_DATA_FILE': RAW_DATA_DIR / "donnees_residentielles_with_zones_final.csv",
    'HYDRO_QUEBEC_FILES': {
        2019: RAW_DATA_DIR / "conso_residentielle_2019.csv",
        2020: RAW_DATA_DIR / "conso_residentielle_2020.csv",
        2021: RAW_DATA_DIR / "conso_residentielle_2021.csv",
        2022: RAW_DATA_DIR / "conso_residentielle_2022.csv",
        2023: RAW_DATA_DIR / "conso_residentielle_2023.csv"
    }
}

# Structure OpenStudio
OPENSTUDIO_DIR = ROOT_DIR / "openstudio"
OPENSTUDIO_MEASURES = OPENSTUDIO_DIR / "measures"  # Correction ici, plus de tuple
WORKFLOW_TEMPLATES = OPENSTUDIO_DIR / "workflow_templates"
WEATHER_DIR = OPENSTUDIO_DIR / "weather"

# Structure résultats
RESULTS_STRUCTURE = {
    'CALIBRATION_DIR': RESULTS_DIR / "calibration",  # Pour les résultats de calibration par campagne
    'SIMULATIONS_DIR': RESULTS_DIR / "openstudio_runs",  # Pour les fichiers de simulation
    'VALIDATION_DIR': RESULTS_DIR / "validation",  # Pour les résultats de validation
    'PROCESSED_DIR': RESULTS_DIR / "processed",  # Pour les résultats traités
    'PROVINCIAL_DIR': RESULTS_DIR / "provincial",  # Pour les résultats agrégés provinciaux
    'VISUALIZATION_DIR': RESULTS_DIR / "visualization"  # Pour les résultats agrégés provinciaux

}

def get_campaign_dir(campaign_id: str) -> Path:
    """Retourne le chemin du dossier d'une campagne de calibration"""
    campaign_dir = RESULTS_STRUCTURE['CALIBRATION_DIR'] / f"campaign_{campaign_id}"
    campaign_dir.mkdir(parents=True, exist_ok=True)
    return campaign_dir

def get_iteration_dirs(iteration: int, campaign_id: str = None) -> dict:
    """
    Retourne les chemins des dossiers pour une itération
    """
    # Dossiers principaux
    sim_dir = RESULTS_STRUCTURE['SIMULATIONS_DIR'] / f"iteration_{iteration}"
    processed_dir = RESULTS_STRUCTURE['PROCESSED_DIR'] / f"iteration_{iteration}"
    provincial_dir = RESULTS_STRUCTURE['PROVINCIAL_DIR'] / f"iteration_{iteration}"
    
    # Créer les dossiers principaux
    for dir_path in [sim_dir, processed_dir, provincial_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)

    # Fichiers de résultats
    provincial_file = provincial_dir / 'results.csv'
    validation_file = RESULTS_STRUCTURE['VALIDATION_DIR'] / f"validation_iter_{iteration}.json"

    # Dossier de calibration si nécessaire
    if campaign_id:
        calib_dir = get_campaign_dir(campaign_id) / f"iteration_{iteration}"
        calib_dir.mkdir(parents=True, exist_ok=True)
    else:
        calib_dir = None

    return {
        'simulation_dir': sim_dir,
        'processed_dir': processed_dir,
        'provincial_dir': provincial_dir,
        'provincial_file': provincial_file,
        'validation_file': validation_file,
        'calibration_dir': calib_dir
    }

def verify_paths() -> dict:
    """Vérifie l'existence des chemins et fichiers essentiels"""
    report = {
        'directories': {},
        'files': {},
        'openstudio': {},
        'results_structure': {}
    }
    
    # Vérification dossiers principaux
    for dir_name, dir_path in {
        'ROOT': ROOT_DIR,
        'DATA': DATA_DIR,
        'RAW_DATA': RAW_DATA_DIR,
        'PROCESSED_DATA': PROCESSED_DATA_DIR,
        'RESULTS': RESULTS_DIR
    }.items():
        report['directories'][dir_name] = dir_path.exists()
    
    # Vérification fichiers de données
    for file_key, file_path in DATA_FILES.items():
        if file_key != 'HYDRO_QUEBEC_FILES':
            report['files'][file_key] = file_path.exists()
    
    # Vérification structure OpenStudio
    report['openstudio']['OPENSTUDIO_MEASURES'] = OPENSTUDIO_MEASURES.exists()
    report['openstudio']['WORKFLOW_TEMPLATES'] = WORKFLOW_TEMPLATES.exists()
    report['openstudio']['WEATHER_DIR'] = WEATHER_DIR.exists()
    
    # Vérification structure résultats
    for dir_name, dir_path in RESULTS_STRUCTURE.items():
        report['results_structure'][dir_name] = dir_path.exists()
    
    return report

if __name__ == "__main__":
    # Créer structure
    for path in RESULTS_STRUCTURE.values():
        path.mkdir(parents=True, exist_ok=True)
    
    # Vérifier et afficher rapport
    report = verify_paths()
    print("\nRapport de vérification des chemins :")
    print("-" * 50)
    
    for category, items in report.items():
        print(f"\n{category.upper()}:")
        for name, exists in items.items():
            print(f"- {name}: {'✓' if exists else '✗'}")