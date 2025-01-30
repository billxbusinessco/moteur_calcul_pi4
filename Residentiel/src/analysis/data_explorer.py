import pandas as pd
import logging
from pathlib import Path
import sys
import os

# Ajout du chemin racine au PYTHONPATH
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from config.paths_config import DATA_FILES, verify_paths

class DataExplorer:
    def __init__(self):
        """
        Initialise l'explorateur de données
        """
        self.logger = self._setup_logger()
        self.paths_report = verify_paths()
        
    def _setup_logger(self):
        """Configure le logger"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger('DataExplorer')

    def load_and_analyze_archetypes(self):
        """
        Charge et analyse le fichier des archétypes
        """
        try:
            if not DATA_FILES['ARCHETYPES_FILE'].exists():
                raise FileNotFoundError(f"Fichier d'archétypes non trouvé: {DATA_FILES['ARCHETYPES_FILE']}")
            
            # Chargement du fichier des archétypes
            df_archetypes = pd.read_csv(DATA_FILES['ARCHETYPES_FILE'])
            
            # Analyse de base
            analysis = {
                'total_archetypes': len(df_archetypes),
                'weather_zones_distribution': df_archetypes['weather_zone'].value_counts().to_dict(),
                'columns': df_archetypes.columns.tolist(),
                'missing_values': df_archetypes.isnull().sum().to_dict()
            }
            
            self.logger.info("Analyse des archétypes terminée")
            return analysis
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'analyse des archétypes: {str(e)}")
            raise

if __name__ == "__main__":
    # Création de l'explorateur
    explorer = DataExplorer()
    
    # Vérification des fichiers
    print("\nVérification des répertoires :")
    print("-" * 50)
    for directory, exists in explorer.paths_report['directories'].items():
        print(f"{directory}: {'✓' if exists else '✗'}")
    
    print("\nVérification des fichiers principaux :")
    print("-" * 50)
    for key, exists in explorer.paths_report['files'].items():
        if key != 'HYDRO_QUEBEC_FILES':
            print(f"{key}: {'✓' if exists else '✗'}")
    
    print("\nVérification des fichiers Hydro-Québec :")
    print("-" * 50)
    for year, exists in explorer.paths_report['files']['HYDRO_QUEBEC_FILES'].items():
        print(f"Fichier {year}: {'✓' if exists else '✗'}")
        
    # Analyse des archétypes
    print("\nAnalyse des archétypes :")
    print("-" * 50)
    try:
        archetype_analysis = explorer.load_and_analyze_archetypes()
        print(f"Nombre total d'archétypes : {archetype_analysis['total_archetypes']}")
        print("\nDistribution par zone météo :")
        for zone, count in archetype_analysis['weather_zones_distribution'].items():
            print(f"Zone {zone}: {count} archétypes")
    except Exception as e:
        print(f"Erreur lors de l'analyse : {str(e)}")